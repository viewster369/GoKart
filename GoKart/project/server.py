import os
from backend.server import app, init_db


if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=3000, debug=debug_mode, use_reloader=False)
