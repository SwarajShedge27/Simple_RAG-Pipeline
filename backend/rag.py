import os
import requests
from db import get_connection
from embeddings import get_embedding

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")


def store_chunks(filename: str, chunks: list[dict]) -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM document_chunks WHERE filename = %s", (filename,))

    for index, chunk in enumerate(chunks):
        chunk_text = chunk["content"]
        page_number = chunk["page_number"]
        embedding_vector = get_embedding(chunk_text)

        embedding_str = "[" + ",".join(str(v) for v in embedding_vector) + "]"

        cur.execute(
            """
            INSERT INTO document_chunks (filename, chunk_index, content, embedding, page_number)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (filename, index, chunk_text, embedding_str, page_number),
        )

    conn.commit()
    cur.close()
    conn.close()

    return len(chunks)


def retrieve_relevant_chunks(question: str, top_k: int = 5) -> list[dict]:
    query_embedding = get_embedding(question)
    query_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT content, filename, page_number
        FROM document_chunks
        ORDER BY embedding <=> %s::vector 
        LIMIT %s
        """,
        (query_str, top_k),
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "content": row[0],
            "filename": row[1],
            "page_number": row[2]
        }
        for row in rows
    ]


def answer_question(question: str) -> str:
    relevant_chunks = retrieve_relevant_chunks(question, top_k=5)

    if not relevant_chunks:
        return "I don't have any documents to search through yet. Please upload a PDF first."

    context_blocks = []
    citations = set()
    for chunk in relevant_chunks:
        filename = chunk["filename"]
        page_number = chunk["page_number"]
        
        context_blocks.append(f"[Document: {filename}, Page: {page_number}]\n{chunk['content']}")
        
        if page_number:
            citations.add(f"Page {page_number} of `{filename}`")
        else:
            citations.add(f"`{filename}`")

    context = "\n\n---\n\n".join(context_blocks)

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
    answer = data["response"].strip()

    lowered_answer = answer.lower()
    is_fallback = "don't know" in lowered_answer or "do not know" in lowered_answer or "no mention" in lowered_answer
    
    if citations and not is_fallback:
        sorted_citations = sorted(list(citations))
        sources_str = "\n\n**Sources:**\n" + "\n".join(f"- {c}" for c in sorted_citations)
        answer += sources_str

    return answer
