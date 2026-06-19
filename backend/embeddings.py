import os
from sentence_transformers import SentenceTransformer

_model = None

def get_model():
    global _model
    if _model is None:
        model_name = os.getenv("EMBED_MODEL", "BAAI/bge-base-en-v1.5")
        _model = SentenceTransformer(model_name)
    return _model


def get_embedding(text: str) -> list[float]:
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
