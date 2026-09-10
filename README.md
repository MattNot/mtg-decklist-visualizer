# MTG Deck Piles

Generate a shareable image of a Magic: The Gathering decklist. The renderer downloads card images from Scryfall, groups duplicate cards, separates the main deck and sideboard, sorts cards by type, and adds color and type summaries to the header. The layout adapts to the selected number of columns.

## Requirements

- Python 3.10 or newer
- Internet access for cards not already in the local cache

## Setup

Create and activate a virtual environment, then install dependencies:

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Decklist format

Use one card per line. Quantities are optional. An optional `About` section can define the deck name, pilot, event, and header artwork with `Name`, `Pilot`, `Event`, and `Thumbnail`. `Thumbnail` is a card name: the web generator downloads its Scryfall `art_crop` image and caches it locally. `Author` is accepted as an alias for `Pilot`. Sideboard headers can be written as `SIDEBOARD:`, `sideboard`, `# Sideboard`, or `#SIDEBOARD`.

```text
About
Name Mono-Blue Terror
Pilot Mario Rossi
Event 1° Tappa - Autumn Season 1 | Lega Pauper Cosenza
Thumbnail Mountain

Deck
4 Lightning Bolt
4 Monastery Swiftspear
4 Mountain

SIDEBOARD:
2 Spell Pierce
1 Tormod's Crypt
```

## Generate an image

```powershell
python deck_piles.py decklist.txt -b background.png -c 6
```

If `-b` is omitted, `background.png` is used. When the decklist contains `Name Mono-Blue Terror`, the default output is `Mono-Blue-Terror.png`. Use `-o` to choose a different filename.

Options:

- `-b, --background`: background image, default `background.png`
- `-o, --output`: output PNG path, default derived from the deck name
- `-c, --columns`: main-deck columns, default `5`; columns expand to fill the space before the sideboard
- `--title`: override the title from the `About` section
- `--quiet`: show only the final result

Cards are sorted left-to-right by type: creatures, sorceries, instants, artifacts, other types, then lands. Duplicate entries are shown once with a quantity badge. When columns overlap horizontally, the badge moves to the bottom-left of the card to remain visible. Card images and Scryfall metadata are cached in `.card_cache`; a failed lookup is retried three times and causes the render to fail rather than producing an incomplete image.

The `mana_symbols/` and `card_type_symbols/` PNG assets are included in the repository and are used in the generated header. The generated image uses a `1080x1440` vertical layout for social media posts. Use `make_background_skeleton.py` to generate a layout guide for designing a custom background.

## Generate the web page

The Figma-style page reuses the same parser, Scryfall cache, card sorting, and quantity handling as the image renderer. The generated header reads `Name`, `Pilot`, `Event`, and `Thumbnail` from the `About` section. When `Thumbnail` is present, the generator lists all Scryfall printings with artwork and asks which one to use; the selected `art_crop` image is downloaded only if it is not already cached. The command-line options `--title`, `--author`, and `--event` override the corresponding values from the decklist.

```powershell
python web_decklist.py decklist.txt
```

This updates `figma-export/figma-export/prova-decklist.html`. Open that file in a browser to view the generated page. Use `--author`, `--event`, `--title`, or `-o` to customize the page metadata and output location. Use `--columns auto` to calculate the column count that produces the largest proportional cards for the current deck.

To export the same page as a `1080x1440` PNG, install the browser runtime once and use:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python web_decklist.py decklist.txt --export-image
```

The PNG is written next to the HTML output, unless a path is supplied after `--export-image`.

### Font selection

The script discovers a system sans-serif font automatically. To use a specific `.ttf` or `.otf` file, set `MTG_FONT_PATH` before running it:

```powershell
$env:MTG_FONT_PATH = "C:\Fonts\MyFont.ttf"
python deck_piles.py decklist.txt
```
