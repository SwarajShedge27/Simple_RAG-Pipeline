import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432),
    "dbname": os.getenv("DB_NAME", "ragdb"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "Password"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    config_default = DB_CONFIG.copy()
    config_default["dbname"] = "postgres"

    try:
        conn = psycopg2.connect(**config_default)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s;", (DB_CONFIG["dbname"],))
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE "{DB_CONFIG["dbname"]}";')

        cur.close()
        conn.close()
    except Exception:
        pass

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise RuntimeError(
            "Failed to enable 'vector' extension. Please ensure 'pgvector' is installed on your PostgreSQL server. "
            f"Error details: {e}"
        ) from e

    embed_model = os.getenv("EMBED_MODEL", "BAAI/bge-base-en-v1.5")
    dimension = 1024 if "large" in embed_model.lower() else 768

    try:
        cur.execute("""
            SELECT atttypmod 
            FROM pg_attribute 
            WHERE attrelid = 'document_chunks'::regclass AND attname = 'embedding';
        """)
        row = cur.fetchone()
        if row and row[0] != dimension:
            print(f"Dimension mismatch in DB: expected {dimension}, found {row[0]}. Recreating table...")
            cur.execute("DROP TABLE IF EXISTS document_chunks CASCADE;")
            conn.commit()
    except Exception:
        conn.rollback()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id          SERIAL PRIMARY KEY,
            filename    TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content     TEXT NOT NULL,
            embedding   vector({dimension}),
            page_number INTEGER
        );
    """)

    cur.execute("""
        ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_number INTEGER;
    """)

    conn.commit()
    cur.close()
    conn.close()
