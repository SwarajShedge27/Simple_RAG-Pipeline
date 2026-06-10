import os
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


def get_embedding(text: str) -> list[float]:
   
    url = f"{OLLAMA_BASE_URL}/api/embeddings"

    payload = {
        "model": EMBED_MODEL,
        "prompt": text,
    }

    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()         

    data = response.json()
    return data["embedding"]             
