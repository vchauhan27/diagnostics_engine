import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool

# Ensure .env is loaded if it hasn't been
_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env", override=False)
load_dotenv(_here.parents[1] / ".env", override=False)

host = os.environ.get("DB_HOST", "localhost")
port = os.environ.get("DB_PORT", "5432")
dbname = os.environ.get("DB_NAME", "tms_db")
user = os.environ.get("DB_USER", "postgres")
password = os.environ.get("DB_PASSWORD")  # Must be set explicitly via environment variable

db_url = os.environ.get("DATABASE_URL")
if db_url:
    # psycopg3 doesn't accept SQLAlchemy driver dialects like +asyncpg
    conninfo = db_url.replace("+asyncpg", "")
else:
    conninfo = f"host={host} port={port} dbname={dbname} user={user} password={password}"

# Create the pool synchronously so agents.py can pass it to AsyncPostgresSaver
pool = AsyncConnectionPool(conninfo=conninfo, min_size=1, max_size=20, open=False, kwargs={"autocommit": True})
_pool_opened = False

async def init_pool():
    global _pool_opened
    if not _pool_opened:
        await pool.open()
        _pool_opened = True

async def close_pool():
    global _pool_opened
    if _pool_opened:
        await pool.close()
        _pool_opened = False

def get_pool() -> Any:
    return pool
