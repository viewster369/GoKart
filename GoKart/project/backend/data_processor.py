"""
data_processor.py
─────────────────
Loads, normalises, balances and indexes the product catalogue so the API
can serve a diverse, paginated feed instead of category-dominated results.

Usage
-----
    from backend.data_processor import DataProcessor
    dp = DataProcessor()               # auto-resolves data/products.json
    dp.print_diagnostics()
    products   = dp.mixed_products     # balanced + interleaved list
    cat_index  = dp.category_index     # { "Fashion": [...], ... }
    categories = dp.category_counts    # { "Fashion": 2000, ... }
"""

import json
import math
import os
import random
import re
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Standard target categories ──────────────────────────────────────────────
STANDARD_CATEGORIES = [
    "Electronics",
    "Fashion",
    "Home",
    "Books",
    "Beauty",
    "Sports",
]

# ── Keyword → category mapping (order matters: first match wins) ────────────
# Sports is FIRST so cricket/fitness items from "Sports, Books and More"
# get classified correctly before Books or Beauty can false-match.
_CATEGORY_RULES: list[tuple[list[str], str]] = [
    # Sports (must be before Books / Beauty to avoid false positives)
    (["sport", "fitness", "gym", "yoga", "cricket", "football",
      "badminton", "tennis", "running", "cycling", "treadmill",
      "dumbbell", "weight", "protein", "supplement", "outdoor",
      "camping", "trekking", "hiking", "swimming", "exercise",
      "athletic", "basketball", "volleyball", "bat", "ball",
      "wicket", "stumps", "gloves", "helmet", "pads",
      "racket", "shuttle", "skipping", "resistance"], "Sports"),
    # Electronics
    (["mobile", "phone", "laptop", "tablet", "headphone", "earphone",
      "earbuds", "speaker", "camera", "television", "tv", "monitor",
      "charger", "powerbank", "smartwatch", "pendrive", "hard disk",
      "gadget", "electronics", "computer", "printer", "keyboard",
      "mouse", "router", "adapter", "led", "usb", "bluetooth",
      "rechargeable", "cable"], "Electronics"),
    # Beauty (no generic "beauty" — causes false positives on product names)
    (["cosmetic", "skincare", "makeup", "perfume", "fragrance",
      "shampoo", "conditioner", "cream", "lotion", "serum", "sunscreen",
      "lipstick", "foundation", "moisturizer", "face wash", "nail polish",
      "personal care", "grooming", "trimmer", "shaver", "hair dryer"],
     "Beauty"),
    # Home (no generic "home" — causes false positives)
    (["kitchen", "furniture", "home decor", "bedsheet", "curtain",
      "pillow", "mattress", "cookware", "utensil", "appliance",
      "vacuum", "iron box", "mixer", "grinder", "blender", "microwave",
      "washing machine", "refrigerator", "lamp",
      "storage", "organizer", "garden", "cleaning", "home & kitchen"],
     "Home"),
    # Books
    (["book", "novel", "textbook", "notebook", "journal", "diary",
      "stationery", "pen", "pencil", "study", "educational",
      "magazine", "comic"], "Books"),
    # Fashion (broadest — acts as fallback for clothing / bags / shoes)
    (["clothing", "shirt", "t-shirt", "tshirt", "jeans", "trouser",
      "pant", "jacket", "hoodie", "sweater", "kurta", "saree", "dress",
      "skirt", "legging", "shorts", "underwear", "innerwear", "sock",
      "shoe", "sneaker", "sandal", "slipper", "boot", "heel",
      "bag", "backpack", "handbag", "wallet", "belt", "watch",
      "sunglasses", "cap", "hat", "scarf", "tie", "glove",
      "luggage", "suitcase", "trolley", "fashion", "apparel",
      "men's clothing", "women's clothing", "kid"], "Fashion"),
]

# ── Raw-category direct mapping (exact match, case-insensitive) ─────────────
_RAW_CATEGORY_MAP: dict[str, str] = {
    "men's clothing":          "Fashion",
    "women's clothing":        "Fashion",
    "suitcases":               "Fashion",
    "sports, books and more":  None,       # needs keyword sub-classification
}

# Maximum products per standard category (for balancing)
DEFAULT_MAX_PER_CATEGORY = 2000


class DataProcessor:
    """One-shot data pipeline executed at server startup."""

    def __init__(self, json_path: str | None = None, max_per_cat: int = DEFAULT_MAX_PER_CATEGORY):
        if json_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            json_path = os.path.join(project_root, "data", "products.json")
            if not os.path.exists(json_path):
                raise FileNotFoundError(
                    f"Dataset not found at {json_path}. "
                    "Run 'python scripts/build_dataset.py' to generate it."
                )

        self._raw: list[dict] = self._load(json_path)
        self._max_per_cat = max_per_cat

        # Pipeline
        normalised = [self._normalise(p) for p in self._raw]
        balanced   = self._balance(normalised)
        self._build_index(balanced)
        self.mixed_products: list[dict] = self._interleave(balanced)
        self.all_products: list[dict] = balanced          # flat balanced list
        self.id_map: dict[str, dict] = {p["id"]: p for p in balanced}

        # Build TF-IDF search index for semantic search
        self._build_search_index(balanced)

    # ── Load ────────────────────────────────────────────────────────────────
    @staticmethod
    def _load(path: str) -> list[dict]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ── Normalise a single product ──────────────────────────────────────────
    def _normalise(self, raw: dict) -> dict:
        raw_cat  = (raw.get("category") or "").strip()
        name     = (raw.get("title") or raw.get("name") or "").strip()
        desc     = (raw.get("description") or raw.get("desc") or "").strip()
        image    = (raw.get("image") or raw.get("img") or "").strip()
        source   = (raw.get("source") or "unknown").strip().lower()
        tags     = raw.get("tags") or []
        pid      = str(raw.get("id", ""))

        # Price – ensure numeric
        price_raw = raw.get("price", 0)
        if isinstance(price_raw, str):
            price_raw = re.sub(r"[^\d.]", "", price_raw)
            try:
                price_raw = float(price_raw)
            except ValueError:
                price_raw = 0.0
        price = round(float(price_raw), 2)

        # Rating – ensure numeric
        rating_raw = raw.get("rating", 0)
        if isinstance(rating_raw, str):
            try:
                rating_raw = float(rating_raw.split()[-1])
            except (ValueError, IndexError):
                rating_raw = 0.0
        rating = round(float(rating_raw), 1)

        # Determine standard category
        category = self._classify(raw_cat, name, desc, tags)
        subcategory = raw_cat if raw_cat.lower() != category.lower() else ""

        # Use existing brand if present, otherwise extract from name
        brand = (raw.get("brand") or "").strip() or self._extract_brand(name)

        # Auto-generate tags if empty
        if not tags:
            tags = self._auto_tags(name, category, subcategory)

        return {
            "id":          pid,
            "title":       name,
            "category":    category,
            "subcategory": subcategory,
            "brand":       brand,
            "price":       price,
            "rating":      rating,
            "image":       image,
            "source":      source,
            "description": desc,
            "tags":        tags,
        }

    # ── Category classification ─────────────────────────────────────────────
    @staticmethod
    def _classify(raw_cat: str, name: str, desc: str, tags: list[str]) -> str:
        raw_lower = raw_cat.lower().strip()

        # 0. Already a standard category — preserve as-is
        for std in STANDARD_CATEGORIES:
            if raw_lower == std.lower():
                return std

        # 1. Exact match (direct-mapped categories)
        if raw_lower in _RAW_CATEGORY_MAP:
            mapped = _RAW_CATEGORY_MAP[raw_lower]
            if mapped is not None:
                return mapped
            # None → needs keyword sub-classification.
            # IMPORTANT: exclude raw_cat from search text to avoid
            # false matches (e.g. "Sports, Books and More" contains "book").
            text = f"{name} {desc} {' '.join(tags)}".lower()
        else:
            text = f"{raw_cat} {name} {desc} {' '.join(tags)}".lower()

        # 2. Keyword matching on combined text
        for keywords, cat in _CATEGORY_RULES:
            if any(kw in text for kw in keywords):
                return cat

        # 3. Default fallback
        return "Fashion"

    # ── Brand extraction heuristic ──────────────────────────────────────────
    @staticmethod
    def _extract_brand(name: str) -> str:
        if not name:
            return "Unknown"
        # Take text before the first "'s" or first comma/dash
        parts = re.split(r"['\u2019]s\s|,\s*|\s-\s|\s–\s", name, maxsplit=1)
        candidate = parts[0].strip()
        words = candidate.split()
        # A brand is typically 1-3 words
        brand = " ".join(words[:min(3, len(words))])
        return brand if brand else "Unknown"

    # ── Auto-tag generation ─────────────────────────────────────────────────
    @staticmethod
    def _auto_tags(name: str, category: str, subcategory: str) -> list[str]:
        stop = {"the", "a", "an", "and", "or", "for", "of", "in", "with",
                "to", "from", "by", "&", "men's", "women's", "is", "at"}
        words = re.findall(r"[a-z]+", name.lower())
        tags = [w for w in words if len(w) > 2 and w not in stop][:6]
        if category.lower() not in [t.lower() for t in tags]:
            tags.append(category.lower())
        if subcategory and subcategory.lower() not in [t.lower() for t in tags]:
            tags.append(subcategory.lower())
        return tags

    # ── Balance dataset ─────────────────────────────────────────────────────
    def _balance(self, products: list[dict]) -> list[dict]:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for p in products:
            buckets[p["category"]].append(p)

        balanced: list[dict] = []
        for cat in STANDARD_CATEGORIES:
            items = buckets.get(cat, [])
            if len(items) > self._max_per_cat:
                random.seed(42)   # deterministic sampling
                items = random.sample(items, self._max_per_cat)
            balanced.extend(items)

        # Also include any products in categories not in STANDARD_CATEGORIES
        for cat, items in buckets.items():
            if cat not in STANDARD_CATEGORIES:
                balanced.extend(items[:self._max_per_cat])

        return balanced

    # ── Category index ──────────────────────────────────────────────────────
    def _build_index(self, products: list[dict]) -> None:
        self.category_index: dict[str, list[dict]] = defaultdict(list)
        for p in products:
            self.category_index[p["category"]].append(p)
        
        # Sort each category index by rating descending (popularity)
        for cat in self.category_index:
            self.category_index[cat].sort(key=lambda x: x.get("rating", 0), reverse=True)
            
        self.category_counts: dict[str, int] = {
            cat: len(items) for cat, items in self.category_index.items()
        }

    # ── Interleave for a mixed feed ─────────────────────────────────────────
    def _interleave(self, products: list[dict]) -> list[dict]:
        """Round-robin across categories, then light shuffle within 10-item
        windows so the feed feels natural, not perfectly cyclic."""
        buckets: dict[str, list[dict]] = defaultdict(list)
        for p in products:
            buckets[p["category"]].append(p)

        # Sort each bucket by rating descending (popularity)
        for items in buckets.values():
            items.sort(key=lambda x: x.get("rating", 0), reverse=True)

        # Round-robin
        interleaved: list[dict] = []
        iterators = {cat: iter(items) for cat, items in buckets.items()}
        active = set(iterators.keys())

        while active:
            for cat in list(active):
                try:
                    interleaved.append(next(iterators[cat]))
                except StopIteration:
                    active.discard(cat)

        return interleaved

    # ── TF-IDF Search Index ──────────────────────────────────────────────────
    def _build_search_index(self, products: list[dict]) -> None:
        """Build a TF-IDF matrix from product schema fields for semantic search."""
        self._search_products = products
        documents = []
        for p in products:
            # Combine key schema fields into a single searchable document
            parts = [
                p.get("title", ""),
                p.get("cleaned_title", ""),
                p.get("category", ""),
                p.get("subcategory", ""),
                p.get("brand", ""),
                p.get("description", "")[:200],
                p.get("short_description", ""),
                " ".join(p.get("tags", [])),
            ]
            documents.append(" ".join(parts).lower())

        self._tfidf = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
        )
        self._tfidf_matrix = self._tfidf.fit_transform(documents)
        print(f"  [OK] TF-IDF search index built: {self._tfidf_matrix.shape[0]} docs x {self._tfidf_matrix.shape[1]} features")

    # ── Semantic Search with Cosine Similarity ──────────────────────────────
    def search(self, query: str, category: str = "", source_list: list[dict] | None = None) -> list[dict]:
        """Search products using TF-IDF cosine similarity for relevance ranking."""
        # If a custom source_list is provided (e.g. category-filtered),
        # fall back to keyword search within that subset.
        if source_list is not None:
            return self._keyword_search(query, category, source_list)

        if not query or not query.strip():
            pool = self.mixed_products
            if category and category.lower() != "all":
                pool = [p for p in pool if p["category"].lower() == category.lower()]
            return pool

        # Transform query into TF-IDF vector and compute cosine similarity
        query_vec = self._tfidf.transform([query.lower()])
        scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

        # Get indices sorted by similarity score (descending)
        ranked_indices = np.argsort(scores)[::-1]

        # Filter to products with a non-zero similarity score
        results = []
        for idx in ranked_indices:
            if scores[idx] <= 0:
                break
            p = self._search_products[idx]
            if category and category.lower() != "all":
                if p["category"].lower() != category.lower():
                    continue
            results.append(p)

        return results

    # ── Fallback keyword search for filtered subsets ────────────────────────
    @staticmethod
    def _keyword_search(query: str, category: str, pool: list[dict]) -> list[dict]:
        """Simple keyword search used when searching within a pre-filtered list."""
        results = pool
        if category and category.lower() != "all":
            results = [p for p in results if p["category"].lower() == category.lower()]
        if query:
            q = query.lower()
            results = [
                p for p in results
                if q in p.get("title", "").lower()
                or q in p.get("category", "").lower()
                or q in p.get("subcategory", "").lower()
                or q in p.get("brand", "").lower()
                or any(q in t for t in p.get("tags", []))
            ]
        return results

    # ── Paginate helper ─────────────────────────────────────────────────────
    @staticmethod
    def paginate(items: list[dict], page: int = 1, limit: int = 20) -> dict:
        page = max(1, page)
        limit = min(max(1, limit), 50)
        total = len(items)
        total_pages = math.ceil(total / limit) if total > 0 else 1
        start = (page - 1) * limit
        end = start + limit
        sliced = items[start:end]
        return {
            "products":    sliced,
            "page":        page,
            "total":       total,
            "total_pages": total_pages,
            "has_more":    end < total,
        }

    # ── Diagnostics ─────────────────────────────────────────────────────────
    def print_diagnostics(self) -> None:
        print("\n" + "=" * 55)
        print("  DATA PROCESSOR — Category Distribution (Balanced)")
        print("=" * 55)
        for cat in sorted(self.category_counts, key=lambda c: -self.category_counts[c]):
            cnt = self.category_counts[cat]
            bar = "#" * (cnt // 50)
            print(f"  {cat:<15} {cnt:>5}  {bar}")
        print(f"\n  Total balanced products : {len(self.all_products)}")
        print(f"  Mixed feed length      : {len(self.mixed_products)}")
        print(f"  ID-map entries         : {len(self.id_map)}")
        print("=" * 55 + "\n")


# ── Standalone test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    dp = DataProcessor()
    dp.print_diagnostics()

    # Show a sample from each category
    for cat, items in dp.category_index.items():
        if items:
            p = items[0]
            print(f"  [{cat}]  {p['title'][:60]}  (${p['price']})")
