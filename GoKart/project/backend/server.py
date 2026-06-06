"""
server.py
─────────
GoKart Flask application — defines all API routes and serves the frontend.

Routes
------
  Auth        : /api/register  /api/login  /api/logout  /api/me
  Products    : /api/products  /api/products/<id>  /api/categories
  Tracking    : /api/track
  Recommends  : /api/recommendations  /api/recommendations/me  /api/curated
  AI Compare  : /api/compare
  Static      : / and /<path:filename>

Start via the project root: python server.py
"""

import hashlib
import json
import logging
import os
import random
import re
import secrets
import tempfile
import urllib.parse
import urllib.request
from logging.handlers import RotatingFileHandler

import pymysql
from flask import Flask, jsonify, request, send_from_directory, session

from backend.db_config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from backend.data_processor import DataProcessor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── AI Provider (GroqCloud — modular setup) ──────────────────────────────────
from backend.ai_provider import AIProvider
ai_provider = AIProvider()

# In-memory comparison cache  {cache_key: answer_str}
_compare_cache: dict[str, str] = {}

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(BASE_DIR)
FRONTEND_DIR  = os.path.join(PROJECT_ROOT, "frontend")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR    = os.path.join(FRONTEND_DIR, "static")
RECSYS_API_URL = os.environ.get("RECSYS_API_URL", "http://localhost:8000")

# ── Logging Configuration ──────────────────────────────────────────────────
# ── Logging Configuration ──────────────────────────────────────────────────
LOG_DIR = os.path.join(tempfile.gettempdir(), "LOGS")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "session.log")
handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
# Also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def log_session_event(event_type, user_email, data=None):
    """Log a structured session event to the log file."""
    msg = f"EVENT: {event_type} | USER: {user_email}"
    if data:
        msg += f" | DATA: {json.dumps(data)}"
    logger.info(msg)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ── Data Processor (runs once at startup) ───────────────────────────────────
dp = DataProcessor()
PRODUCTS = dp.all_products          # balanced flat list
MIXED    = dp.mixed_products        # interleaved for mixed feed


def get_db():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def init_db():
    """Create the database and users table if they do not already exist."""
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, port=DB_PORT,
        autocommit=True
    )
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(f"USE `{DB_NAME}`")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INT          AUTO_INCREMENT PRIMARY KEY,
                name       VARCHAR(120) NOT NULL,
                email      VARCHAR(255) NOT NULL UNIQUE,
                password   VARCHAR(255) NOT NULL,
                created_at DATETIME     DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)
    conn.close()


# ── Recommendation Engine ───────────────────────────────────────────────────
try:
    from backend.recommendation.engine import RecommendationEngine
    rec_engine = RecommendationEngine(PRODUCTS)
except Exception:
    logger.exception("Failed to initialize recommendation engine. Falling back to curated/random strategies.")
    rec_engine = None


# ═══════════════════════════════════════════════════════════════════════════
#  AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/register", methods=["POST"])
def register():
    data  = request.get_json(force=True)
    name  = (data.get("name",  "") or "").strip()
    email = (data.get("email", "") or "").strip().lower()
    pwd   = (data.get("password", "") or "").strip()

    if not name or not email or not pwd:
        return jsonify({"error": "All fields are required."}), 400
    if len(pwd) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    try:
        hashed_pwd = hashlib.sha256(pwd.encode()).hexdigest()
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed_pwd)
            )
        conn.close()
    except pymysql.err.IntegrityError:
        return jsonify({"error": "Email already registered."}), 409

    session["user"] = {"name": name, "email": email}
    log_session_event("REGISTER", email, {"name": name})
    return jsonify({"name": name, "email": email}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data  = request.get_json(force=True)
    email = (data.get("email", "") or "").strip().lower()
    pwd   = (data.get("password", "") or "").strip()

    hashed_pwd = hashlib.sha256(pwd.encode()).hexdigest()

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name, email FROM users WHERE email = %s AND password = %s",
            (email, hashed_pwd)
        )
        row = cur.fetchone()
    conn.close()

    if not row:
        log_session_event("LOGIN_FAILED", email)
        return jsonify({"error": "Invalid email or password."}), 401

    session["user"] = {"name": row["name"], "email": row["email"]}
    log_session_event("LOGIN_SUCCESS", row["email"])
    return jsonify({"name": row["name"], "email": row["email"]}), 200


@app.route("/api/logout", methods=["POST"])
def logout():
    user = session.get("user")
    email = user["email"] if user else "anonymous"
    session.pop("user", None)
    log_session_event("LOGOUT", email)
    return jsonify({"ok": True}), 200


@app.route("/api/me")
def me():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user), 200


# ═══════════════════════════════════════════════════════════════════════════
#  PRODUCT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/categories")
def categories():
    """Return available categories with product counts."""
    return jsonify(dp.category_counts), 200


@app.route("/api/products/<product_id>")
def product_detail(product_id):
    """Return a single product by ID."""
    product = dp.id_map.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(product), 200


@app.route("/api/products")
def products():
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 20, type=int)
    search = request.args.get("search", "", type=str).strip()
    category = request.args.get("category", "", type=str).strip()

    # Use TF-IDF semantic search when a query is present
    if search:
        source = dp.search(search, category=category)
    elif category and category.lower() != "all":
        source = dp.category_index.get(category, [])
    else:
        source = MIXED

    return jsonify(dp.paginate(source, page, limit)), 200


# ═══════════════════════════════════════════════════════════════════════════
#  TRACKING
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/track", methods=["POST"])
def track():
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("id")
    cat = data.get("cat")

    if pid or cat:
        interactions = session.get("interactions", [])
        interaction = {"id": pid, "cat": cat}
        if interaction not in interactions:
            interactions.append(interaction)
            session["interactions"] = interactions[-50:]  # keep last 50
            session.modified = True
            
            user = session.get("user")
            email = user["email"] if user else "anonymous"
            log_session_event("TRACK", email, interaction)
    return jsonify({"status": "tracked"}), 200


# ═══════════════════════════════════════════════════════════════════════════
#  RECOMMENDATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/recommendations/me")
def recommendations_me():
    """Return personalised recommendations for the currently logged-in user.
    Tries the context-aware recsys FastAPI service first, then falls back
    to the local recommendation engine.  Supports pagination via page/limit."""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 10, type=int)
    limit = min(limit, 50)
    if page < 1:
        page = 1

    email = user["email"]
    name = user.get("name", email)
    location = request.args.get("location", "home")
    mock_time = request.args.get("mock_time", "")

    # Try the context-aware recsys service (FastAPI on port 8000)
    try:
        params = urllib.parse.urlencode({
            "user_id": email,
            "user_name": name,
            "location": location,
            "mock_time": mock_time,
        })
        url = f"{RECSYS_API_URL}/api/recommendations?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            # Paginate external service results
            all_recs = data if isinstance(data, list) else []
            return jsonify(dp.paginate(all_recs, page, limit)), 200
    except Exception:
        pass

    # Fallback to local recommendation engine
    client_interactions = session.get("interactions", [])
    if rec_engine:
        all_recs = rec_engine.get_recommendations(client_interactions, top_n=100)
    else:
        all_recs = random.sample(PRODUCTS, min(50, len(PRODUCTS)))

    return jsonify(dp.paginate(all_recs, page, limit)), 200


@app.route("/api/recommendations", methods=["GET", "POST"])
def recommendations():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 10, type=int)
    limit = min(limit, 50)
    if page < 1:
        page = 1

    client_interactions = session.get("interactions", [])
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        if "interactions" in data:
            client_interactions = data["interactions"]
        if "product_id" in data and "category" in data:
            interaction = {"id": data["product_id"], "cat": data["category"]}
            if interaction not in client_interactions:
                client_interactions.append(interaction)
                session["interactions"] = client_interactions[-50:]
                session.modified = True

    if rec_engine:
        all_recs = rec_engine.get_recommendations(client_interactions, top_n=100)
    else:
        all_recs = random.sample(PRODUCTS, min(50, len(PRODUCTS)))

    return jsonify(dp.paginate(all_recs, page, limit)), 200


# ═══════════════════════════════════════════════════════════════════════════
#  CURATED (works for both authenticated & anonymous users)
# ═══════════════════════════════════════════════════════════════════════════

def get_trending_products(count: int = 12) -> list[dict]:
    """Return high-rated, category-diverse products for anonymous users."""
    # Pick top-rated products from each category, round-robin
    buckets: dict[str, list[dict]] = {}
    for cat, items in dp.category_index.items():
        sorted_items = sorted(items, key=lambda p: p.get("rating", 0), reverse=True)
        buckets[cat] = sorted_items

    result: list[dict] = []
    per_cat = max(2, count // len(buckets)) if buckets else count
    for cat in buckets:
        result.extend(buckets[cat][:per_cat])

    return result[:count]


@app.route("/api/curated")
def curated():
    """Return curated products — personalised if logged in, trending otherwise."""
    count = request.args.get("count", 12, type=int)
    count = min(max(1, count), 24)

    user = session.get("user")
    if user:
        # Try recommendation engine with user interactions
        client_interactions = session.get("interactions", [])
        if rec_engine and client_interactions:
            recs = rec_engine.get_recommendations(client_interactions, top_n=count)
        elif rec_engine:
            recs = rec_engine.get_recommendations([], top_n=count)
        else:
            recs = get_trending_products(count)
    else:
        recs = get_trending_products(count)

    return jsonify({"products": recs}), 200


# ═══════════════════════════════════════════════════════════════════════════
#  AI COMPARISON ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

def _sanitize(text: str, max_len: int = 500) -> str:
    """Strip HTML tags, control chars, and truncate to prevent prompt injection."""
    text = re.sub(r'<[^>]+>', '', str(text))          # strip HTML
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # control chars
    # Block basic injection attempts
    for bad in ['ignore previous', 'forget instructions', 'system:', 'assistant:']:
        text = re.sub(re.escape(bad), '***', text, flags=re.IGNORECASE)
    return text[:max_len].strip()


def _format_product_for_prompt(p: dict, idx: int) -> str:
    """Convert a product dict to a clean text block for the LLM prompt."""
    title   = _sanitize(p.get('title') or p.get('name') or 'Unknown', 120)
    cat     = _sanitize(p.get('category') or 'General', 60)
    price   = p.get('price', 'N/A')
    rating  = p.get('rating', 'N/A')
    desc    = _sanitize(p.get('description') or p.get('desc') or '', 300)
    brand   = _sanitize(p.get('brand') or '', 60)
    source  = p.get('source', '')
    currency = '₹' if source == 'flipkart' else '$'

    lines = [
        f"Product {idx}: {title}",
        f"  Category : {cat}",
        f"  Price    : {currency}{price}",
        f"  Rating   : {rating}/5",
    ]
    if brand:
        lines.append(f"  Brand    : {brand}")
    if desc:
        lines.append(f"  Details  : {desc}")
    return '\n'.join(lines)


@app.route("/api/compare", methods=["POST"])
def compare_products():
    """LLM-powered product comparison grounded strictly in provided product data."""
    data     = request.get_json(force=True, silent=True) or {}
    products = data.get("products", [])
    raw_query = data.get("query", "Which product is best?")

    # ── Edge cases ──────────────────────────────────────────────────────────
    if not products:
        return jsonify({"answer": "Please select at least one product to compare. You can add products using the **+ Compare** button on any product card."}), 200

    # Clamp & sanitize inputs
    products = products[:4]
    query    = _sanitize(raw_query, 300)
    if not query:
        query = "Which product is best?"

    # ── Cache check ─────────────────────────────────────────────────────────
    ids_key  = ','.join(str(p.get('id', '')) for p in products)
    cache_key = hashlib.md5(f"{ids_key}||{query}".encode()).hexdigest()
    if cache_key in _compare_cache:
        return jsonify({"answer": _compare_cache[cache_key], "cached": True}), 200

    # ── Build grounded prompt ───────────────────────────────────────────────
    product_blocks = '\n\n'.join(
        _format_product_for_prompt(p, i + 1) for i, p in enumerate(products)
    )

    if len(products) == 1:
        mode_instruction = (
            "The user has selected only one product. "
            "Provide a concise, helpful summary of this product including its key strengths, "
            "potential drawbacks, and who it would suit best. "
            "Do NOT invent features not listed above."
        )
    else:
        mode_instruction = (
            "Compare the products above. "
            "Use ONLY the data provided — do not invent or assume any features, specs, or attributes. "
            "Structure your response as:\n"
            "1. **Quick comparison** (2-3 sentences)\n"
            "2. **Pros & Cons** for each product (bullet points)\n"
            "3. **Recommendation** — which to pick and for whom, based strictly on the data above."
        )

    system_msg = (
        "You are GoKart's expert product comparison assistant. "
        "You MUST base every claim solely on the product data provided in the user message. "
        "Never hallucinate specs, prices, or features. "
        "Be concise, friendly, and helpful. Use markdown formatting."
    )

    user_msg = (
        f"Here is the product data:\n\n{product_blocks}\n\n"
        f"User question: {query}\n\n"
        f"{mode_instruction}"
    )

    # ── Helper: generate mock comparison from product data ─────────────────
    def _mock_compare(prods, q):
        """Build a grounded comparison using only the product data we have."""
        def _get(p, *keys, default='N/A'):
            for k in keys:
                v = p.get(k)
                if v:
                    return v
            return default

        if len(prods) == 1:
            p = prods[0]
            title = _get(p, 'title', 'name', default='Product')
            price = _get(p, 'price')
            rating = _get(p, 'rating')
            cat = _get(p, 'category')
            desc = _get(p, 'description', 'desc', default='')
            brand = _get(p, 'brand', default='')
            source = p.get('source', '')
            currency = '₹' if source == 'flipkart' else '$'

            lines = [
                f"## 📋 {title}\n",
                f"**Category:** {cat}  ",
                f"**Price:** {currency}{price}  ",
                f"**Rating:** {'⭐' * min(int(float(rating)), 5)} ({rating}/5)  " if rating != 'N/A' else "",
                f"**Brand:** {brand}  " if brand else "",
                "",
                "### ✅ Key Strengths",
            ]
            if rating != 'N/A' and float(rating) >= 4.0:
                lines.append(f"- Highly rated at **{rating}/5** by buyers")
            if price != 'N/A':
                lines.append(f"- Priced at **{currency}{price}**")
            if brand:
                lines.append(f"- From trusted brand **{brand}**")
            if desc:
                lines.append(f"- {desc[:150]}")

            lines += [
                "",
                "### 🎯 Best For",
                f"- Shoppers looking for a solid **{cat}** product at this price point.",
            ]
            return '\n'.join(lines)

        # ── Multi-product comparison ────────────────────────────────────────
        lines = ["## ⚡ Quick Comparison\n"]

        # Summary sentence
        names = [_get(p, 'title', 'name', default='Product') for p in prods]
        lines.append(f"Comparing **{', '.join(names[:-1])}** and **{names[-1]}**.\n")

        # Table
        lines.append("| Feature | " + " | ".join(f"**{n[:25]}**" for n in names) + " |")
        lines.append("|---|" + "|".join(["---"] * len(prods)) + "|")

        # Price row
        prices = []
        for p in prods:
            source = p.get('source', '')
            currency = '₹' if source == 'flipkart' else '$'
            pr = _get(p, 'price')
            prices.append(f"{currency}{pr}" if pr != 'N/A' else 'N/A')
        lines.append("| 💰 Price | " + " | ".join(prices) + " |")

        # Rating row
        ratings = [_get(p, 'rating') for p in prods]
        lines.append("| ⭐ Rating | " + " | ".join(f"{r}/5" if r != 'N/A' else 'N/A' for r in ratings) + " |")

        # Category row
        cats = [_get(p, 'category') for p in prods]
        lines.append("| 📂 Category | " + " | ".join(cats) + " |")

        # Brand row
        brands = [_get(p, 'brand', default='-') for p in prods]
        lines.append("| 🏷️ Brand | " + " | ".join(brands) + " |")

        lines.append("")

        # Pros & Cons per product
        lines.append("### 👍 Pros & 👎 Cons\n")
        for i, p in enumerate(prods):
            title = _get(p, 'title', 'name', default='Product')
            rating = _get(p, 'rating')
            price = _get(p, 'price')
            source = p.get('source', '')
            currency = '₹' if source == 'flipkart' else '$'

            lines.append(f"**{i+1}. {title}**")
            # Pros
            if rating != 'N/A' and float(rating) >= 4.0:
                lines.append(f"- ✅ Excellent rating ({rating}/5)")
            elif rating != 'N/A' and float(rating) >= 3.0:
                lines.append(f"- ✅ Decent rating ({rating}/5)")
            if price != 'N/A':
                lines.append(f"- ✅ Available at {currency}{price}")
            desc = _get(p, 'description', 'desc', default='')
            if desc:
                lines.append(f"- ✅ {desc[:100]}")
            # Cons
            if rating != 'N/A' and float(rating) < 3.5:
                lines.append(f"- ⚠️ Below-average rating ({rating}/5)")
            lines.append("")

        # Recommendation
        lines.append("### 🏆 Recommendation\n")
        # Pick the best rated one
        best = max(prods, key=lambda p: float(p.get('rating', 0) or 0))
        best_name = _get(best, 'title', 'name', default='Product')
        best_rating = _get(best, 'rating')
        lines.append(f"Based on the data, **{best_name}** stands out with a rating of **{best_rating}/5**. "
                      f"It's a strong choice if you're looking for the highest-rated option among these.")

        # Check cheapest
        def safe_price(p):
            try:
                return float(str(p.get('price', '0')).replace(',', ''))
            except (ValueError, TypeError):
                return float('inf')
        cheapest = min(prods, key=safe_price)
        if cheapest != best:
            ch_name = _get(cheapest, 'title', 'name', default='Product')
            ch_source = cheapest.get('source', '')
            ch_curr = '₹' if ch_source == 'flipkart' else '$'
            ch_price = _get(cheapest, 'price')
            lines.append(f"\nIf budget is your priority, consider **{ch_name}** at **{ch_curr}{ch_price}**.")

        return '\n'.join(lines)

    # ── AI call (with mock fallback) ─────────────────────────────────────────
    if ai_provider.available:
        try:
            # Use Groq-supported high-performance models
            answer = ai_provider.generate_comparison(
                system_msg=system_msg,
                user_msg=user_msg,
                model="qwen/qwen3-32b"
            )
            
            if answer:
                # Cache the result (keep cache bounded)
                if len(_compare_cache) > 200:
                    keys = list(_compare_cache.keys())
                    for k in keys[:50]:
                        del _compare_cache[k]
                _compare_cache[cache_key] = answer
                return jsonify({"answer": answer}), 200

        except Exception:
            logger.exception("GroqCloud compare call failed — falling back to mock comparison")

    # ── Fallback: mock comparison built from product data ───────────────────
    # Lightweight indicator for the frontend
    fallback_indicator = "\n\n> [!NOTE]\n> AI insights unavailable, using standard comparison mode\n"
    answer = _mock_compare(products, query) + fallback_indicator
    _compare_cache[cache_key] = answer
    return jsonify({"answer": answer, "fallback": True}), 200


# ═══════════════════════════════════════════════════════════════════════════
#  STATIC FILES
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/")
def root():
    return send_from_directory(TEMPLATES_DIR, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    if filename.endswith(".html"):
        return send_from_directory(TEMPLATES_DIR, filename)
    return send_from_directory(STATIC_DIR, filename)


# Entry point is project root server.py — do not run this module directly.
