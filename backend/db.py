import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os

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
    # 1. Connect to the default 'postgres' database to check/create the target database
    config_default = DB_CONFIG.copy()
    config_default["dbname"] = "postgres"

    try:
        conn = psycopg2.connect(**config_default)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Check if database exists
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s;", (DB_CONFIG["dbname"],))
        exists = cur.fetchone()
        if not exists:
            print(f"Database '{DB_CONFIG['dbname']}' does not exist. Creating it...")
            cur.execute(f'CREATE DATABASE "{DB_CONFIG["dbname"]}";')
            print(f"Database '{DB_CONFIG['dbname']}' created successfully.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"ℹ️ Note: Could not verify/create database '{DB_CONFIG['dbname']}' automatically: {e}")
        print("Will try to connect directly. Ensure the database exists.")

    # 2. Connect to the target database and build tables/indices
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id          SERIAL PRIMARY KEY,
            filename    TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content     TEXT NOT NULL,
            embedding   vector(768)   -- nomic-embed-text produces 768-dim vectors
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS embedding_idx
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialised successfully.")

