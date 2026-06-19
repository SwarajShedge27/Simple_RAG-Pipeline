import os
import requests
import time
from dotenv import load_dotenv
from db import get_connection
from embeddings import get_embedding, get_embeddings

load_dotenv()

def store_chunks(filename: str, chunks: list[dict]) -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM document_chunks WHERE filename = %s", (filename,))

    chunk_texts = [c["content"] for c in chunks]
    embedding_vectors = get_embeddings(chunk_texts)

    for i, (chunk, embedding_vector) in enumerate(zip(chunks, embedding_vectors)):
        chunk_text = chunk["content"]
        page_number = chunk["page_number"]
        embedding_str = "[" + ",".join(str(v) for v in embedding_vector) + "]"

        cur.execute(
            """
            INSERT INTO document_chunks (filename, chunk_index, content, embedding, page_number)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (filename, i, chunk_text, embedding_str, page_number),
        )

    conn.commit()
    cur.close()
    conn.close()

    return len(chunks)

_cached_ranker = None

def get_ranker():
    global _cached_ranker
    if _cached_ranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _cached_ranker = CrossEncoder("BAAI/bge-reranker-base")
        except ImportError:
            pass
    return _cached_ranker

def expand_query_multi(question: str, num_queries: int = 3) -> list[str]:
    
    prompt = f"""You are an AI assistant tasked with generating alternative versions of a search query.
    Generate {num_queries} different search queries to retrieve relevant documents for the question below.
    Provide each query on a new line. Do not number the queries, and do not write any introductory or concluding text.
    Original Question: {question}"""

    api_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{api_base}/v1/chat/completions"
    model_name = os.getenv("LLM_MODEL", "llama3.1:8b")

    for attempt in range(3):
        try:
            response = requests.post(
                url,
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "stream": False 
                },
                timeout=1200
            )
            response.raise_for_status()
            data = response.json()
            output = data["choices"][0]["message"]["content"].strip()
            
            queries = [q.strip().lstrip("1234567890.- ") for q in output.split("\n") if q.strip()]

            if question not in queries:
                queries.insert(0, question)
            return queries[:num_queries + 1]
        except Exception as e:
            print(f"Attempt {attempt+1}/3 failed during multi-query generation: {e}")
            if attempt < 2:
                time.sleep(2) 
            else:
                return [question]


def retrieve_relevant_chunks(question: str, top_k: int = 7, use_rerank: bool = True, rerank_top_n: int = 4, use_expansion: bool = True) -> list[dict]:
    if not use_expansion:
        queries = [question]
    else:
        queries = expand_query_multi(question, num_queries=3)
        print(f"Generated Queries for expansion: {queries}")

    conn = get_connection()
    cur = conn.cursor()

    db_limit = top_k
    ranker = None
    if use_rerank:
        ranker = get_ranker()
        if ranker is not None:
            db_limit = max(top_k * 3, 10)

    try:
        query_embeddings = get_embeddings(queries)
    except Exception as e:
        print(f"Error generating embeddings for queries: {e}")
        try:
            query_embeddings = [get_embedding(question)]
            queries = [question]
        except Exception:
            return []

    all_chunks = {}
    for q, query_embedding in zip(queries, query_embeddings):
        query_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        cur.execute(
            """
            SELECT content, filename, page_number, (embedding <=> %s::vector) AS distance
            FROM document_chunks
            ORDER BY embedding <=> %s::vector 
            LIMIT %s
            """,
            (query_str, query_str, db_limit),
        )
        rows = cur.fetchall()
        for row in rows: # [0] content, [1] filename, [2] page_number, and [3] distance
            chunk_content = row[0]
            similarity = round(1.0 - float(row[3]), 4) if row[3] is not None else 0.0
            
            if chunk_content not in all_chunks or similarity > all_chunks[chunk_content]["similarity"]: # saving relevent chuncks in all_chunks, those who have higher similarity gets in all_chuks
                all_chunks[chunk_content] = {
                    "content": chunk_content,
                    "filename": row[1],
                    "page_number": row[2],
                    "similarity": similarity
                }

    cur.close()
    conn.close()

    chunks = list(all_chunks.values())

    if use_rerank and ranker is not None and chunks:
        try:
            pairs = [[question, chunk["content"]] for chunk in chunks]
            scores = ranker.predict(pairs)
            for chunk, score in zip(chunks, scores):
                chunk["rerank_score"] = float(score)
            
            reranked_chunks = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
            
            threshold = float(os.getenv("RERANK_THRESHOLD", "0.35"))
            filtered_chunks = [c for c in reranked_chunks if c["rerank_score"] >= threshold]
            
            print(f"Reranked {len(reranked_chunks)} chunks; kept {len(filtered_chunks)} chunks matching threshold >= {threshold}")
            return filtered_chunks[:rerank_top_n]
        except Exception as e:
            print(f"Reranking error: {e}")
            return chunks[:top_k]

    chunks = sorted(chunks, key=lambda x: x["similarity"], reverse=True)
    return chunks[:top_k]


def answer_question(question: str, top_k: int = 7, relevant_chunks: list[dict] = None,use_rerank: bool = True,rerank_top_n: int = 4,temperature: float = 0.2,return_sources: bool = True) -> str:
    if relevant_chunks is None:
        relevant_chunks = retrieve_relevant_chunks(question, top_k=top_k, use_rerank=use_rerank, rerank_top_n=rerank_top_n)

    if not relevant_chunks:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM document_chunks")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        if count == 0:
            return "I don't have any documents to search through yet. Please upload a PDF first."
        return "I don't know based on the provided documents."

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

    prompt = f"""You are a helpful assistant. Answer the question directly and concisely using ONLY the facts explicitly mentioned in the context.
    - By default, your answer should be no more than three sentences. However, if the user explicitly requests a detailed explanation, elaboration, or steps, bypass this length limit and explain the concepts fully using only the context.
    - Do NOT use introductory phrases (such as "Based on the context", "According to the document", or "According to Page X").
    - Do NOT use any external knowledge; rely ONLY on the provided context.
    - If the context does not contain the direct answer to the question, state exactly: "I don't know based on the provided document." Do not try to extrapolate or force-fit an answer.

    CONTEXT:
    {context}

    QUESTION:
    {question}

    ANSWER:"""

    api_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{api_base}/v1/chat/completions"

    model_name = os.getenv("LLM_MODEL", "llama3.1:8b")
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }
    response = requests.post(url, json=payload, timeout=1200)
    response.raise_for_status()
    data = response.json()
    answer = data["choices"][0]["message"]["content"].strip()

    lowered_answer = answer.lower()
    is_fallback = "don't know" in lowered_answer or "do not know" in lowered_answer or "no mention" in lowered_answer
    
    if citations and not is_fallback and return_sources:
        sorted_citations = sorted(list(citations))
        sources_str = "\n\n**Sources:**\n" + "\n".join(f"- {c}" for c in sorted_citations)
        answer += sources_str

    return answer