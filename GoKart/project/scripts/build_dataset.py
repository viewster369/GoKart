"""
build_dataset.py
────────────────
Reads the Amazon Best Sellers CSV from the new ecommerce dataset,
normalises every product into GoKart's standard schema, balances
categories, and writes data/products_final.json.

Usage:
    python scripts/build_dataset.py
"""

import csv
import json
import os
import random
import re
import hashlib
import urllib.parse
from collections import defaultdict

# ── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

CSV_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "ecommerce-product-dataset-main",
    "data",
    "amazon_com",
    "best_sellers",
    "amazon_com_best_sellers_2025_01_27",
    "amazon_com_best_sellers_2025_01_27.csv",
)
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "products.json")

# ── Target categories ──────────────────────────────────────────────────────
MAX_PER_CATEGORY = 2000
STANDARD_CATEGORIES = ["Electronics", "Fashion", "Home", "Books", "Beauty", "Sports"]

# ── Category color themes (bg / fg) for SVG placeholders ──────────────────
CATEGORY_COLORS = {
    "Electronics": ("#1a1a2e", "#e94560"),
    "Fashion":     ("#2d132c", "#ee4c7c"),
    "Home":        ("#2d4059", "#ea5455"),
    "Books":       ("#3c1642", "#e94560"),
    "Beauty":      ("#6a097d", "#f5c7f7"),
    "Sports":      ("#0f3460", "#e94560"),
}

CATEGORY_ICONS = {
    "Electronics": "⚡",
    "Fashion":     "👗",
    "Home":        "🏠",
    "Books":       "📚",
    "Beauty":      "✨",
    "Sports":      "🏅",
}

# ── Amazon top-level category → GoKart category mapping ───────────────────
AMAZON_CAT_MAP: dict[str, str | None] = {
    # Electronics
    "Electronics":                  "Electronics",
    "Computers & Accessories":      "Electronics",
    "Cell Phones & Accessories":    "Electronics",
    "Camera & Photo Products":      "Electronics",
    "Video Games":                  "Electronics",
    "Software":                     "Electronics",
    "Musical Instruments":          "Electronics",  # close enough
    "Apps & Games":                 "Electronics",
    # Fashion
    "Clothing, Shoes & Jewelry":    "Fashion",
    # Home
    "Home & Kitchen":               "Home",
    "Kitchen & Dining":             "Home",
    "Tools & Home Improvement":     "Home",
    "Patio, Lawn & Garden":         "Home",
    "Industrial & Scientific":      "Home",
    "Office Products":              "Home",
    "Pet Supplies":                 "Home",
    # Books
    "Books":                        "Books",
    "Kindle Store":                 "Books",
    "Audible Books & Originals":    "Books",
    "CDs & Vinyl":                  "Books",   # media
    "Movies & TV":                  "Books",   # media
    # Beauty
    "Beauty & Personal Care":       "Beauty",
    "Health & Household":           "Beauty",
    "Baby":                         "Beauty",  # personal care adjacent
    # Sports
    "Sports & Outdoors":            "Sports",
    "Sports Collectibles":          "Sports",
    "Automotive":                   "Sports",  # active/outdoor adjacent
    # Ambiguous — use keyword sub-classification
    "Toys & Games":                 None,
    "Grocery & Gourmet Food":       None,
    "Arts, Crafts & Sewing":        None,
    "Unique Finds":                 None,
    "Handmade Products":            None,
    "Collectibles & Fine Art":      None,
}

# ── Keyword rules for ambiguous categories (first match wins) ─────────────
KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["sport", "fitness", "gym", "yoga", "cricket", "football", "basketball",
      "tennis", "running", "cycling", "swimming", "outdoor", "camping",
      "hiking", "trekking", "exercise", "athletic"], "Sports"),
    (["phone", "laptop", "tablet", "headphone", "speaker", "camera",
      "charger", "gadget", "electronic", "computer", "keyboard", "mouse",
      "usb", "bluetooth", "cable", "battery", "led", "monitor", "printer",
      "robot", "drone"], "Electronics"),
    (["cosmetic", "skincare", "makeup", "perfume", "shampoo", "cream",
      "lotion", "serum", "lipstick", "foundation", "moisturizer",
      "face wash", "nail", "hair", "vitamin", "supplement", "health",
      "essential oil"], "Beauty"),
    (["kitchen", "furniture", "home", "bedsheet", "curtain", "pillow",
      "cookware", "appliance", "vacuum", "storage", "organizer",
      "garden", "cleaning", "tool", "craft", "sewing", "paint",
      "adhesive", "food", "snack", "coffee", "tea", "spice", "grocery"], "Home"),
    (["book", "novel", "textbook", "journal", "educational", "magazine",
      "comic", "music", "album", "vinyl", "cd", "dvd", "movie", "film"], "Books"),
    (["clothing", "shirt", "dress", "pants", "jeans", "jacket", "shoe",
      "sneaker", "bag", "backpack", "wallet", "watch", "jewelry",
      "fashion", "apparel", "hat", "sunglasses", "costume", "doll",
      "toy", "game", "puzzle", "lego", "action figure"], "Fashion"),
]


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def classify_category(node_name: str, product_name: str, description: str) -> str:
    """Map an Amazon category path to a GoKart standard category."""
    top_level = node_name.split(" > ")[0].strip() if node_name else ""

    # 1. Direct mapping
    if top_level in AMAZON_CAT_MAP:
        mapped = AMAZON_CAT_MAP[top_level]
        if mapped is not None:
            return mapped

    # 2. Keyword sub-classification
    text = f"{node_name} {product_name} {description}".lower()
    for keywords, cat in KEYWORD_RULES:
        if any(kw in text for kw in keywords):
            return cat

    # 3. Fallback
    return "Home"


def extract_image_url(image_urls_raw: str) -> str:
    """Parse the imageUrls JSON array and pick the best image URL."""
    if not image_urls_raw or not image_urls_raw.strip():
        return ""

    try:
        urls = json.loads(image_urls_raw)
    except (json.JSONDecodeError, TypeError):
        return ""

    if not urls or not isinstance(urls, list):
        return ""

    # Pick the first URL and upgrade to higher quality
    url = urls[0] if isinstance(urls[0], str) else ""

    if not url:
        return ""

    # Strip all Amazon image scaling modifiers to get the raw high-res image.
    # E.g., ._AC_UL320_.jpg -> .jpg
    url = re.sub(r'\._[A-Za-z0-9_,]+_\.', '.', url)
    return url


def extract_image_url_birdfood(row: dict) -> str:
    """Extract image from bird_food schema (different column names)."""
    # Try mainImageUrl first, then images array
    main = (row.get("mainImageUrl") or "").strip()
    if main:
        return main

    images_raw = (row.get("images") or "").strip()
    if images_raw:
        try:
            imgs = json.loads(images_raw)
            if imgs and isinstance(imgs, list):
                first = imgs[0]
                if isinstance(first, dict):
                    return first.get("url", "")
                elif isinstance(first, str):
                    return first
        except (json.JSONDecodeError, TypeError):
            pass
    return ""


def parse_price(sale_price: str, listed_price: str) -> float:
    """Extract a valid price from salePrice or listedPrice."""
    for raw in [sale_price, listed_price]:
        if raw and raw.strip():
            cleaned = re.sub(r"[^\d.]", "", raw.strip())
            try:
                price = float(cleaned)
                if price > 0:
                    return round(price, 2)
            except ValueError:
                continue
    return 0.0


def parse_rating(raw: str) -> float:
    """Parse rating string to float."""
    if not raw or not raw.strip():
        return 0.0
    try:
        return round(float(raw.strip()), 1)
    except ValueError:
        return 0.0


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text).strip()


def clean_title(raw: str) -> str:
    """Shorten product title, removing excessive descriptions and seller boilerplate."""
    if not raw:
        return "Product"
    # Strip leading/trailing dashes and quotes
    t = raw.strip().replace('\"', '').replace('\'', '')
    t = re.sub(r'^[-|\s]+|[-|\s]+$', '', t)
    
    # Cut off at common seller boilerplate delimiters
    cutoffs = ['|', ' - ', ' – ', '【', '★', 'WELCOME', 'Package', 'Packing list', 'Material:']
    for c in cutoffs:
        idx = t.find(c)
        if idx > 15:  # Don't cut if the delimiter is too early in the string
            t = t[:idx].strip()
            
    # Max length 55 chars
    if len(t) > 55:
        # Try to cut at the last space before 55
        space_idx = t.rfind(' ', 0, 52)
        if space_idx > 15:
            t = t[:space_idx]
        else:
            t = t[:52]
        t += '...'
    return t


def clean_desc(raw: str) -> str:
    """Generate a clean, compact 1-2 line summary of the description."""
    if not raw or len(raw.strip()) < 5:
        return "No description available."
        
    d = raw
    # Remove dash-banner lines
    d = re.sub(r'["-]+\s*[A-Z ]+\s*["-]+', '', d)
    # Remove lines that are all caps + dashes
    d = re.sub(r'(?m)^[A-Z\s\-!★]{10,}$', '', d)
    # Remove boilerplate headers
    d = re.sub(r'(?i)(packing list|package includes?|package content|what(\'s| is) in(cluded)?( in)? (the )?box)[:\s]*', '', d)
    # Remove excessive newlines and trim
    d = re.sub(r'\n+', ' ', d)
    d = strip_html(d).strip()
    
    # Cap length to 150 chars max for the short description
    if len(d) > 150:
        space_idx = d.rfind(' ', 0, 147)
        if space_idx > 0:
            d = d[:space_idx] + '...'
        else:
            d = d[:147] + '...'
            
    return d if len(d) >= 5 else "No description available."


def auto_tags(name: str, category: str, brand: str) -> list[str]:
    """Generate tags from product name."""
    stop_words = {"the", "a", "an", "and", "or", "for", "of", "in", "with",
                  "to", "from", "by", "&", "is", "at", "on", "it", "its",
                  "this", "that", "all", "no", "not", "but", "each", "set",
                  "new", "one", "two", "three", "pack", "count", "size"}
    words = re.findall(r"[a-z]+", name.lower())
    tags = [w for w in words if len(w) > 2 and w not in stop_words][:6]
    if category.lower() not in [t.lower() for t in tags]:
        tags.append(category.lower())
    return tags


def generate_svg_placeholder(title: str, category: str) -> str:
    """Generate a data URI SVG placeholder card for products without images."""
    colors = CATEGORY_COLORS.get(category, ("#333333", "#ffffff"))
    icon = CATEGORY_ICONS.get(category, "📦")
    bg, fg = colors

    # Truncate title for display
    display_title = title[:30] + "…" if len(title) > 30 else title
    # Escape for SVG XML
    display_title = display_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
    cat_label = category.replace("&", "&amp;")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{bg};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:{bg}cc;stop-opacity:1"/>
    </linearGradient>
  </defs>
  <rect width="400" height="400" fill="url(#bg)" rx="12"/>
  <text x="200" y="160" text-anchor="middle" font-size="64" fill="{fg}" opacity="0.3">{icon}</text>
  <text x="200" y="230" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="16" font-weight="bold" fill="{fg}">{display_title}</text>
  <text x="200" y="260" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="12" fill="{fg}" opacity="0.6">{cat_label}</text>
</svg>'''

    encoded = urllib.parse.quote(svg, safe='')
    return f"data:image/svg+xml,{encoded}"


def make_product_id(sku: str, index: int) -> str:
    """Generate a unique product ID from SKU."""
    if sku and sku.strip():
        return f"amz_{sku.strip()}"
    return f"amz_gen_{index}"


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def process_best_sellers_csv(csv_path: str) -> list[dict]:
    """Read and normalize the Amazon Best Sellers CSV."""
    products = []
    seen_skus = set()

    print(f"  Reading: {csv_path}")
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            name = (row.get("name") or "").strip()
            if not name:
                continue

            sku = (row.get("sku") or "").strip()
            # Deduplicate by SKU
            if sku:
                if sku in seen_skus:
                    continue
                seen_skus.add(sku)

            # Category
            node_name = (row.get("nodeName") or row.get("new_path") or "").strip()
            description = strip_html(row.get("description") or "")
            category = classify_category(node_name, name, description)

            # Price
            price = parse_price(
                row.get("salePrice", ""),
                row.get("listedPrice", "")
            )
            if price <= 0:
                continue  # skip free / invalid products

            # Rating
            rating = parse_rating(row.get("rating", ""))

            # Image
            image = extract_image_url(row.get("imageUrls", ""))

            # Brand
            brand = (row.get("brandName") or "").strip()
            # Strip "Brand: " prefix that Amazon sometimes includes
            if brand.startswith("Brand: "):
                brand = brand[7:].strip()
            if not brand:
                # Extract from name
                parts = re.split(r"['\u2019]s\s|,\s*|\s-\s|\s–\s", name, maxsplit=1)
                brand = " ".join(parts[0].split()[:3]).strip() or "Unknown"

            # Tags
            tags = auto_tags(name, category, brand)

            # Build product
            pid = make_product_id(sku, idx)

            cleaned_title = clean_title(name)
            short_desc = clean_desc(description)

            product = {
                "id":                pid,
                "title":             name,
                "cleaned_title":     cleaned_title,
                "category":          category,
                "subcategory":       node_name.split(" > ")[0] if " > " in node_name else node_name,
                "brand":             brand,
                "price":             price,
                "rating":            rating,
                "image":             image,
                "source":            "amazon",
                "description":       description if description else f"{name} — premium quality product.",
                "short_description": short_desc,
                "tags":              tags,
            }
            products.append(product)

    print(f"  Parsed {len(products)} valid products from CSV")
    return products


def balance_dataset(products: list[dict], max_per_cat: int) -> list[dict]:
    """Balance the dataset so no category dominates."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for p in products:
        buckets[p["category"]].append(p)

    # Sort each bucket by rating desc (prefer higher-rated products)
    for cat in buckets:
        buckets[cat].sort(key=lambda p: (p["rating"], p["price"]), reverse=True)

    balanced = []
    for cat in STANDARD_CATEGORIES:
        items = buckets.get(cat, [])
        if len(items) > max_per_cat:
            # Take top-rated ones
            items = items[:max_per_cat]
        balanced.extend(items)
        print(f"    {cat}: {len(items)} products")

    return balanced


def apply_placeholders(products: list[dict]) -> list[dict]:
    """Add SVG placeholders for products missing images."""
    no_image_count = 0
    for p in products:
        if not p["image"]:
            p["image"] = generate_svg_placeholder(p["title"], p["category"])
            no_image_count += 1

    print(f"  Generated {no_image_count} SVG placeholders")
    return products


def main():
    print("=" * 60)
    print("  GoKart Dataset Builder")
    print("=" * 60)

    if not os.path.exists(CSV_PATH):
        print(f"\n  ERROR: CSV not found at {CSV_PATH}")
        return

    # 1. Parse CSV
    print("\n[1/4] Parsing Amazon Best Sellers CSV...")
    products = process_best_sellers_csv(CSV_PATH)

    # 2. Balance
    print(f"\n[2/4] Balancing dataset (max {MAX_PER_CATEGORY} per category)...")
    products = balance_dataset(products, MAX_PER_CATEGORY)

    # 3. Add placeholders for missing images
    print(f"\n[3/4] Generating image placeholders...")
    products = apply_placeholders(products)

    # 4. Write output
    print(f"\n[4/4] Writing {len(products)} products to {OUTPUT_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\n  Output: {OUTPUT_PATH}")
    print(f"  Size:   {file_size:.1f} MB")
    print(f"  Total:  {len(products)} products")
    print("=" * 60)


if __name__ == "__main__":
    main()
