#!/usr/bin/env python3
"""
Magi Nation Card PDF Generator

Downloads full card images (with frames, text, art) from the jokerduel/magination
GitHub Pages site and generates a printable PDF with cards in a 3x3 grid.

Usage:
    python magi_nation_print.py cards.txt [-o output.pdf] [--rebuild-index]

Input file format (one card per line, optional quantity, set, and region):
    # Comments are ignored
    3 Brannix
    2 Flutter Yup
    Drush [PR]              # specific set (promo)
    Drush [DE]              # Dream's End version
    Ember Vard (Cald)       # specific region
    Ember Vard (Arderial)   # different region
    Aerial Flist [ND] (Paradwyn)  # set + region
    Alaban
"""

import argparse
import base64
import html
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path

import requests
from fpdf import FPDF
from PIL import Image

# --- Constants ---
IMAGE_BASE_URL = "https://jokerduel.github.io/magination/cardimages"
GITHUB_API_BASE = "https://api.github.com/repos/jokerduel/magination/contents"
INDEX_PATH = Path.home() / ".magi_nation_card_index.json"
CACHE_DIR = Path(tempfile.gettempdir()) / "magi_nation_cards"

# Sets to scrape from the magination repo (set_code -> index filename prefix)
SETS = {
    "AW": "Awakening",
    "BS": "Base Set",
    "DE": "Dream's End",
    "ND": "Nightmare's Dawn",
    "PR": "Promos",
    "TR": "Traitor's Reach",
    "UL": "Universal",
    "VS": "Voice of the Storms",
    "DD4": "Demo Deck (Core)",
}

# Map set codes to their index HTML filenames
SET_INDEX_FILES = {
    "AW": "AW_index.html",
    "BS": "BS_index.html",
    "DE": "DE_index.html",
    "ND": "ND_index.html",
    "PR": "PR_index.html",
    "TR": "TR_index.html",
    "UL": "UL_index.html",
    "VS": "VS_index.html",
    "DD4": "DemoDeck4_index.html",
}

# PDF layout (inches)
PAGE_W, PAGE_H = 8.5, 11.0
CARD_W, CARD_H = 2.5, 3.5
COLS, ROWS = 3, 3
MARGIN_X = (PAGE_W - COLS * CARD_W) / 2   # ~0.5"
MARGIN_Y = (PAGE_H - ROWS * CARD_H) / 2   # ~0.25"


def normalize(name: str) -> str:
    """Normalize a card name for fuzzy matching."""
    return re.sub(r"[_\s\-'\".,\u2018\u2019\u201C\u201D]+", "", name.lower())


def _clean_html_text(text: str) -> str:
    """Strip HTML tags and decode HTML entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_index_html(html: str) -> list[tuple[str, str, str]]:
    """Extract (image_filename, card_display_name, region) tuples from an index HTML page.

    Handles two HTML layouts:
    1. Table rows (<TR>) with 3 <TD> cells: card link, region, type  (most sets)
    2. Flat link lists inside a single <td>  (DD4 demo decks)
    """
    results = []
    found_images = set()

    # --- Pass 1: table-row format (most sets) ---
    rows = re.split(r"<TR[^>]*>", html, flags=re.IGNORECASE)
    for row in rows:
        link_match = re.search(
            r'href="cardimages/([^"]+\.jpg)"[^>]*>'
            r'(?:<font[^>]*>)?\s*(.+?)\s*(?:</font>)?\s*</[Aa]>',
            row, re.IGNORECASE | re.DOTALL,
        )
        if not link_match:
            continue
        image_file = link_match.group(1)
        name = _clean_html_text(link_match.group(2))

        # Extract region from the second <TD> in this row
        region = ""
        tds = re.findall(r"<TD[^>]*>(.*?)</TD>", row, re.IGNORECASE | re.DOTALL)
        if len(tds) >= 2:
            region = _clean_html_text(tds[1])

        results.append((image_file, name, region))
        found_images.add(image_file)

    # --- Pass 2: catch any remaining cardimages links not in table rows (DD4, etc.) ---
    for m in re.finditer(
        r'href="cardimages/([^"]+\.jpg)"[^>]*>'
        r'(?:<font[^>]*>)?\s*(.+?)\s*(?:</font>)?\s*</[Aa]>',
        html, re.IGNORECASE | re.DOTALL,
    ):
        image_file = m.group(1)
        if image_file in found_images:
            continue
        name = _clean_html_text(m.group(2))
        results.append((image_file, name, ""))
        found_images.add(image_file)

    return results


def build_index(rebuild: bool = False) -> dict:
    """Build or load the card index by scraping the magination repo's HTML index pages.

    Returns a dict:
        "cards": {normalized_name: [{"url", "image", "display", "set", "region"}, ...]}
        "all_names": [list of all normalized names]
    """
    if not rebuild and INDEX_PATH.exists():
        with open(INDEX_PATH) as f:
            return json.load(f)

    print("Building card index from GitHub...", file=sys.stderr)
    cards = defaultdict(list)

    for set_code, index_file in SET_INDEX_FILES.items():
        url = f"{GITHUB_API_BASE}/{index_file}"
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"  Warning: could not fetch {set_code} index (HTTP {resp.status_code})",
                  file=sys.stderr)
            continue

        html = base64.b64decode(resp.json()["content"]).decode("utf-8")
        entries = _parse_index_html(html)

        for image_file, display_name, region in entries:
            norm = normalize(display_name)
            image_url = f"{IMAGE_BASE_URL}/{image_file}"
            cards[norm].append({
                "url": image_url,
                "image": image_file,
                "display": display_name,
                "set": set_code,
                "region": region,
            })

        set_count = sum(1 for v in cards.values() for e in v if e["set"] == set_code)
        print(f"  {set_code} ({SETS[set_code]}): {set_count} cards", file=sys.stderr)

    index = {"cards": dict(cards), "all_names": list(cards.keys())}
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)

    total = sum(len(v) for v in cards.values())
    unique = len(cards)
    print(f"Index saved to {INDEX_PATH} ({unique} unique names, {total} printings)",
          file=sys.stderr)
    return index


def parse_input(filepath: str) -> list[tuple[int, str, str | None, str | None]]:
    """Parse input file. Returns list of (quantity, card_name, set_or_None, region_or_None)."""
    entries = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Strip inline comments: anything after # preceded by whitespace
            line = re.sub(r"\s+#.*$", "", line).strip()

            # Extract optional (Region) suffix
            region_match = re.search(r"\(([^)]+)\)\s*$", line)
            region_filter = None
            if region_match:
                region_filter = region_match.group(1).strip()
                line = line[:region_match.start()].strip()

            # Extract optional [SET] suffix
            set_match = re.search(r"\[(\w+)\]\s*$", line)
            set_filter = None
            if set_match:
                set_filter = set_match.group(1).upper()
                line = line[:set_match.start()].strip()

            # Extract optional quantity prefix
            qty_match = re.match(r"^(\d+)\s+(.+)$", line)
            if qty_match:
                qty, name = int(qty_match.group(1)), qty_match.group(2).strip()
            else:
                qty, name = 1, line

            entries.append((qty, name, set_filter, region_filter))
    return entries


def _normalize_region(region: str) -> str:
    """Normalize a region name for comparison."""
    return re.sub(r"['\s]+", "", region.lower())


def resolve_cards(entries: list[tuple[int, str, str | None, str | None]],
                  index: dict) -> list[dict]:
    """Resolve card names to image URLs. Returns flat list of card dicts (one per copy)."""
    cards_db = index["cards"]
    all_names = index["all_names"]
    resolved = []
    errors = []

    for qty, name, set_filter, region_filter in entries:
        norm = normalize(name)

        if norm in cards_db:
            versions = cards_db[norm]

            # Apply set filter
            if set_filter:
                filtered = [v for v in versions if v["set"] == set_filter]
                if not filtered:
                    available = ", ".join(sorted(set(v["set"] for v in versions)))
                    errors.append((
                        name,
                        [f"No [{set_filter}] version; available sets: {available}"],
                    ))
                    continue
                versions = filtered

            # Apply region filter
            if region_filter:
                norm_region = _normalize_region(region_filter)
                filtered = [v for v in versions
                            if _normalize_region(v.get("region", "")) == norm_region]
                if not filtered:
                    available = ", ".join(sorted(set(
                        v.get("region", "?") for v in versions)))
                    label = f" [{set_filter}]" if set_filter else ""
                    errors.append((
                        name,
                        [f"No ({region_filter}) region{label}; "
                         f"available regions: {available}"],
                    ))
                    continue
                versions = filtered

            chosen = versions[0]
            for _ in range(qty):
                resolved.append(chosen)
        else:
            # Fuzzy matching
            close = get_close_matches(norm, all_names, n=3, cutoff=0.6)
            suggestions = []
            for c in close:
                entry = cards_db[c][0]
                sets = ", ".join(sorted(set(v["set"] for v in cards_db[c])))
                suggestions.append(f"{entry['display']} [{sets}]")
            errors.append((name, suggestions))

    if errors:
        print("\nUnmatched cards:", file=sys.stderr)
        for name, suggestions in errors:
            msg = f'  - "{name}"'
            if suggestions:
                msg += f"  (did you mean: {'; '.join(suggestions)}?)"
            print(msg, file=sys.stderr)
        print(file=sys.stderr)

    return resolved


def download_image(card: dict) -> str | None:
    """Download a card image and return the local file path. Uses cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_path = CACHE_DIR / card["image"]

    if local_path.exists():
        return str(local_path)

    try:
        resp = requests.get(card["url"], timeout=30)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
        # Validate it's a real image
        Image.open(local_path).verify()
        return str(local_path)
    except Exception as e:
        print(f"  Error downloading {card['display']}: {e}", file=sys.stderr)
        if local_path.exists():
            local_path.unlink()
        return None


def trim_black_border(img_path: str) -> str:
    """Crop black borders from a card image, returning path to the trimmed version.

    Detects rows/columns of near-black pixels at the edges and removes them.
    If no significant border is found, returns the original path unchanged.
    """
    trimmed_path = img_path.rsplit(".", 1)[0] + "_trimmed.jpg"
    if os.path.exists(trimmed_path):
        return trimmed_path

    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    pixels = img.load()
    threshold = 30  # average RGB below this is considered "black"

    def is_dark_row(row):
        total = sum(pixels[col, row][0] + pixels[col, row][1] + pixels[col, row][2]
                     for col in range(w))
        return (total / w / 3) < threshold

    def is_dark_col(col):
        total = sum(pixels[col, row][0] + pixels[col, row][1] + pixels[col, row][2]
                     for row in range(h))
        return (total / h / 3) < threshold

    top = 0
    while top < h and is_dark_row(top):
        top += 1

    bottom = h
    while bottom > top and is_dark_row(bottom - 1):
        bottom -= 1

    left = 0
    while left < w and is_dark_col(left):
        left += 1

    right = w
    while right > left and is_dark_col(right - 1):
        right -= 1

    # Only crop if border is significant (> 2% of dimension on any side)
    border_top = top
    border_bottom = h - bottom
    border_left = left
    border_right = w - right
    border_pct = max(border_top / h, border_bottom / h, border_left / w, border_right / w)
    if border_pct < 0.02:
        return img_path

    # Keep half the detected border for a clean black edge
    keep = 0.5
    crop_left = int(border_left * (1 - keep))
    crop_top = int(border_top * (1 - keep))
    crop_right = w - int(border_right * (1 - keep))
    crop_bottom = h - int(border_bottom * (1 - keep))

    cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))
    cropped.save(trimmed_path, "JPEG", quality=95)
    return trimmed_path


def draw_cut_lines(pdf):
    """Draw dashed cut lines along the card grid boundaries."""
    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.01)
    pdf.set_dash_pattern(dash=0.1, gap=0.05)

    # Vertical lines (COLS + 1 lines)
    for col in range(COLS + 1):
        x = MARGIN_X + col * CARD_W
        pdf.line(x, 0, x, PAGE_H)

    # Horizontal lines (ROWS + 1 lines)
    for row in range(ROWS + 1):
        y = MARGIN_Y + row * CARD_H
        pdf.line(0, y, PAGE_W, y)

    pdf.set_dash_pattern()


def generate_pdf(cards: list[dict], output_path: str):
    """Generate a PDF with cards in a 3x3 grid layout."""
    pdf = FPDF(unit="in", format="letter")
    pdf.set_auto_page_break(False)

    total = len(cards)
    print(f"Generating PDF with {total} card(s)...", file=sys.stderr)

    i = 0
    while i < total:
        pdf.add_page()
        draw_cut_lines(pdf)
        for slot in range(COLS * ROWS):
            if i >= total:
                break
            card = cards[i]
            img_path = download_image(card)
            if img_path is None:
                print(f"  Skipping {card['display']} (download failed)", file=sys.stderr)
                i += 1
                continue

            img_path = trim_black_border(img_path)

            row, col = divmod(slot, COLS)
            x = MARGIN_X + col * CARD_W
            y = MARGIN_Y + row * CARD_H
            pdf.image(img_path, x=x, y=y, w=CARD_W, h=CARD_H)
            i += 1

    pdf.output(output_path)
    print(f"PDF saved to {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a printable PDF of Magi Nation cards.",
        epilog=(
            "Set codes: AW (Awakening), BS (Base Set), DE (Dream's End), "
            "ND (Nightmare's Dawn), PR (Promos), TR (Traitor's Reach), "
            "UL (Universal), VS (Voice of the Storms), DD4 (Demo Deck). "
            "Regions: Arderial, Bograth, Cald, Core, d'Resh, Kybar's Teeth, "
            "Nar, Naroom, Orothe, Paradwyn, Underneath, Universal, Weave. "
            "PRINTING TIP: Cards are sized at 2.5\"x3.5\" (standard trading "
            "card size). When printing, select 'Actual Size' or set scale to "
            "100% in your print dialog. Using 'Fit to Page' will shrink the "
            "cards below their intended dimensions."
        ),
    )
    parser.add_argument("input", help="Text file with card names (one per line)")
    parser.add_argument("-o", "--output", default="magi_nation_cards.pdf",
                        help="Output PDF path (default: magi_nation_cards.pdf)")
    parser.add_argument("--rebuild-index", action="store_true",
                        help="Force rebuild the card index from GitHub")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Build/load the card index
    index = build_index(rebuild=args.rebuild_index)

    # Parse the input file
    entries = parse_input(args.input)
    if not entries:
        print("No cards found in input file.", file=sys.stderr)
        sys.exit(1)
    print(f"Parsed {sum(q for q, *_ in entries)} card(s) from {args.input}", file=sys.stderr)

    # Resolve card names to URLs
    cards = resolve_cards(entries, index)
    if not cards:
        print("No cards could be resolved. Check your input file.", file=sys.stderr)
        sys.exit(1)

    # Generate the PDF
    generate_pdf(cards, args.output)


if __name__ == "__main__":
    main()
