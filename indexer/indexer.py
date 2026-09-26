import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env — local engine dir first, project root as fallback
_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env", override=False)
load_dotenv(_here.parent / ".env", override=False)

import pandas as pd
from langchain_community.document_loaders import (
    CSVLoader,
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import SecretStr

# ---- Load ----
# Pick the right loader based on file extension.

def load_document(path: str) -> list[Document]:
    ext = Path(path).suffix.lower()

    if ext == ".pdf":
        return PyPDFLoader(path).load()

    if ext == ".docx":
        return Docx2txtLoader(path).load()

    if ext == ".txt":
        return TextLoader(path).load()

    if ext == ".md":
        return UnstructuredMarkdownLoader(path).load()

    if ext == ".csv":
        return CSVLoader(path).load()

    if ext in (".html", ".htm"):
        return UnstructuredHTMLLoader(path).load()

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
        text = df.to_string(index=False)
        return [Document(page_content=text, metadata={"source": path})]

    if ext in (".png", ".jpg", ".jpeg"):
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path))
        return [Document(page_content=text, metadata={"source": path})]

    print(f"Skipping unsupported file: {path}")
    return []


def load_documents(folder: str) -> list[Document]:
    docs = []
    # rglob("*") walks the full directory tree; is_file() skips subdirectory
    # entries so they are never passed to load_document as unsupported paths.
    for file_path in Path(folder).rglob("*"):
        if not file_path.is_file():
            continue
        docs.extend(load_document(str(file_path)))
    print(f"Loaded {len(docs)} documents from {folder}")
    return docs


# ---- Split ----

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


# ---- Embed ----

embeddings = OpenAIEmbeddings(
    model="baai/bge-m3",
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=SecretStr(os.getenv("OPENROUTER_API_KEY") or "dummy"),
    tiktoken_enabled=False,
    check_embedding_ctx_length=False,
)


# ---- Store ----
host = os.environ.get("DB_HOST", "localhost")
port = os.environ.get("DB_PORT", "5432")
dbname = os.environ.get("DB_NAME", "tms_db")
user = os.environ.get("DB_USER", "postgres")
password = os.environ.get("DB_PASSWORD")
db_url = os.environ.get("DATABASE_URL")

if db_url:
    conninfo = db_url.replace("+asyncpg", "")
else:
    auth = f"{user}:{password}" if password else user
    conninfo = f"postgresql://{auth}@{host}:{port}/{dbname}"

code_changes_db = PGVector(
    embeddings=embeddings, 
    collection_name="code_changes",
    connection=conninfo
)


def _stable_chunk_id(source: str, chunk_index: int) -> str:
    """Return a deterministic ID for a chunk so re-runs upsert instead of duplicate."""
    raw = f"{source}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()


def index_documents(docs: list[Document], vector_store: PGVector, product_name: str | None = None):
    if not docs:
        print(f"No documents to index into '{vector_store.collection_name}'. Skipping.")
        return

    for doc in docs:
        if product_name:
            doc.metadata["product"] = product_name

    chunks = text_splitter.split_documents(docs)

    ids = [
        _stable_chunk_id(chunk.metadata.get("source", "db_or_folder"), i)
        for i, chunk in enumerate(chunks)
    ]

    vector_store.add_documents(chunks, ids=ids)
    print(f"Indexed {len(chunks)} chunks into '{vector_store.collection_name}' (upserted by stable id)")


def index_folder(folder: str, vector_store: PGVector, product_name: str | None = None):
    docs = load_documents(folder)
    index_documents(docs, vector_store, product_name)


async def index_postgres_data(product_name: str | None = None):
    from AIAgent.db import get_pool
    pool = get_pool()
    
    # 1. Update Defects
    print("Checking for defects needing embeddings...")
    defect_query = """
        SELECT defect_id, issue_type, title, description, module, resolution 
        FROM defects 
        WHERE embedding IS NULL
    """
    
    async with pool.connection() as conn, conn.cursor() as cursor:
            try:
                await cursor.execute(defect_query)
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                if rows:
                    print(f"Generating embeddings for {len(rows)} defects...")
                    for row in rows:
                        data = dict(zip(columns, row))
                        content = f"Title: {data['title']}\nModule: {data['module']}\nDescription: {data['description']}"
                        if data['resolution']:
                            content += f"\nResolution: {data['resolution']}"
                        
                        vector = await embeddings.aembed_query(content)
                        vector_str = "[" + ",".join(map(str, vector)) + "]"
                        
                        await cursor.execute(
                            "UPDATE defects SET embedding = %s::vector WHERE defect_id = %s",
                            (vector_str, data['defect_id'])
                        )
                    print("Updated defect embeddings.")
                else:
                    print("All defects already have embeddings.")
            except Exception as e:  # noqa: BLE001
                print(f"Warning: Could not update defects: {e}")
                
    # 2. Update Test Executions
    print("Checking for test executions needing embeddings...")
    te_query = """
        SELECT te.execution_id, te.status, te.notes, tc.title, tc.description
        FROM test_executions te
        JOIN test_cases tc ON te.test_case_id = tc.test_case_id
        WHERE te.status IN ('FAILED', 'BLOCKED') AND te.embedding IS NULL
    """
    
    async with pool.connection() as conn, conn.cursor() as cursor:
            try:
                await cursor.execute(te_query)
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                if rows:
                    print(f"Generating embeddings for {len(rows)} test executions...")
                    for row in rows:
                        data = dict(zip(columns, row))
                        content = f"Title: {data['title']}\nStatus: {data['status']}\nDescription: {data['description']}"
                        if data['notes']:
                            content += f"\nNotes: {data['notes']}"
                            
                        vector = await embeddings.aembed_query(content)
                        vector_str = "[" + ",".join(map(str, vector)) + "]"
                        
                        await cursor.execute(
                            "UPDATE test_executions SET embedding = %s::vector WHERE execution_id = %s",
                            (vector_str, data['execution_id'])
                        )
                    print("Updated test execution embeddings.")
                else:
                    print("All failed test executions already have embeddings.")
            except Exception as e:  # noqa: BLE001
                print(f"Warning: Could not update test executions: {e}")


if __name__ == "__main__":
    # Use run_indexer.py as the canonical entry point — it derives the
    # product name from sample.log (the single source of truth) instead
    # of hardcoding it here.
    import subprocess
    import sys
    subprocess.run([sys.executable, str(Path(__file__).parent / "run_indexer.py")], check=True)