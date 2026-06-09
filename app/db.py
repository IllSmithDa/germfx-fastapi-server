from __future__ import annotations

import os
from urllib.parse import urlencode
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# --- Option B: split env vars for Supabase/Postgres ---
# Expected variables (compatible with psql-style names):
#   PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE
PGUSER = os.getenv("SUPABASE_USERNAME")
PGPASSWORD = os.getenv("SUPABASE_PW")
PGHOST = os.getenv("SUPABASE_HOST")
PGPORT = os.getenv("SUPABASE_PORT")
PGDATABASE = os.getenv("SUPABASE_DB_NAME")

def _build_sqlalchemy_url_from_parts() -> str | None:
    if not all([PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE]):
        return None
    # Always require SSL for Supabase or remote Postgres by default
    query = {"sslmode": "require"}
    qs = urlencode(query)
    return f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

# Fallbacks (optional): support single-URL envs if present
# Prefer explicit parts; else try SUPABASE_DB_URL, DATABASE_URL, LOCAL_DATABASE_URL
DB_URL_FROM_PARTS = _build_sqlalchemy_url_from_parts()
RAW_URL = (
    DB_URL_FROM_PARTS
    or os.getenv("SUPABASE_DB_URL")
    or os.getenv("LOCAL_DATABASE_URL")
)

if not RAW_URL:
    raise RuntimeError(
        "No database configuration found. "
        "Set PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE in .env "
        "or provide SUPABASE_DB_URL / DATABASE_URL / LOCAL_DATABASE_URL."
    )

# Normalize url: if 'postgres://' scheme, upgrade to 'postgresql+psycopg2://'
def _normalize_sqlalchemy_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    # Ensure sslmode=require exists for supabase-like hosts if not present
    if ("supabase.co" in url or "supabase.net" in url) and "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url

DATABASE_URL = _normalize_sqlalchemy_url(RAW_URL)

# Helpful startup logs (mask password)
def _mask_url(u: str) -> str:
    try:
        # crude mask: hide credentials section between '://' and '@'
        if "://" in u and "@" in u:
            prefix, rest = u.split("://", 1)
            creds, tail = rest.split("@", 1)
            return f"{prefix}://***:***@{tail}"
    except Exception:
        pass
    return u

if "supabase" in DATABASE_URL:
    print("🔗 Using Supabase Database connection.")
else:
    print("🖥️ Using Database connection from parts/local env.")

print("DB URL (masked):", _mask_url(DATABASE_URL))

# Create engine with modest pool settings (leave headroom for other services)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency: yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
