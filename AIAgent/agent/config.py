import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from pydantic import SecretStr

# Load .env — local engine dir first, project root as fallback
_here = Path(__file__).resolve().parent.parent
load_dotenv(_here / ".env", override=False)
load_dotenv(_here.parent / ".env", override=False)

embeddings = OpenAIEmbeddings(
    model="baai/bge-m3",
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=SecretStr(os.getenv("OPENROUTER_API_KEY") or "dummy"),
    tiktoken_enabled=False,
    check_embedding_ctx_length=False,
)

from langchain_openrouter import ChatOpenRouter
llm= ChatOpenRouter(
         model="dots-studio/dots-3-note-preview:free",
         temperature=0,
     )

host = os.environ.get("DB_HOST", "localhost")
port = os.environ.get("DB_PORT", "5432")
dbname = os.environ.get("DB_NAME", "tms_db")
user = os.environ.get("DB_USER", "postgres")
password = os.environ.get("DB_PASSWORD")
db_url = os.environ.get("DATABASE_URL")

def _add_ssl_disable(url: str) -> str:
    """Append ssl=disable to a postgresql+asyncpg URL.

    asyncpg does NOT accept 'sslmode' as a query-string parameter — that is a
    libpq/psycopg convention.  The asyncpg-native parameter is 'ssl' and the
    value that disables TLS is 'disable'.  Using the wrong key causes:
        TypeError: connect() got an unexpected keyword argument 'sslmode'
    """
    # Strip any accidental legacy sslmode param first
    import re
    url = re.sub(r'[?&]sslmode=[^&]*', '', url)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}ssl=disable"


if db_url:
    conninfo = db_url.replace("+asyncpg", "")
    # PGVector async_mode requires the asyncpg driver explicitly
    async_conninfo = db_url if "+asyncpg" in db_url else db_url.replace("postgresql://", "postgresql+asyncpg://", 1).replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
else:
    auth = f"{user}:{password}" if password else user
    conninfo = f"postgresql://{auth}@{host}:{port}/{dbname}"
    async_conninfo = f"postgresql+asyncpg://{auth}@{host}:{port}/{dbname}"

# Disable SSL to prevent asyncpg from resolving ~/.postgresql/postgresql.key
# via Path.resolve() → os.getcwd(), which blockbuster flags as a blocking call.
async_conninfo = _add_ssl_disable(async_conninfo)

code_changes_db = PGVector(
    embeddings=embeddings,
    collection_name="code_changes",
    connection=async_conninfo,
    async_mode=True,
    create_extension=False,  # Extension already exists; asyncpg rejects multi-command batches
)
