"""
Run indexer — populates PostgreSQL pgvector with historical failures and code changes.
Test case details are stored in PostgreSQL (not here).

Product name is derived from sample.log via FailureParser — the log and the
SQL schema are the single source of truth.  No product string is hardcoded here.
"""
import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env", override=False)
load_dotenv(_here.parents[1] / ".env", override=False)

if str(_here.parent) not in sys.path:
    sys.path.insert(0, str(_here.parent))

from indexer.indexer import code_changes_db, index_folder, index_postgres_data
from AIAgent.db import close_pool, init_pool
from AIAgent.parser import FailureParser


async def main():
    # --- Derive product name from sample.log (single source of truth) ----------
    _log_path = _here / "data" / "sample.log"
    _parsed = FailureParser().parse(str(_log_path))
    _product_name = _parsed.product_name
    
    if _product_name is None:
        raise RuntimeError(
            f"Could not extract 'Product Name:' from {_log_path}. "
            "Ensure the log contains a 'Product Name: <value>' line before running the indexer."
        )
    
    print(f"Product name read from sample.log: '{_product_name}'")
    
    await init_pool()
    try:
        # --- Index historical failures from PostgreSQL ----------------------
        print("\nIndexing historical failures directly into PostgreSQL pgvector...")
        await index_postgres_data(product_name=_product_name)
        
        # --- Index code changes from files ----------------------------------
        _data = _here / "data"
        print("\nIndexing code changes -> PostgreSQL pgvector (collection: code_changes)")
        index_folder(str(_data / "code_changes"), code_changes_db, product_name=_product_name)
        
        print("\nDone! pgvector is now populated.")
    finally:
        await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
