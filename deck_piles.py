from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

CARD_W = 180
CARD_H = 251
CANVAS_W = 1600
CANVAS_H = 1400
CACHE_DIR = Path(".card_cache")
TOP_MARGIN = 120
BOTTOM_MARGIN = 70
CARD_VERTICAL_GAP = 12
CARD_HORIZONTAL_GAP = 6
SECTION_GAP = 24
RIGHT_MARGIN = 40


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    configured_path = os.environ.get("MTG_FONT_PATH")
    if configured_path and Path(configured_path).exists():
        return ImageFont.truetype(configured_path, size)
    if os.name == "nt":
        windows_font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        windows_font = windows_font_dir / ("arialbd.ttf" if bold else "arial.ttf")
        if windows_font.exists():
            return ImageFont.truetype(windows_font, size)
    fc_match = shutil.which("fc-match")
    if fc_match:
        families = ("Arial:style=Bold", "Arial", "sans-serif:style=Bold", "sans-serif") if bold else ("Arial", "sans-serif")
        for family in families:
            result = subprocess.run(
                [fc_match, "-f", "%{file}", family],
                capture_output=True,
                text=True,
                check=False,
            )
            font_path = Path(result.stdout.strip())
            if result.returncode == 0 and font_path.exists():
                return ImageFont.truetype(font_path, size)
    return ImageFont.load_default(size=size)


BADGE_FONT = load_font(22, bold=True)
HEADER_FONT = load_font(26, bold=True)
SECTION_FONT = load_font(18, bold=True)
TYPE_FONT = load_font(15, bold=True)
CATEGORY_NAMES = ("Creatures", "Sorceries", "Instants", "Artifacts", "Other", "Lands")
SYMBOL_DIR = Path(__file__).parent / "mana_symbols"
CARD_TYPE_SYMBOL_DIR = Path(__file__).parent / "card_type_symbols"
SCRYFALL_RETRIES = 3
MTG_COLORS = {
    "W": (245, 245, 220),
    "U": (55, 145, 225),
    "B": (95, 80, 105),
    "R": (225, 70, 45),
    "G": (70, 170, 80),
}
LOGGER = logging.getLogger("deck_piles")


def parse_decklist(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]], str | None]:
    LOGGER.info("Reading decklist: %s", path)
    main_deck: list[tuple[int, str]] = []
    sideboard: list[tuple[int, str]] = []
    current_section = main_deck
    deck_name: str | None = None
    in_about = False
    pattern = re.compile(r"^(?:(\d+)x?\s+)?(.+?)\s*$")
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section_name = line.lstrip("#").strip().rstrip(":").strip().lower()
        if section_name == "about":
            in_about = True
            continue
        if section_name in {"deck", "main", "mainboard"}:
            in_about = False
            current_section = main_deck
            continue
        if section_name == "sideboard":
            in_about = False
            current_section = sideboard
            continue
        if line.startswith(("#", "//")):
            continue
        if in_about:
            name_match = re.match(r"^name\s+(.+?)\s*$", line, re.IGNORECASE)
            if name_match:
                deck_name = name_match.group(1).strip()
            continue
        match = pattern.match(line)
        if not match:
            continue
        quantity = int(match.group(1) or 1)
        name = match.group(2).strip()
        current_section.append((quantity, name))
    if not main_deck and not sideboard:
        raise ValueError(f"No cards found in {path}")
    LOGGER.info("Parsed %d main entries and %d sideboard entries", len(main_deck), len(sideboard))
    LOGGER.info("Deck name: %s", deck_name or "(default)")
    return main_deck, sideboard, deck_name


def safe_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") + ".jpg"


def output_filename(title: str) -> Path:
    filename = re.sub(r"[^A-Za-z0-9._ -]+", "", title).strip(" .")
    filename = re.sub(r"\s+", "-", filename) or "deck"
    return Path(f"{filename}.png")


def fetch_card(name: str, session: requests.Session) -> tuple[Image.Image, str, list[str]]:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / safe_filename(name)
    type_cache_path = cache_path.with_suffix(".json")
    if cache_path.exists() and type_cache_path.exists():
        metadata = json.loads(type_cache_path.read_text(encoding="utf-8"))
        if "colors" in metadata:
            LOGGER.info("Cache hit: %s", name)
            return Image.open(cache_path).convert("RGB"), metadata["type_line"], metadata["colors"]

    last_error: requests.RequestException | None = None
    for attempt in range(SCRYFALL_RETRIES):
        try:
            LOGGER.info("Fetching %s from Scryfall (attempt %d/%d)", name, attempt + 1, SCRYFALL_RETRIES)
            response = session.get(
                "https://api.scryfall.com/cards/named",
                params={"exact": name},
                timeout=20,
            )
            response.raise_for_status()
            card = response.json()
            image_url = card.get("image_uris", {}).get("normal")
            if not image_url and card.get("card_faces"):
                image_url = card["card_faces"][0].get("image_uris", {}).get("normal")
            if not image_url:
                raise ValueError(f"Scryfall returned no image for {name}")
            image_response = session.get(image_url, timeout=30)
            image_response.raise_for_status()
            colors = card.get("color_identity") or card.get("colors", [])
            cache_path.write_bytes(image_response.content)
            type_cache_path.write_text(
                json.dumps({"type_line": card.get("type_line", ""), "colors": colors}),
                encoding="utf-8",
            )
            LOGGER.info("Fetched and cached: %s", name)
            return Image.open(io.BytesIO(image_response.content)).convert("RGB"), card.get("type_line", ""), colors
        except requests.RequestException as error:
            last_error = error
            LOGGER.warning("Scryfall request failed for %s: %s", name, error)
            if attempt < SCRYFALL_RETRIES - 1:
                retry_after = response.headers.get("Retry-After", "") if "response" in locals() else ""
                try:
                    delay = max(1.0, float(retry_after))
                except ValueError:
                    delay = 2.0 ** attempt
                LOGGER.info("Retrying %s in %.1f seconds", name, delay)
                time.sleep(delay)
    raise last_error or requests.RequestException(f"Could not fetch {name}")


def card_category(type_line: str) -> int:
    if "Creature" in type_line:
        return 0
    if "Sorcery" in type_line:
        return 1
    if "Instant" in type_line:
        return 2
    if "Artifact" in type_line:
        return 3
    if "Land" in type_line:
        return 5
    return 4


def card_type_symbol(type_line: str) -> str:
    for card_type in ("creature", "sorcery", "instant", "artifact", "enchantment", "planeswalker", "battle", "kindred", "land"):
        if card_type.capitalize() in type_line:
            return card_type
    return "artifact"


def header_color(counts: dict[str, int]) -> tuple[int, int, int]:
    total = sum(counts.values())
    if not total:
        return (70, 70, 70)
    mixed = tuple(
        int(sum(MTG_COLORS[color][channel] * count for color, count in counts.items()) / total)
        for channel in range(3)
    )
    brightness = sum(mixed) / 3
    return tuple(min(255, int(brightness + (channel - brightness) * 1.8)) for channel in mixed)


def draw_header_gradient(
    canvas: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
    counts: dict[str, int],
) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    gradient_start = left + int((right - left) * 0.7)
    palette = {**MTG_COLORS, "C": (115, 115, 115)}
    visible_counts = {
        color: count
        for color, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if color in palette and count
    }
    total = sum(visible_counts.values())
    if not total:
        return
    LOGGER.info("Drawing color header with %d segments", len(visible_counts))
    boundaries = [gradient_start]
    for count in list(visible_counts.values())[:-1]:
        boundaries.append(boundaries[-1] + (right - gradient_start + 1) * count / total)
    boundaries.append(right + 1)
    colors = list(visible_counts)
    for index, color_name in enumerate(colors):
        segment_left = int(round(boundaries[index]))
        segment_right = int(round(boundaries[index + 1]))
        draw.rectangle((segment_left, top, segment_right, bottom), fill=(*palette[color_name], 255))
        segment_width = segment_right - segment_left
        symbol_path = SYMBOL_DIR / f"{color_name}.png"
        if symbol_path.exists():
            symbol = Image.open(symbol_path).convert("RGBA")
            symbol_bounds = symbol.getbbox()
            symbol_size = segment_width - 6
            if symbol_bounds and symbol_size >= 38:
                symbol = symbol.crop(symbol_bounds).resize((38, 38), Image.Resampling.LANCZOS)
                symbol_x = segment_left + (segment_width - symbol.width) // 2
                symbol_y = top + (bottom - top - symbol.height) // 2
                canvas.paste(symbol, (symbol_x, symbol_y), symbol)
        if segment_right < right:
            draw.line((segment_right, top, segment_right, bottom), fill=(10, 12, 12, 255), width=3)


def draw_mana_symbol(draw: ImageDraw.ImageDraw, color_name: str, center_x: int, center_y: int) -> None:
    fill = (255, 255, 255, 235)
    if color_name == "W":
        draw.ellipse((center_x - 7, center_y - 7, center_x + 7, center_y + 7), outline=fill, width=3)
    elif color_name == "U":
        draw.ellipse((center_x - 8, center_y - 5, center_x + 8, center_y + 7), outline=fill, width=3)
        draw.arc((center_x - 5, center_y - 10, center_x + 5, center_y + 2), 180, 360, fill=fill, width=3)
    elif color_name == "B":
        draw.ellipse((center_x - 6, center_y - 9, center_x + 6, center_y + 5), fill=fill)
        draw.polygon(((center_x - 9, center_y + 4), (center_x + 9, center_y + 4), (center_x, center_y + 10)), fill=fill)
    elif color_name == "R":
        draw.polygon(((center_x - 2, center_y - 10), (center_x + 8, center_y - 1), (center_x + 2, center_y - 1), (center_x + 5, center_y + 10), (center_x - 8, center_y), (center_x - 2, center_y)), fill=fill)
    elif color_name == "G":
        draw.ellipse((center_x - 8, center_y - 6, center_x + 8, center_y + 8), outline=fill, width=3)
        draw.line((center_x, center_y - 9, center_x, center_y + 4), fill=fill, width=3)
    elif color_name == "C":
        draw.ellipse((center_x - 8, center_y - 8, center_x + 8, center_y + 8), outline=fill, width=3)


def make_background(path: Path | None) -> Image.Image:
    if path:
        return ImageOps.fit(Image.open(path).convert("RGB"), (CANVAS_W, CANVAS_H))

    image = Image.new("RGB", (CANVAS_W, CANVAS_H))
    pixels = image.load()
    for y in range(CANVAS_H):
        shade = int(42 + 18 * (y / CANVAS_H))
        for x in range(CANVAS_W):
            grain = (x * 13 + y * 7) % 7
            pixels[x, y] = (shade + grain, shade - 8 + grain, shade - 18 + grain)
    image = image.filter(ImageFilter.GaussianBlur(1.2))
    draw = ImageDraw.Draw(image, "RGBA")
    for x in range(-CANVAS_H, CANVAS_W, 80):
        draw.line((x, 0, x + CANVAS_H, CANVAS_H), fill=(210, 170, 90, 18), width=2)
    return image


def render_group(
    canvas: Image.Image,
    deck: list[tuple[int, str]],
    top: int,
    bottom: int,
    columns: int,
    session: requests.Session,
    left: int,
    right: int,
    color_counts: dict[str, int],
) -> dict[str, int]:
    if not deck:
        return {}
    LOGGER.info("Rendering group with %d entries and %d columns", len(deck), columns)
    cards: list[tuple[int, str, Image.Image, int, str]] = []
    for quantity, name in deck:
        try:
            card, type_line, colors = fetch_card(name, session)
        except (requests.RequestException, ValueError) as error:
            raise RuntimeError(f"Could not fetch {name} after {SCRYFALL_RETRIES} attempts: {error}") from error
        for color in colors:
            color_counts[color] = color_counts.get(color, 0) + quantity
        if not colors:
            color_counts["C"] = color_counts.get("C", 0) + quantity
        cards.append((quantity, name, card, card_category(type_line), card_type_symbol(type_line)))
    cards.sort(key=lambda entry: (entry[3], entry[1].lower()))
    if not cards:
        return {}
    category_counts: dict[str, int] = {}
    for quantity, name, card, category, symbol_name in cards:
        category_counts[symbol_name] = category_counts.get(symbol_name, 0) + quantity
    LOGGER.info("Group ready: %d card images", len(cards))
    column_count = max(1, min(columns, len(cards)))
    row_count = (len(cards) + column_count - 1) // column_count
    horizontal_step = (right - left - CARD_W) / max(1, column_count - 1)
    available_height = bottom - top - CARD_H
    vertical_step = min(
        CARD_H + CARD_VERTICAL_GAP,
        available_height / max(1, row_count - 1),
    )
    cards_overlap_horizontally = horizontal_step < CARD_W + CARD_HORIZONTAL_GAP
    draw = ImageDraw.Draw(canvas, "RGBA")

    for index, (quantity, name, card, category, symbol_name) in enumerate(cards):
        column = index % column_count
        row = index // column_count
        x = int(left + column * horizontal_step)
        y = int(top + row * vertical_step)
        card = ImageOps.fit(card, (CARD_W, CARD_H))
        card = ImageOps.expand(card, border=3, fill=(235, 225, 200))
        rotated = card.convert("RGBA")
        shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
        shadow.paste((0, 0, 0, 100), (8, 10), rotated.getchannel("A"))
        canvas.paste(shadow, (x + 8, y + 8), shadow)
        canvas.paste(rotated, (x, y), rotated)
        if quantity > 1:
            if cards_overlap_horizontally:
                badge = (x + 8, y + CARD_H - 56, x + 62, y + CARD_H - 10)
                badge_center = (x + 35, y + CARD_H - 33)
            else:
                badge = (x + CARD_W - 62, y + 10, x + CARD_W - 8, y + 56)
                badge_center = (x + CARD_W - 35, y + 33)
            draw.rounded_rectangle(
                badge,
                radius=9,
                fill=(255, 238, 120, 255),
                outline=(15, 18, 16, 255),
                width=2,
            )
            draw.text(
                badge_center,
                f"x{quantity}",
                anchor="mm",
                font=BADGE_FONT,
                fill=(15, 18, 16, 255),
            )
    return category_counts


def draw_type_counts(canvas: Image.Image, x: int, y: int, category_counts: dict[str, int]) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    symbol_names = ("creature", "sorcery", "instant", "artifact", "enchantment", "planeswalker", "battle", "kindred", "land")
    for symbol_name in symbol_names:
        count = category_counts.get(symbol_name, 0)
        if not count:
            continue
        symbol_path = CARD_TYPE_SYMBOL_DIR / f"{symbol_name}.png"
        if symbol_path.exists():
            symbol = Image.open(symbol_path).convert("RGBA")
            symbol.thumbnail((22, 22), Image.Resampling.LANCZOS)
            symbol_x = x
            symbol_y = y + (20 - symbol.height) // 2
            canvas.paste(symbol, (symbol_x, symbol_y), symbol)
            draw.text((x + 27, y), str(count), font=TYPE_FONT, fill=(35, 35, 35, 255))
        else:
            draw.text((x, y), str(count), font=TYPE_FONT, fill=(35, 35, 35, 255))
        x += 50


def panel_right(left: int, deck: list[tuple[int, str]], columns: int) -> int:
    column_count = max(1, min(columns, len(deck)))
    return left + (column_count - 1) * (CARD_W + CARD_HORIZONTAL_GAP) + CARD_W


def render(
    main_deck: list[tuple[int, str]],
    sideboard: list[tuple[int, str]],
    background: Path | None,
    output: Path,
    columns: int,
    title: str,
) -> None:
    canvas = make_background(background)
    session = requests.Session()
    session.headers["User-Agent"] = "mtg-deck-piles/1.0 (personal use)"
    draw = ImageDraw.Draw(canvas, "RGBA")
    main_count = sum(quantity for quantity, name in main_deck)
    sideboard_count = sum(quantity for quantity, name in sideboard)
    main_left = 60
    sideboard_width = panel_right(0, sideboard, 2) if sideboard else 0
    max_sideboard_left = CANVAS_W - RIGHT_MARGIN - sideboard_width
    sideboard_left = max_sideboard_left if sideboard else CANVAS_W - RIGHT_MARGIN
    main_right = sideboard_left - SECTION_GAP if sideboard else CANVAS_W - RIGHT_MARGIN
    sideboard_right = sideboard_left + sideboard_width
    color_counts: dict[str, int] = {}
    main_types = render_group(canvas, main_deck, 220, CANVAS_H - BOTTOM_MARGIN, columns, session, main_left, main_right, color_counts)
    sideboard_types = render_group(canvas, sideboard, 220, CANVAS_H - BOTTOM_MARGIN, 2, session, sideboard_left, sideboard_right, color_counts)
    draw.rectangle((main_left, 35, 650, 98), fill=(10, 12, 12, 255))
    draw_header_gradient(canvas, main_left, 35, 650, 98, color_counts)
    draw.text(
        (main_left + 15, 49),
        title,
        font=HEADER_FONT,
        fill=(255, 255, 255, 255),
    )
    draw.rectangle((main_left, 102, main_right, 155), fill=(235, 231, 218, 255))
    draw.text(
        (main_left + 15, 115),
        f"{main_count} cards",
        font=SECTION_FONT,
        fill=(35, 35, 35, 255),
    )
    draw_type_counts(canvas, main_left + 120, 115, main_types)
    draw.rectangle((sideboard_left, 102, sideboard_right, 184), fill=(255, 255, 255, 255))
    draw.text((sideboard_left + 5, 108), "SIDEBOARD", font=SECTION_FONT, fill=(35, 35, 35, 255))
    draw.text((sideboard_left + 5, 132), f"{sideboard_count} cards", font=TYPE_FONT, fill=(35, 35, 35, 255))
    draw_type_counts(canvas, sideboard_left + 75, 132, sideboard_types)
    draw.rectangle((main_left, 162, main_right, 184), fill=(255, 255, 255, 255))
    draw.text((main_left + 15, 163), "MAIN DECK", font=SECTION_FONT, fill=(35, 35, 35, 255))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=95)
    LOGGER.info("Image written: %s", output)
    print(f"Saved {output} ({main_count} main cards, {sideboard_count} sideboard cards)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an MTG decklist as overlapping card piles.")
    parser.add_argument("decklist", type=Path, help="Text file containing quantities and card names")
    parser.add_argument("-o", "--output", type=Path, help="Output PNG path; defaults to the deck name")
    parser.add_argument("-b", "--background", type=Path, help="Optional background image", default="background.png")
    parser.add_argument("-c", "--columns", type=int, default=6, help="Number of piles across the image")
    parser.add_argument("--title", help="Override the title from the decklist About section")
    parser.add_argument("--quiet", action="store_true", help="Show only the final result")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    if args.columns < 1:
        parser.error("--columns must be at least 1")
    try:
        main_deck, sideboard, deck_name = parse_decklist(args.decklist)
        title = args.title or deck_name or "MTG deck"
        output = args.output or output_filename(title)
        LOGGER.info("Using output file: %s", output)
        render(main_deck, sideboard, args.background, output, args.columns, title)
    except (OSError, ValueError, RuntimeError, requests.RequestException) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
