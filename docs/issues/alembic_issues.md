# Alembic & Supabase Sync Troubleshooting and Resolution Guide

This guide provides a detailed walkthrough of the troubleshooting process undertaken to resolve synchronization issues between **Alembic migrations** and the **Supabase PostgreSQL** database. The problem centered around Alembic migrations not updating Supabase with the new `enc_email` column that existed locally.

---

## 1. Problem Summary

Despite running Alembic migration commands successfully, Supabase was not reflecting updates made in the local development database. The `enc_email` column in the `User` table appeared locally but was absent in the Supabase schema. Even after using `alembic upgrade head` and `--sql` options, no visible changes were made to the Supabase environment.

---

## 2. Root Causes Identified

The investigation identified several potential issues that prevented Alembic from syncing properly:

1. Alembic was connected to the wrong database URL (local instead of Supabase).
2. The `alembic_version` table did not exist in Supabase, meaning Alembic could not track revisions.
3. The `--sql` flag generated SQL scripts instead of executing them.
4. Migration scripts were inconsistent with the live database schema.

---

## 3. How I originally attempted to fix

1. Double check the alembic.ini
2. recreate the migration history using 'alembic stamp head'
3. Re-run migrations using the following commands:

  alembic revision --autogenerate -m "Add email_enc to users"
  alembic upgrade head

4. The results did not prove to the fruitful as the table in the supabase application did not successfully update



## 4. Step-by-Step Resolution

1. Dropped all existing Supabase tables since no production data was present.  
2. Deleted the entire Alembic setup including the `alembic/` folder and `alembic.ini`.  
3. Reinstalled Alembic using:  
   ```bash
   pip install alembic

4. Re-initialize Alembic

  alembic init alembic

5. Edit the env.py file in the alembic foldier to point towards the Supabase database and conncect it to written models

  import os
  from alembic import context
  from app.models import Base
  from dotenv import load_dotenv

  load_dotenv()
  config = context.config
  config.set_main_option('sqlalchemy.url', os.getenv('DATABASE_URL'))
  target_metadata = Base.metadata


6. Run migrations using the following commands:

  alembic revision --autogenerate -m "Add email_enc to users"
  alembic upgrade head

7. Run SQL commands to check for alembic

  select * from public.alembic_version;
 
