# Magi-Nation Proxy Card Generator

A command-line tool that generates printable PDF sheets of Magi-Nation trading card proxies. It downloads card images from the [jokerduel/magination](https://jokerduel.github.io/magination/) archive and arranges them in a 3x3 grid on standard US Letter pages, ready to print and cut.

## Features

- **Full card images** with frames, text, and art sourced from the magination GitHub Pages archive
- **3x3 grid layout** on 8.5" x 11" pages at standard trading card size (2.5" x 3.5")
- **Dashed cut lines** for easy trimming
- **Automatic black border trimming** on card images
- **Fuzzy name matching** with suggestions for misspelled card names
- **Set and region filtering** to select specific printings of a card
- **Local caching** of downloaded images to avoid redundant downloads
- **Persistent card index** built from the magination repo, with option to rebuild

## Requirements

- Python 3.10+
- [fpdf2](https://pypi.org/project/fpdf2/)
- [Pillow](https://pypi.org/project/pillow/)
- [requests](https://pypi.org/project/requests/)

Install dependencies:

```bash
pip install fpdf2 Pillow requests
```

## Usage

```bash
python magi_nation_print.py <input_file> [-o <output.pdf>] [--rebuild-index]
```

### Arguments

| Argument | Description |
|---|---|
| `input` | Text file with card names (one per line) |
| `-o`, `--output` | Output PDF path (default: `magi_nation_cards.pdf`) |
| `--rebuild-index` | Force rebuild the card index from the magination GitHub repo |

### Examples

```bash
# Generate a PDF from a card list
python magi_nation_print.py my_deck.txt

# Specify an output filename
python magi_nation_print.py my_deck.txt -o my_deck_proxies.pdf

# Rebuild the card index (useful if new cards are added upstream)
python magi_nation_print.py my_deck.txt --rebuild-index
```

## Input File Format

Create a plain text file with one card per line. Lines starting with `#` are treated as comments. Inline comments (after `#`) are also supported.

```text
# My Naroom Deck
3 Leaf Hyren
2 Arboll
Pruitt
Sperri
```

### Specifying Quantity

Prefix a card name with a number to include multiple copies:

```text
3 Leaf Hyren    # adds 3 copies
Arboll           # adds 1 copy (default)
```

### Filtering by Set

Append a set code in square brackets to select a specific printing:

```text
Drush [PR]       # Promo version
Drush [DE]       # Dream's End version
```

### Filtering by Region

Append a region in parentheses to select a specific region's version:

```text
Ember Vard (Cald)       # Cald version
Ember Vard (Arderial)   # Arderial version
```

### Combining Set and Region Filters

```text
Aerial Flist [ND] (Paradwyn)   # Nightmare's Dawn, Paradwyn version
```

## Supported Sets

| Code | Set Name |
|---|---|
| `AW` | Awakening |
| `BS` | Base Set |
| `DE` | Dream's End |
| `ND` | Nightmare's Dawn |
| `PR` | Promos |
| `TR` | Traitor's Reach |
| `UL` | Universal |
| `VS` | Voice of the Storms |
| `DD4` | Demo Deck (Core) |

## Supported Regions

Arderial, Bograth, Cald, Core, d'Resh, Kybar's Teeth, Nar, Naroom, Orothe, Paradwyn, Underneath, Universal, Weave

## Printing Tips

- Cards are sized at **2.5" x 3.5"** (standard trading card size)
- When printing, select **"Actual Size"** or set scale to **100%** in your print dialog
- Using "Fit to Page" will shrink the cards below their intended dimensions
- Dashed cut lines are included on each page for easy trimming

## How It Works

1. **Index building** — On first run, the script scrapes the magination repo's HTML index pages via the GitHub API and builds a local card index (`~/.magi_nation_card_index.json`). Subsequent runs use the cached index unless `--rebuild-index` is passed.
2. **Name resolution** — Card names from the input file are normalized and matched against the index. If no exact match is found, fuzzy matching suggests close alternatives.
3. **Image download** — Card images are downloaded from the magination GitHub Pages site and cached in a temp directory to speed up future runs.
4. **Border trimming** — Black borders on card images are automatically detected and cropped for cleaner output.
5. **PDF generation** — Cards are laid out in a 3x3 grid on US Letter pages with dashed cut lines using fpdf2.
