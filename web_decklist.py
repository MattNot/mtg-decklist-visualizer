from __future__ import annotations

import argparse
import html
import os
from pathlib import Path

import requests

from deck_piles import (
    CARD_TYPE_SYMBOL_DIR,
    CATEGORY_NAMES,
    card_category,
    card_type_symbol,
    fetch_card,
    parse_decklist,
    parse_decklist_settings,
    safe_filename,
)

ROOT = Path(__file__).parent
DEFAULT_TEMPLATE = ROOT / "figma-export" / "figma-export" / "prova-decklist.html"
DEFAULT_OUTPUT = DEFAULT_TEMPLATE
CACHE_DIR = ROOT / ".card_cache"
IMAGE_DIR = DEFAULT_TEMPLATE.parent / "images"


def relative_asset(path: Path, output: Path) -> str:
    return Path(os.path.relpath(path, output.parent)).as_posix()


def load_cards(entries: list[tuple[int, str]], session: requests.Session) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    for quantity, name in entries:
        _, type_line, colors = fetch_card(name, session)
        cards.append(
            {
                "quantity": quantity,
                "name": name,
                "type_line": type_line,
                "colors": colors,
                "category": card_category(type_line),
                "symbol": card_type_symbol(type_line),
                "image": CACHE_DIR / safe_filename(name),
            }
        )
    return sorted(cards, key=lambda card: (int(card["category"]), str(card["name"]).lower()))


def render_cards(cards: list[dict[str, object]], output: Path) -> str:
    rendered: list[str] = []
    for card in cards:
        name = html.escape(str(card["name"]))
        image = html.escape(relative_asset(Path(card["image"]), output), quote=True)
        type_line = html.escape(str(card["type_line"]))
        quantity = int(card["quantity"])
        badge = f'<span class="copies">x{quantity}</span>' if quantity > 1 else ""
        rendered.append(
            f'<article class="card" title="{name} - {type_line}">'
            f'<img src="{image}" alt="{name}" loading="lazy">{badge}</article>'
        )
    return "\n".join(rendered)


def render_type_summary(cards: list[dict[str, object]], output: Path) -> str:
    counts: dict[str, int] = {}
    for card in cards:
        symbol = str(card["symbol"])
        counts[symbol] = counts.get(symbol, 0) + int(card["quantity"])
    parts: list[str] = []
    for symbol, count in counts.items():
        symbol_path = CARD_TYPE_SYMBOL_DIR / f"{symbol}.png"
        if symbol_path.exists():
            source = html.escape(relative_asset(symbol_path, output), quote=True)
            parts.append(f'<span class="type-count"><img src="{source}" alt="">{count}</span>')
        else:
            parts.append(f'<span class="type-count">{count}</span>')
    return "".join(parts)


def render_section(
    name: str,
    cards: list[dict[str, object]],
    output: Path,
    columns: int,
) -> str:
    total = sum(int(card["quantity"]) for card in cards)
    card_markup = render_cards(cards, output)
    summary = render_type_summary(cards, output)
    section_class = name.lower().replace(" ", "-")
    rows = (len(cards) + columns - 1) // columns if cards else 0
    style = f"--columns:{columns}"
    if rows > 4:
        available_height = 684
        card_height = (available_height - 8 * (rows - 1)) / rows
        card_width = card_height * 94 / 128
        style += f";--card-width:{card_width:.2f}px"
    return f'<section class="card-panel {section_class}" style="{style}"><div class="card-grid">{card_markup}</div></section>'


def render_stat(name: str, cards: list[dict[str, object]], output: Path) -> str:
    total = sum(int(card["quantity"]) for card in cards)
    return (
        f'<div class="deck-stat"><div class="stat-label">{name.upper()} / {total} Carte</div>'
        f'<div class="type-summary">{render_type_summary(cards, output)}</div></div>'
    )


def write_page(
    main_deck: list[dict[str, object]],
    sideboard: list[dict[str, object]],
    title: str,
    author: str,
    event: str,
    output: Path,
    columns: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    logo = html.escape(relative_asset(IMAGE_DIR / "logo-lpc-letter-white.png", output), quote=True)
    thumbnail = html.escape(relative_asset(IMAGE_DIR / "thumbnail.png", output), quote=True)
    safe_title = html.escape(title)
    safe_author = html.escape(author)
    safe_event = html.escape(event)
    page = f'''<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Decklist di {safe_title}">
  <title>{safe_title} | Lega Pauper Cosenza</title>
  <link rel="stylesheet" href="styles.css">
  <style>
    :root {{ --columns: {columns}; --brick: #a43f38; --ink: #7e332d; --canvas-scale: 1.40625; --header-split: 67.8%; }}
    html, body {{ width: 100%; min-height: 100%; overflow-x: hidden; overflow-y: auto; }}
    .prova-decklist-1 {{ width: 768px; height: 1024px; overflow: hidden; transform: scale(var(--canvas-scale)); transform-origin: top left; background: #f8f7f7; color: white; }}
    .header-74 {{ position: relative; height: 292px; overflow: hidden; background: var(--brick); }}
    .header-74::after {{ content: ""; position: absolute; left: 0; right: 0; top: 211px; height: 81px; background: linear-gradient(to right, rgba(91, 31, 28, .4) 0 var(--header-split), rgba(49, 22, 21, .62) var(--header-split) 100%); pointer-events: none; }}
    .header-content {{ position: relative; z-index: 1; height: 211px; padding: 32px 34px 0; }}
    .header-thumb {{ position: absolute; z-index: 0; right: 0; top: 0; width: 32.2%; height: 211px; object-fit: cover; object-position: 62% center; clip-path: polygon(21% 0, 100% 0, 100% 100%, 0 100%); }}
    .header-title {{ position: relative; max-width: 470px; margin: 0 0 2px; font-family: var(--font-family-din-condensed), Impact, sans-serif; font-size: 43px; line-height: .98; letter-spacing: 0; white-space: nowrap; }}
    .header-author {{ margin: 0; font-size: 23px; line-height: 1.15; }}
    .header-event {{ position: absolute; left: 180px; bottom: 20px; max-width: 260px; margin: 0; padding: 0; font-size: 14px; line-height: 1.15; font-weight: 700; }}
    .header-logo {{ position: absolute; left: 34px; bottom: 18px; z-index: 2; width: 126px; height: auto; }}
    .header-stats {{ position: absolute; z-index: 2; left: 34px; right: 34px; bottom: 0; display: grid; grid-template-columns: 5fr 2fr; gap: 0; height: 81px; }}
    .deck-stat {{ padding: 15px 0 0; }}
    .deck-stat + .deck-stat {{ padding-left: 0; }}
    .stat-label {{ margin-bottom: 9px; font: 700 14px/1.1 var(--font-family-helvetica-neue), sans-serif; }}
    .type-summary {{ display: flex; flex-wrap: wrap; gap: 15px; align-items: center; }}
    .type-count {{ display: inline-flex; align-items: center; gap: 5px; font-size: 16px; }}
    .type-count img {{ width: 22px; height: 22px; object-fit: contain; }}
    .body-2 {{ display: grid; grid-template-columns: 5fr 2fr; gap: 18px; min-height: 732px; padding: 20px 34px 0; background: #f8f7f7; }}
    .card-panel {{ align-self: start; padding: 12px 10px 16px; border-radius: 3px; }}
    .main-deck {{ background: rgba(164, 63, 56, .08); }}
    .sideboard {{ background: rgba(90, 90, 90, .08); }}
    .card-grid {{ display: grid; grid-template-columns: repeat(var(--columns), minmax(0, var(--card-width, 1fr))); justify-content: center; align-content: start; gap: 8px 4px; }}
    .sideboard {{ --columns: 2 !important; }}
    .card {{ position: relative; width: 100%; min-width: 0; aspect-ratio: 94 / 128; overflow: visible; border: 0; border-radius: 4px; box-shadow: 3px 4px 2px rgba(0,0,0,.45); background: linear-gradient(#f1f1f1, #e6e6e6); }}
    .card:hover {{ z-index: 2; transform: translateY(-3px); }}
    .card img {{ display: block; width: 100%; height: 100%; object-fit: cover; border-radius: 0; }}
    .copies {{ position: absolute; right: 0; top: 0; display: grid; place-items: center; min-width: 25px; height: 23px; padding: 0 4px; background: #fff; color: var(--ink); font: 700 14px/1 var(--font-family-helvetica-neue), sans-serif; }}
    @media (max-width: 600px) {{ .prova-decklist-1 {{ min-height: 100vh; }} .header-content {{ padding-left: 22px; padding-right: 22px; }} .header-title {{ font-size: clamp(28px, 5.6vw, 43px); }} .header-event {{ left: 122px; max-width: 210px; font-size: 11px; }} .header-logo {{ left: 22px; width: 88px; }} .header-stats {{ left: 22px; right: 22px; }} .body-2 {{ gap: 10px; padding-left: 22px; padding-right: 22px; }} .deck-stat + .deck-stat {{ padding-left: 12px; }} .type-summary {{ gap: 8px; }} }}
  </style>
</head>
<body>
  <main class="prova-decklist-1">
    <header class="header-74">
      <img class="header-thumb" src="{thumbnail}" alt="">
      <div class="header-content">
        <img class="header-logo" src="{logo}" alt="Lega Pauper Cosenza">
        <h1 class="header-title">{safe_title}</h1>
        <p class="header-author">{safe_author}</p>
        <p class="header-event">{safe_event}</p>
      </div>
            <div class="header-stats">
                {render_stat("Main Deck", main_deck, output)}
                {render_stat("Sideboard", sideboard, output) if sideboard else ""}
            </div>
    </header>
    <div class="body-2">
            {render_section("Main Deck", main_deck, output, columns)}
            {render_section("Sideboard", sideboard, output, 2) if sideboard else ""}
    </div>
  </main>
</body>
<script>
    (() => {{
        const canvas = document.querySelector('.prova-decklist-1');
        const baseWidth = 768;
        const baseHeight = 1024;
        const exportScale = 1.40625;
        const resizeCanvas = () => {{
            const scale = Math.min(exportScale, window.innerWidth / baseWidth);
            canvas.style.setProperty('--canvas-scale', scale);
            document.body.style.width = `${{baseWidth * scale}}px`;
            document.body.style.height = `${{baseHeight * scale}}px`;
        }};
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
    }})();
</script>
</html>
'''
    output.write_text(page, encoding="utf-8")


def export_image(page_path: Path, image_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Image export requires Playwright. Install it with "
            "python -m pip install playwright and python -m playwright install chromium."
        ) from error

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1440}, device_scale_factor=1)
        page.goto(page_path.resolve().as_uri(), wait_until="networkidle")
        page.screenshot(path=str(image_path), full_page=False)
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Figma-style MTG decklist page.")
    parser.add_argument("decklist", type=Path, nargs="?", default=ROOT / "decklist.txt")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("-c", "--columns", type=int, default=5)
    parser.add_argument("--author", help="Override the pilot from the decklist About section")
    parser.add_argument("--event", help="Override the event from the decklist About section")
    parser.add_argument("--title", help="Override the deck title")
    parser.add_argument(
        "--export-image",
        nargs="?",
        const="auto",
        metavar="PNG",
        help="Also export the page as a 1080x1440 PNG",
        default="./decklist_new.png",
    )
    args = parser.parse_args()
    if args.columns < 1:
        parser.error("--columns must be at least 1")

    main_entries, side_entries, deck_name = parse_decklist(args.decklist)
    settings = parse_decklist_settings(args.decklist)
    title = args.title or settings.get("name") or deck_name or "MTG deck"
    author = args.author or settings.get("pilot") or settings.get("author") or "Giovanni Mancini"
    event = args.event or settings.get("event") or "1° Tappa - Autumn Season 1 | Lega Pauper Cosenza"
    session = requests.Session()
    session.headers["User-Agent"] = "mtg-decklist-web/1.0 (personal use)"
    main_cards = load_cards(main_entries, session)
    side_cards = load_cards(side_entries, session)
    write_page(main_cards, side_cards, title, author, event, args.output, args.columns)
    if args.export_image:
        image_output = (
            args.output.with_suffix(".png")
            if args.export_image == "auto"
            else Path(args.export_image)
        )
        export_image(args.output, image_output)
        print(f"Saved {image_output} (1080x1440)")
    print(f"Saved {args.output} ({len(main_cards)} main entries, {len(side_cards)} sideboard entries)")


if __name__ == "__main__":
    main()
