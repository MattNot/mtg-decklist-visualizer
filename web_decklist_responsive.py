from __future__ import annotations

import argparse
import html
from pathlib import Path

import requests

from deck_piles import fetch_card_art, parse_decklist, parse_decklist_settings
from web_decklist import (
  DIN_FONT,
  HELVETICA_FONT,
    IMAGE_DIR,
    ROOT,
    export_image,
    choose_columns,
    load_cards,
  relative_asset,
    render_section,
    render_stat,
)

DEFAULT_RESPONSIVE_OUTPUT = ROOT / "figma-export" / "figma-export" / "responsive-decklist.html"
EXPORT_PRESETS = {
  "1": ("Portrait 4:5", 1080, 1350),
  "2": ("Portrait 3:4", 1080, 1440),
  "3": ("Square 1:1", 1080, 1080),
  "4": ("Landscape 1.91:1", 1080, 566),
  "5": ("Reels & Stories 9:16", 1080, 1920),
}


def choose_export_dimensions() -> tuple[int, int]:
  print("Choose an export format (press Enter for Portrait 3:4):")
  for key, (name, width, height) in EXPORT_PRESETS.items():
    recommended = " (recommended)" if key == "2" else ""
    print(f"  {key}. {name}: {width}x{height}{recommended}")
  choice = input("Format [2]: ").strip() or "2"
  if choice not in EXPORT_PRESETS:
    raise ValueError("invalid export format")
  _, width, height = EXPORT_PRESETS[choice]
  return width, height


def write_responsive_page(
    main_deck: list[dict[str, object]],
    sideboard: list[dict[str, object]],
    title: str,
    author: str,
    event: str,
    output: Path,
    columns: int,
    thumbnail_path: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    logo = html.escape(relative_asset(IMAGE_DIR / "logo-lpc-letter-white.png", output), quote=True)
    thumbnail = html.escape(relative_asset(thumbnail_path, output), quote=True)
    din_font = html.escape(relative_asset(DIN_FONT, output), quote=True)
    helvetica_font = html.escape(relative_asset(HELVETICA_FONT, output), quote=True)
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
    :root {{
      --columns: {columns};
      --brick: #a43f38;
      --ink: #7e332d;
      --font-family-helvetica-neue: "Helvetica Neue", sans-serif;
      --font-family-din-condensed: "DIN Condensed", sans-serif;
      --type-scale: 1.12;
    }}
    @font-face {{ font-family: "Helvetica Neue"; src: url("{helvetica_font}") format("truetype"); font-weight: 100 900; }}
    @font-face {{ font-family: "DIN Condensed"; src: url("{din_font}") format("truetype"); font-weight: 700; }}
    * {{ box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; margin: 0; overflow: hidden; }}
    body {{ font-family: var(--font-family-helvetica-neue); background: #f8f7f7; }}
    .prova-decklist-1 {{ width: 100vw; height: 100vh; display: grid; grid-template-rows: minmax(180px, 29%) minmax(0, 71%); background: #f8f7f7; color: white; }}
    .header-74 {{ position: relative; min-height: 0; overflow: hidden; background: var(--brick); }}
    .header-74::after {{ content: ""; position: absolute; inset: auto 0 0; height: 28%; background: linear-gradient(to right, rgba(91, 31, 28, .4) 0 67.8%, rgba(49, 22, 21, .62) 67.8% 100%); pointer-events: none; }}
    .header-content {{ position: relative; z-index: 1; height: 72%; padding: clamp(20px, 3vw, 42px) clamp(20px, 3.2vw, 48px) 0; display: flex; flex-direction: column; }}
    .header-thumb {{ position: absolute; z-index: 0; right: 0; top: 0; width: 32.2%; height: 72%; object-fit: cover; object-position: 62% center; clip-path: polygon(21% 0, 100% 0, 100% 100%, 0 100%); }}
    .header-title {{ max-width: 62%; margin: 0; font-family: var(--font-family-din-condensed), Impact, sans-serif; font-size: calc(76px * var(--type-scale)); line-height: .9; letter-spacing: .02em; white-space: normal; overflow-wrap: anywhere; color: #fff; text-shadow: 0 2px 0 rgba(0,0,0,.18); }}
    .header-author {{ max-width: 62%; margin: .35em 0 0; font-size: calc(32px * var(--type-scale)); line-height: 1.1; font-weight: 700; overflow-wrap: anywhere; color: #fff; text-shadow: 0 2px 0 rgba(0,0,0,.12); }}
    .header-bottom {{ margin-top: auto; margin-bottom: calc(6px * var(--type-scale)); display: flex; align-items: center; gap: calc(16px * var(--type-scale)); }}
    .header-event {{ max-width: 40%; margin: 0; font-size: calc(20px * var(--type-scale)); line-height: 1.15; font-weight: 700; color: #fff; text-shadow: 0 2px 0 rgba(0,0,0,.12); }}
    .header-logo {{ flex-shrink: 0; width: min(calc(160px * var(--type-scale)), 13vh); height: auto; }}
    .header-stats {{ position: absolute; z-index: 2; left: clamp(20px, 3.2vw, 48px); right: clamp(20px, 3.2vw, 48px); bottom: 0; display: grid; grid-template-columns: 5fr 2fr; height: 28%; }}
    .deck-stat {{ padding-top: clamp(8px, 1.2vw, 18px); }}
    .stat-label {{ margin-bottom: .5em; font: 700 calc(20px * var(--type-scale))/1.1 var(--font-family-helvetica-neue), sans-serif; }}
    .type-summary {{ display: flex; flex-wrap: wrap; gap: clamp(6px, 1vw, 15px); align-items: center; }}
    .type-count {{ display: inline-flex; align-items: center; gap: .3em; font-size: calc(23px * var(--type-scale)); }}
    .type-count img {{ width: calc(31px * var(--type-scale)); height: calc(31px * var(--type-scale)); object-fit: contain; }}
    .body-2 {{ min-height: 0; display: grid; grid-template-columns: minmax(0, 5fr) minmax(170px, 2fr); gap: clamp(8px, 1.5vw, 24px); padding: clamp(10px, 1.8vw, 28px) clamp(20px, 3.2vw, 48px) 0; background: linear-gradient(rgba(248, 247, 247, .3), rgba(248, 247, 247, .3)) 0 0 / auto no-repeat, url("{thumbnail}") center / cover no-repeat; background-color: #f8f7f7; }}
    .card-panel {{ min-width: 0; min-height: 0; align-self: stretch; padding: clamp(8px, 1vw, 16px); border-radius: 3px; }}
    .main-deck {{ background: rgba(164, 63, 56, .08); }}
    .sideboard {{ background: rgba(90, 90, 90, .08); --columns: 2; }}
    .card-grid {{ display: grid; grid-template-columns: repeat(var(--columns), minmax(0, var(--card-width, 1fr))); justify-content: space-between; align-content: start; height: 100%; gap: clamp(4px, .6vw, 10px); }}
    .card {{ position: relative; width: 100%; min-width: 0; aspect-ratio: 63 / 88; overflow: visible; border-radius: 4px; box-shadow: 3px 4px 2px rgba(0,0,0,.45); background: #e6e6e6; }}
    .card img {{ display: block; width: 100%; height: 100%; object-fit: contain; border-radius: 0; }}
    .copies {{ position: absolute; right: 0; top: 0; display: grid; place-items: center; min-width: calc(35px * var(--type-scale)); height: calc(32px * var(--type-scale)); padding: 0 calc(6px * var(--type-scale)); background: #fff; color: var(--ink); font: 700 calc(20px * var(--type-scale))/1 var(--font-family-helvetica-neue), sans-serif; }}
    @media (max-aspect-ratio: 4/5) {{
      .prova-decklist-1 {{ grid-template-rows: minmax(180px, 25%) minmax(0, 75%); }}
      .body-2 {{ grid-template-columns: 1fr; grid-template-rows: minmax(0, 3fr) minmax(120px, 1fr); overflow: hidden; }}
      .header-title {{ max-width: calc(100% - 160px); font-size: calc(64px * var(--type-scale)); }}
      .header-author {{ max-width: 100%; font-size: calc(27px * var(--type-scale)); }}
    }}
    @media (max-aspect-ratio: 1/2) {{
      .header-title {{ max-width: calc(100% - 140px); font-size: calc(58px * var(--type-scale)); }}
      .header-author {{ max-width: 100%; font-size: calc(25px * var(--type-scale)); }}
      .header-event {{ max-width: 42%; }}
      .header-thumb {{ width: 38%; }}
      .header-stats {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (min-aspect-ratio: 4/5) and (max-aspect-ratio: 4/3) {{
      .header-content {{ padding-top: clamp(16px, 2.4vw, 30px); }}
      .header-title {{ font-size: calc(64px * var(--type-scale)); line-height: .85; }}
      .header-author {{ margin: .25em 0 0; font-size: calc(27px * var(--type-scale)); }}
      .header-bottom {{ margin-bottom: calc(4px * var(--type-scale)); }}
      .header-logo {{ width: min(calc(150px * var(--type-scale)), 13vh); }}
    }}
  </style>
</head>
<body>
  <main class="prova-decklist-1">
    <header class="header-74">
      <img class="header-thumb" src="{thumbnail}" alt="">
      <div class="header-content">
        <h1 class="header-title">{safe_title}</h1>
        <h3 class="header-author">{safe_author}</h3>
        <div class="header-bottom">
          <img class="header-logo" src="{logo}" alt="Lega Pauper Cosenza">
          <p class="header-event">{safe_event}</p>
        </div>
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
  <script>
    (() => {{
      const fitCards = () => {{
        const typeScale = Math.max(1.12, Math.min(window.innerWidth / 1080, window.innerHeight / 1440));
        document.documentElement.style.setProperty('--type-scale', typeScale);
        document.querySelectorAll('.card-panel').forEach((panel) => {{
          const grid = panel.querySelector('.card-grid');
          const cards = grid ? grid.querySelectorAll('.card').length : 0;
          const columns = Number.parseInt(getComputedStyle(panel).getPropertyValue('--columns'), 10);
          if (!grid || !cards || !columns) return;
          const styles = getComputedStyle(grid);
          const columnGap = parseFloat(styles.columnGap) || 0;
          const rowGap = parseFloat(styles.rowGap) || 0;
          const isSideboard = panel.classList.contains('sideboard');
          let bestColumns = isSideboard ? 2 : columns;
          let bestCardWidth = 0;
          const maxColumns = Math.min(cards, 12);
          for (let candidate = 1; candidate <= maxColumns; candidate += 1) {{
            const rows = Math.ceil(cards / candidate);
            const widthByColumns = (grid.clientWidth - columnGap * (candidate - 1)) / candidate;
            const widthByRows = ((grid.clientHeight - rowGap * (rows - 1)) / rows) * 63 / 88;
            const cardWidth = Math.min(widthByColumns, widthByRows);
            if (cardWidth > bestCardWidth) {{
              bestCardWidth = cardWidth;
              bestColumns = candidate;
            }}
          }}
          grid.style.setProperty('--columns', bestColumns);
          grid.style.setProperty('--card-width', `${{Math.max(0, bestCardWidth)}}px`);
        }});
      }};
      fitCards();
      window.addEventListener('resize', fitCards);
      window.addEventListener('load', fitCards);
    }})();
  </script>
</body>
</html>
'''
    output.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a responsive MTG decklist page.")
    parser.add_argument("decklist", type=Path, nargs="?", default=ROOT / "decklist.txt")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_RESPONSIVE_OUTPUT)
    parser.add_argument("-c", "--columns", default="5")
    parser.add_argument("--author")
    parser.add_argument("--event")
    parser.add_argument("--title")
    parser.add_argument("--export-width", type=int)
    parser.add_argument("--export-height", type=int)
    parser.add_argument("--export-image", nargs="?", const="auto", metavar="PNG", default="./responsive-decklist.png")
    args = parser.parse_args()
    if (args.export_width is None) != (args.export_height is None):
      parser.error("--export-width and --export-height must be provided together")
    if args.export_width is None:
      try:
        args.export_width, args.export_height = choose_export_dimensions()
      except (EOFError, ValueError):
        parser.error("invalid export format; choose a number from 1 to 5")
    if args.export_width < 1 or args.export_height < 1:
        parser.error("export dimensions must be positive")
    main_entries, side_entries, deck_name = parse_decklist(args.decklist)
    if args.columns.lower() == "auto":
      columns = choose_columns(len(main_entries))
    else:
      try:
        columns = int(args.columns)
      except ValueError:
        parser.error("--columns must be a positive integer or 'auto'")
      if columns < 1:
        parser.error("--columns must be a positive integer or 'auto'")
    settings = parse_decklist_settings(args.decklist)
    title = args.title or settings.get("name") or deck_name or "MTG deck"
    author = args.author or settings.get("pilot") or settings.get("author") or "Giovanni Mancini"
    event = args.event or settings.get("event") or "1° Tappa - Autumn Season 1 | Lega Pauper Cosenza"
    session = requests.Session()
    session.headers["User-Agent"] = "mtg-decklist-responsive/1.0 (personal use)"
    thumbnail_path = IMAGE_DIR / "thumbnail.png"
    if settings.get("thumbnail"):
        thumbnail_path.write_bytes(fetch_card_art(settings["thumbnail"], session).read_bytes())
    main_cards = load_cards(main_entries, session)
    side_cards = load_cards(side_entries, session)
    write_responsive_page(
        main_cards,
        side_cards,
        title,
        author,
        event,
        args.output,
        columns,
        thumbnail_path,
    )
    if args.export_image:
        image_output = args.output.with_suffix(".png") if args.export_image == "auto" else Path(args.export_image)
        export_image(args.output, image_output, args.export_width, args.export_height)
        print(f"Saved {image_output} ({args.export_width}x{args.export_height})")
    print(f"Saved {args.output} ({len(main_cards)} main entries, {len(side_cards)} sideboard entries)")


if __name__ == "__main__":
    main()
