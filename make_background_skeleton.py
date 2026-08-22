from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from deck_piles import (
    BOTTOM_MARGIN,
    CANVAS_H,
    CANVAS_W,
    CARD_H,
    CARD_HORIZONTAL_GAP,
    CARD_W,
    parse_decklist,
    panel_right,
)

BACKGROUND = (224, 228, 226)
HEADER = (18, 22, 22)
MAIN_FILL = (211, 232, 220)
SIDE_FILL = (229, 220, 240)
CARD_OUTLINE = (52, 75, 64)
TEXT = (25, 30, 28)
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
SMALL_FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
BOLD_FONT = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 25)


def draw_group(
    draw: ImageDraw.ImageDraw,
    entries: list[tuple[int, str]],
    left: int,
    top: int,
    bottom: int,
    columns: int,
    fill: tuple[int, int, int],
) -> None:
    column_count = max(1, min(columns, len(entries)))
    row_count = (len(entries) + column_count - 1) // column_count
    vertical_step = min(
        CARD_H + 12,
        (bottom - top - CARD_H) / max(1, row_count - 1),
    )
    for index, (quantity, name) in enumerate(entries):
        column = index % column_count
        row = index // column_count
        x = left + column * (CARD_W + CARD_HORIZONTAL_GAP)
        y = int(top + row * vertical_step)
        draw.rectangle((x, y, x + CARD_W, y + CARD_H), fill=fill, outline=CARD_OUTLINE, width=3)
        draw.text((x + 8, y + 8), f"CARD {index + 1}", font=SMALL_FONT, fill=TEXT)
        draw.text((x + 8, y + 32), name[:20], font=SMALL_FONT, fill=TEXT)
        draw.text((x + 8, y + CARD_H - 30), f"x{quantity}", font=SMALL_FONT, fill=TEXT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a layout skeleton for a custom MTG background.")
    parser.add_argument("decklist", type=Path, nargs="?", default=Path("decklist.txt"))
    parser.add_argument("-o", "--output", type=Path, default=Path("background-skeleton.png"))
    parser.add_argument("-c", "--columns", type=int, default=6)
    parser.add_argument("--title", help="Override the title read from the decklist")
    args = parser.parse_args()
    if args.columns < 1:
        parser.error("--columns must be at least 1")

    main_deck, sideboard, deck_name = parse_decklist(args.decklist)
    title = args.title or deck_name or "MTG deck"
    main_left = 60
    sideboard_left = 1190
    main_right = panel_right(main_left, main_deck, args.columns)
    sideboard_right = panel_right(sideboard_left, sideboard, 2)

    image = Image.new("RGB", (CANVAS_W, CANVAS_H), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((main_left, 35, 650, 98), fill=HEADER)
    draw.text((main_left + 15, 49), title, font=BOLD_FONT, fill=(255, 255, 255))
    draw.rectangle((main_left, 102, main_right, 155), fill=(255, 255, 255))
    draw.text((main_left + 15, 115), f"{sum(q for q, _ in main_deck)} cards", font=FONT, fill=TEXT)
    draw.rectangle((main_left, 162, main_right, 184), fill=(255, 255, 255))
    draw.text((main_left + 15, 163), "MAIN DECK", font=SMALL_FONT, fill=TEXT)
    draw.rectangle((sideboard_left, 102, sideboard_right, 184), fill=(255, 255, 255))
    draw.text((sideboard_left + 5, 108), "SIDEBOARD", font=FONT, fill=TEXT)
    draw.text((sideboard_left + 5, 140), f"{sum(q for q, _ in sideboard)} cards", font=SMALL_FONT, fill=TEXT)
    draw_group(draw, main_deck, main_left, 220, CANVAS_H - BOTTOM_MARGIN, args.columns, MAIN_FILL)
    draw_group(draw, sideboard, sideboard_left, 220, CANVAS_H - BOTTOM_MARGIN, 2, SIDE_FILL)
    draw.rectangle((35, CANVAS_H - 48, 540, CANVAS_H - 18), fill=(255, 255, 255))
    draw.text((48, CANVAS_H - 44), "CARD AREA: 180 x 251 px  |  gap: 6 px", font=SMALL_FONT, fill=TEXT)
    image.save(args.output)
    print(f"Saved {args.output} ({CANVAS_W}x{CANVAS_H})")


if __name__ == "__main__":
    main()
