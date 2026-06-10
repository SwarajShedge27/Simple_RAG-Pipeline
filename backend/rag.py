"""
rag.py - The core RAG logic

This file handles two main jobs:
  1. store_chunks()  - After PDF processing, save chunks + embeddings to pgvector
  2. answer_question() - At query time, find relevant chunks and ask the LLM

RAG flow recap:
  Upload  → extract text → chunk → embed each chunk → store in postgres
  Query   → embed query  → similarity search → retrieve top chunks → LLM → answer
"""

import os
import requests
from db import get_connection
from embeddings import get_embedding

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")


def store_chunks(filename: str, chunks: list[str]) -> int:
   
    conn = get_connection()
    cur = conn.cursor()

    # Optional: remove old chunks for this file so re-uploads don't duplicate
    cur.execute("DELETE FROM document_chunks WHERE filename = %s", (filename,))

    for index, chunk_text in enumerate(chunks):
        # Generate the embedding vector for this chunk
        embedding_vector = get_embedding(chunk_text)

        # Convert the Python list to the string format pgvector expects: "[0.1, 0.2, ...]"
        embedding_str = "[" + ",".join(str(v) for v in embedding_vector) + "]"

        cur.execute(
            """
            INSERT INTO document_chunks (filename, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s)
            """,
            (filename, index, chunk_text, embedding_str),
        )

    conn.commit()
    cur.close()
    conn.close()

    return len(chunks)


def retrieve_relevant_chunks(question: str, top_k: int = 5) -> list[str]:
    
    query_embedding = get_embedding(question)
    query_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT content
        FROM document_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_str, top_k),
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [row[0] for row in rows]


def answer_question(question: str) -> str:
    
    relevant_chunks = retrieve_relevant_chunks(question, top_k=5)

    if not relevant_chunks:
        return "I don't have any documents to search through yet. Please upload a PDF first."

    context = "\n\n---\n\n".join(relevant_chunks)

    prompt = f"""You are a helpful assistant. Answer the user's question using ONLY the context provided below.
If the answer is not in the context, say "I don't know based on the provided document."

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""

    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,        
    }

    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()

    data = response.json()
    return data["response"].strip()
