# ADR 001: Architecture Modernization and Scalability

**Date:** 2026-09-22
**Status:** Accepted

## Context
The initial implementation of the Simple RAG Pipeline suffered from several architectural limitations:
1. **Performance Bottleneck:** Embeddings were generated on the CPU using `sentence-transformers`, causing unacceptable delays (minutes) when processing large PDFs.
2. **Database Inefficiency:** The FastAPI backend created a new PostgreSQL connection per query, leading to connection exhaustion under load.
3. **UI Limitations:** The Streamlit frontend lacked modern UI/UX paradigms, was difficult to customize, and required a heavy Python runtime.
4. **Environment Fragility:** Running services natively on the host machine resulted in inconsistent environments and dependency conflicts.

## Decisions

1. **GPU Offloading via Ollama:**
   We replaced local PyTorch CPU execution with direct API calls to the local Ollama instance using the `nomic-embed-text` model.
   *Rationale:* Ollama natively manages GPU acceleration. This offloads the heaviest mathematical operations to the RTX 4060, achieving a 10x-50x speedup.

2. **Database Connection Pooling:**
   We implemented `psycopg2.pool.SimpleConnectionPool` in `backend/db.py`.
   *Rationale:* Reusing established TCP connections to PostgreSQL drastically reduces query latency and prevents the database from rejecting connections under concurrent load.

3. **Frontend Migration to Next.js:**
   We deprecated Streamlit in favor of a modern Node.js/React application using Next.js (App Router) and Tailwind CSS.
   *Rationale:* React provides a significantly better, highly customizable user experience (resembling ChatGPT). Next.js API routes safely proxy requests to the backend, avoiding CORS issues, and a Node.js Docker container is much lighter to serve static HTML/JS assets.

4. **Containerization (Docker Compose):**
   The entire stack (PostgreSQL + pgvector, FastAPI Backend, Next.js Frontend) was containerized and orchestrated via `docker-compose.yml`.
   *Rationale:* Ensures 100% environment reproducibility across developer machines and production deployments.

## Consequences
- **Positive:** The system is now blazing fast, horizontally scalable, visually polished, and trivial to deploy (`docker compose up -d`).
- **Negative:** The system architecture is slightly more complex, introducing Node.js and Docker as mandatory dependencies for local development. However, the benefits heavily outweigh the initial learning curve.
