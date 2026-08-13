# GermFx FastAPI Backend (Postgres via Supabase) + OpenFDA

This project is the backend for **GermFx**, a medication tracking and symptom logging app.  
It exposes APIs for users, medications, symptom logs, and integrates with the **OpenFDA** API.

---

## 🚀 Quick Start

### 1) Prerequisites
- **Python 3.10+**
- **Docker** (optional, for local Postgres — *not needed if using Supabase directly*)
- A **Supabase** account (Free plan is fine)

### 2) Install Python dependencies
```bash
pip install -r requirements.txt
# or
pip install fastapi uvicorn sqlalchemy psycopg2-binary httpx python-dotenv cryptography passlib[bcrypt]
```

### 3) Configure environment (.env)
Create a file named **`.env`** in the project root.

#### (A) Supabase Postgres connection
In Supabase Dashboard → Project → **Connect** → **Direct connection** (or **Session/PgBouncer**).  
Copy the Postgres URL and convert it for SQLAlchemy + psycopg2:
```
# Example (adjust host, user, password, db)
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
```
> `?sslmode=require` is recommended for Supabase. Alternatively, you can set this in SQLAlchemy’s `create_engine(connect_args={"sslmode": "require"})`.

#### (B) Security keys
We protect user identity with **deterministic email hashing (HMAC)** and optional **reversible encryption (Fernet)**.

Add the following to `.env`:
```
EMAIL_PEPPER=<set via generate_keys.py>
FERNET_KEY=<set via generate_keys.py>
```

Generate them with the helper script (see next section).

---

## 🔐 Generate secrets with `generate_keys.py`

We include a tiny script that produces **EMAIL_PEPPER** and **FERNET_KEY**.  
You can print them or write them directly into your `.env`.

```bash
# Print values
python generate_keys.py

# Or write to .env (creates file if missing)
python generate_keys.py --write .env
```

> **Do not** commit `.env` to your repo. Instead, commit an `.env.example` without secrets.

**What these keys do**  
- `EMAIL_PEPPER`: used in a keyed HMAC to create a deterministic, non-reversible `email_hash` for lookups/uniqueness.  
- `FERNET_KEY`: optional reversible encryption for `email_enc` (used only if you need to send mail).

---

## 🗄️ SQLAlchemy DB config (Supabase)

```python
# app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

> If you prefer passing SSL via code:
> ```python
> engine = create_engine(
>     DATABASE_URL,
>     connect_args={"sslmode": "require"},
>     pool_pre_ping=True,
> )
> ```

**FastAPI dependency**
```python
# app/deps.py
from typing import Generator
from app.db import SessionLocal

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()
```

---

## 🔑 Security: Password & Email Protection

- **Passwords**: hashed with **bcrypt** via `passlib` (`password_hash` column).  
- **Emails**: not stored in plaintext by default. We store:
  - `email_hash` (HMAC-SHA256 with `EMAIL_PEPPER`) for lookups + uniqueness.
  - Optional `email_enc` (Fernet) if you need to send emails (password reset, onboarding).

**Utilities**
```python
# app/security.py
import os, hmac, hashlib, base64
from cryptography.fernet import Fernet, InvalidToken

EMAIL_PEPPER = os.environ["EMAIL_PEPPER"]
FERNET_KEY = os.getenv("FERNET_KEY")  # optional
_f = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None

def canonicalize_email(s: str) -> str:
    return s.strip().lower()

def hash_email(email: str) -> str:
    msg = canonicalize_email(email).encode()
    key = EMAIL_PEPPER.encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def encrypt_email(email: str) -> str | None:
    if not _f: return None
    return _f.encrypt(canonicalize_email(email).encode()).decode()

def decrypt_email(token: str) -> str | None:
    if not _f: return None
    try:
        return _f.decrypt(token.encode()).decode()
    except InvalidToken:
        return None
```

---

## 🌐 External API: OpenFDA
- **Base URL:** https://api.fda.gov/drug/label.json
- Example:
```http
GET /medications/drug-info?drug=ibuprofen
```

---

## 🧭 Useful commands

```bash
# Run the server (auto-reload)
uvicorn app.main:app --reload

# Run server for mobile 
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


# Format / lint (if you use ruff/black)
ruff check . && black .
```

---

## 📌 Notes on Supabase connection headroom
Keep some DB connection **headroom** for Supabase internal services (Auth, Realtime, Studio), admin tools, and spikes. For example, if you have 3 workers, cap SQLAlchemy pool like `pool_size=5, max_overflow=5` which yields ~30 potential connections total.

---

## 🧪 API Docs
Go to `http://localhost:8000/docs` for interactive Swagger UI.



## 🗄️ Database Migrations with Alembic

We use **Alembic** to manage schema changes as your SQLAlchemy models evolve.

### 1) Install Alembic

```bash
pip install alembic
# If PATH issues:
python -m alembic --version
```

Add to `requirements.txt`:

```bash
pip freeze | grep alembic >> requirements.txt
```

### 2) Initialize Alembic

```bash
alembic init alembic
# or
python -m alembic init alembic
```

This creates:
```
alembic.ini
alembic/
  env.py
  script.py.mako
  versions/
```

### 3) Configure Alembic

Edit `alembic/env.py` to import your models and load `.env`:

```python
import os
from dotenv import load_dotenv
load_dotenv()

from app.db import Base
target_metadata = Base.metadata

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("LOCAL_DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
if DATABASE_URL and ("supabase.co" in DATABASE_URL or "supabase.net" in DATABASE_URL) and "sslmode=" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"
```

### 4) Creating & Running Migrations

After changing models:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Rollback if needed:

```bash
alembic downgrade -1
```

### 5) Supabase Tips

- Keep `sslmode=require` in your connection string or let `env.py` add it.
- Use small pool sizes to leave headroom for Supabase services.
