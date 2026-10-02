import os
import logging
import requests

logger = logging.getLogger(__name__)

def get_embedding(text: str) -> list[float]:
    api_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{api_base}/api/embeddings"
    
    payload = {
        "model": os.getenv("EMBED_MODEL", "nomic-embed-text"),
        "prompt": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["embedding"]
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to Ollama at {api_base}. Is Ollama running?")
        raise
    except requests.exceptions.Timeout:
        logger.error(f"Ollama embedding request timed out.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama embeddings: {e}", exc_info=True)
        raise

def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    
    # Ollama /api/embeddings doesn't natively support batching multiple prompts in a single call.
    # However, because it's extremely fast on GPU, we can iterate. 
    # For a real production app with huge batching, a thread pool can be used.
    embeddings = []
    for text in texts:
        embeddings.append(get_embedding(text))
    return embeddings
