import os
from backend.server import app, init_db

# Optional: initialize database only when Vercel imports the app
# Use carefully if init_db() creates tables safely using IF NOT EXISTS
try:
    init_db()
except Exception as e:
    print("Database initialization skipped or failed:", e)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=3000, debug=debug_mode, use_reloader=False)