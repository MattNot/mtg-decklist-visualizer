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

Use one card per line. Quantities are optional. An optional `About` section can define the deck title with `Name`. Sideboard headers can be written as `SIDEBOARD:`, `sideboard`, `# Sideboard`, or `#SIDEBOARD`.

```text
About
Name Mono-Blue Terror

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
- `-c, --columns`: main-deck columns, default `6`; columns expand to fill the space before the sideboard
- `--title`: override the title from the `About` section
- `--quiet`: show only the final result

Cards are sorted left-to-right by type: creatures, sorceries, instants, artifacts, other types, then lands. Duplicate entries are shown once with a quantity badge. When columns overlap horizontally, the badge moves to the bottom-left of the card to remain visible. Card images and Scryfall metadata are cached in `.card_cache`; a failed lookup is retried three times and causes the render to fail rather than producing an incomplete image.

The `mana_symbols/` and `card_type_symbols/` PNG assets are included in the repository and are used in the generated header. Use `make_background_skeleton.py` to generate a `1600x1400` layout guide for designing a custom background.
