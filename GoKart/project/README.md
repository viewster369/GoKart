# 🛒 GoKart — AI-Powered Product Recommendation System

GoKart is a full-stack e-commerce platform built with **Flask** and vanilla **HTML/CSS/JS** that serves personalised product recommendations using a hybrid recommendation engine (content-based + collaborative filtering). It supports user authentication, real-time product browsing, AI-assisted product comparison, and session-based interaction tracking.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔐 **Auth** | Register / Login / Logout with session-based authentication |
| 🛍 **Product Catalogue** | 12,000 + products across 6 categories, paginated |
| 🔍 **Search & Filter** | Full-text search + category filtering via API |
| 🤖 **Recommendations** | Hybrid engine (content-based TF-IDF + collaborative popularity) |
| 🧠 **AI Comparison** | GroqCloud-powered product comparison (falls back to rule-based) |
| 📦 **Cart** | Client-side cart with persistent localStorage |
| 📊 **Session Logging** | Rotating log file for auth + tracking events |

---

## 📂 Project Structure

```
RTRP/
├── backend/
│   ├── __init__.py            # Package marker
│   ├── server.py              # Flask app — all API routes
│   ├── db_config.py           # MySQL config (reads from .env)
│   ├── data_processor.py      # Data pipeline: load → normalise → balance → index
│   └── recommendation/
│       ├── __init__.py
│       ├── engine.py          # Hybrid recommendation engine
│       ├── content_based.py   # TF-IDF cosine similarity model
│       ├── collaborative.py   # Popularity-based collaborative model
│       └── tracker.py         # User interaction parser
│
├── frontend/
│   ├── templates/
│   │   ├── index.html         # Landing / homepage
│   │   ├── dashboard.html     # Product browsing dashboard
│   │   ├── product.html       # Product detail page
│   │   ├── cart.html          # Shopping cart
│   │   ├── home.html          # Post-login landing page
│   │   ├── login.html         # Login form
│   │   └── signup.html        # Registration form
│   └── static/                # Static assets (images etc.)
│
├── data/
│   └── products.json          # 12,000+ balanced product catalogue (Amazon Best Sellers)
│
├── scripts/
│   └── build_dataset.py       # One-time pipeline: CSV → products.json
│
├── LOGS/                      # Runtime logs (gitignored)
│   └── session.log
│
├── .env                       # Secrets — NOT committed to git
├── .gitignore
├── requirements.txt
├── server.py                  # Project entry point
└── README.md
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites

- Python 3.11+
- MySQL 8.0+ (running locally or via Docker)

### 2. Clone & Install Dependencies

```bash
git clone <your-repo-url>
cd RTRP
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the template and fill in your values:

```bash
# Edit .env with your actual credentials
```

`.env` file (already present — do **not** commit):

```ini
FLASK_DEBUG=0

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=gokart_db

GROQ_API_KEY=gsk_...   # Required for AI comparison
```

### 4. Start MySQL

Ensure MySQL is running. The app will auto-create the `gokart_db` database and `users` table on first start.

### 5. Run the App

```bash
python server.py
```

Open **http://localhost:3000** in your browser.

---

## 🗄️ Dataset

The product catalogue (`data/products.json`) contains **~12,000** products sourced from Amazon Best Sellers (2025), balanced across 6 categories:

| Category | Count |
|---|---|
| Electronics | up to 2,000 |
| Fashion | up to 2,000 |
| Home | up to 2,000 |
| Books | up to 2,000 |
| Beauty | up to 2,000 |
| Sports | up to 2,000 |

### Rebuilding the Dataset

If you have access to the raw Amazon Best Sellers CSV:

```bash
# Place the CSV under data/ecommerce-product-dataset-main/...
python scripts/build_dataset.py
```

---

## 🔌 API Reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/register` | Register a new user |
| `POST` | `/api/login` | Log in |
| `POST` | `/api/logout` | Log out |
| `GET` | `/api/me` | Current session info |

### Products
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/products` | `page`, `limit`, `search`, `category` | Paginated product list |
| `GET` | `/api/products/<id>` | — | Single product detail |
| `GET` | `/api/categories` | — | Category list with counts |

### Recommendations
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/recommendations/me` | `page`, `limit`, `location` | Personalised recs (auth required) |
| `GET/POST` | `/api/recommendations` | `page`, `limit` | Hybrid recommendations (auth required) |
| `GET` | `/api/curated` | `count` | Trending / personalised picks |
| `POST` | `/api/track` | body: `{id, cat}` | Track product interaction |

### AI
| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/api/compare` | `{products: [...], query: "..."}` | AI product comparison |

---

## 🏗️ Architecture

```
Browser (HTML/CSS/JS)
       │
       │  HTTP / Fetch API
       ▼
Flask Server (backend/server.py)
       │
       ├── DataProcessor          ← loads & indexes products.json at startup
       ├── RecommendationEngine   ← hybrid TF-IDF + popularity scoring
       ├── MySQL (PyMySQL)        ← user accounts
       └── GroqCloud API (optional)  ← AI product comparison
```

---

## 📋 Requirements

```
flask>=3.0
pymysql>=1.1
numpy>=1.26
scikit-learn>=1.4
openai>=1.30
python-dotenv>=1.0
```

---

## 🔒 Security Notes

- All credentials live in `.env` — never committed to source control
- Passwords are stored in plain text in MySQL (demo only — use hashing in production)
- GroqCloud key is optional; the comparison feature falls back gracefully

---

## 📝 License

This project is for academic/demo purposes.
