"""
db_config.py
────────────
MySQL connection settings loaded exclusively from environment variables.
Set values in the project .env file (never commit credentials to source control).
"""

import os

DB_HOST     = os.getenv("DB_HOST",     "localhost")
DB_USER     = os.getenv("DB_USER",     "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME",     "gokart_db")
DB_PORT     = int(os.getenv("DB_PORT", "3306"))
