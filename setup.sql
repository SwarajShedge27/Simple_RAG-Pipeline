
CREATE DATABASE ragdb;

\c ragdb

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL,          
    chunk_index INTEGER NOT NULL,      
    content     TEXT NOT NULL,         
    embedding   vector(768)           
);

-- Index for fast similarity search (cosine distance) ---
CREATE INDEX IF NOT EXISTS embedding_idx
ON document_chunks
USING ivfflat (embedding vector_cosine_ops) -- use cosine distance for similarity
WITH (lists = 100); -- Adjust 'lists' based on your dataset size for better performance


SELECT 'Database setup complete!' AS status;
