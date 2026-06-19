# 🧠 Simple RAG Application

A beginner-friendly **Retrieval-Augmented Generation (RAG)** app built with:

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI |
| Database | PostgreSQL + pgvector |
| PDF parsing | PyPDF2 |
| Embeddings | HuggingFace (`BAAI/bge-base-en-v1.5`) |
| LLM | Ollama (`llama3.1:8b`) |

---

## 📂 Folder Structure

```
simple-rag/
├── backend/
│   ├── main.py            # FastAPI app with /upload and /chat routes
│   ├── db.py              # PostgreSQL connection + table creation
│   ├── pdf_processor.py   # PDF text extraction + chunking
│   ├── embeddings.py      # Ollama embedding calls
│   ├── rag.py             # Store chunks + retrieve + answer question
│   └── requirements.txt
│
├── frontend/
│   ├── Home.py            # Page 1: Upload PDF
│   ├── pages/
│   │   └── Chat.py        # Page 2: Chat interface
│   └── requirements.txt
│
├── uploads/               # Uploaded PDFs are saved here temporarily
├── setup.sql              # One-time database setup script
└── README.md
```

---

## 🔄 How RAG Works (in plain English)

### When you upload a PDF:
1. The PDF text is extracted with **PyPDF2**
2. The text is split into small **chunks** (e.g. 500 characters/tokens each, with 50-char/token overlap)
3. Each chunk is sent to the local HuggingFace **BAAI/bge-base-en-v1.5** model, which converts it into a list of 768 numbers (an *embedding vector*) that represents its meaning
4. The chunk text + embedding are saved in **PostgreSQL using pgvector**

### When you ask a question:
1. Your question is also converted to an embedding vector (same model)
2. **pgvector** finds the stored chunks whose vectors are closest to your question's vector — these are the most *semantically relevant* chunks
3. Those chunks are bundled into a context prompt and sent to **Ollama's llama3.1:8b** LLM
4. The LLM reads the context and answers your question

This is RAG in a nutshell: **Retrieve** relevant context → **Augment** the prompt with it → **Generate** an answer.

---

## 🧠 Advanced Features: Reranking & Multi-Query Expansion

### 1. Two-Stage Retrieval (Reranking)
To improve the accuracy of retrieved context, the application implements a **two-stage retrieval pipeline**:
* **Stage 1 (Coarse Retrieval)**: Retrieves a larger candidate pool of documents from PostgreSQL via vector similarity search using `pgvector` distance matching (`db_limit = max(top_k * 3, 10)`).
* **Stage 2 (Fine Re-ranking)**: Passes candidate text-query pairs to a specialized Cross-Encoder model (`BAAI/bge-reranker-base`) to score their relevance.
* **Threshold Filtering**: Discards any retrieved chunks that fall below `RERANK_THRESHOLD` (default `0.35`). The top `rerank_top_n` scoring chunks are used as prompt context.

### 2. Multi-Query Expansion
To overcome variations in user phrasing, the backend translates the user query into multiple query variations using an LLM prompt. The vector database is searched using the embeddings of all generated queries, merging the retrieved candidates to improve retrieval coverage (recall).

---

## 🧪 Hyperparameter Tuning Suite

Located in the [`evaluation/`](file:///c:/Users/Swaraj Shedge/Desktop/simple-rag/evaluation) directory, this subsystem automatically optimizes the critical configurations of the RAG pipeline.

### 1. Optimization Goal
Tuning utilizes the **Optuna** library to maximize a combined validation metric calculated using **Ragas**:

```text
                  Faithfulness + Answer Relevancy + Answer Correctness
Combined Score = ------------------------------------------------------
                                           3
```

* **Faithfulness**: Measures prompt adherence and lack of hallucinations (LLM-as-a-judge).
* **Answer Relevancy**: Evaluates semantic alignment with the question.
* **Answer Correctness**: Scores factual accuracy against ground truth datasets.

### 2. Tuned Parameters Search Space
* `chunk_size` (300 to 900)
* `overlap` (30 to 90)
* `temperature` (0.0 to 0.5)
* `top_k` (3 to 10)
* `use_rerank` (True/False)
* `rerank_top_n` (1 to 5)

To run the tuning script:
```bash
python evaluation/tune.py
```

---

## 🛠️ Prerequisites

Make sure you have these installed before starting:

- **Python 3.10+**
- **PostgreSQL 14+**
- **pgvector extension** (see instructions below)
- **Ollama** (see instructions below)

---

## 📦 Installation Guide

### Step 1 — Install PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download and run the installer from https://www.postgresql.org/download/windows/

---

### Step 2 — Install pgvector

pgvector is a PostgreSQL extension that adds vector similarity search.

**macOS (Homebrew):**
```bash
brew install pgvector
```

**Ubuntu/Debian (from source):**
```bash
sudo apt install postgresql-server-dev-all build-essential git
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

**Windows:** See https://github.com/pgvector/pgvector#windows

---

### Step 3 — Set up the database

```bash
# Run the SQL setup script as the postgres superuser
psql -U postgres -f setup.sql
```

This creates the `ragdb` database, enables pgvector, and creates the `document_chunks` table.

If you get a password prompt, your postgres user's password is needed. If you haven't set one:
```bash
sudo -u postgres psql -f setup.sql     # Linux
```

---

### Step 4 — Install Ollama

Ollama lets you run LLMs locally.

**macOS / Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:** Download from https://ollama.com/download

Start Ollama (it runs as a background service):
```bash
ollama serve
```

Pull the model we need (the embedding model `BAAI/bge-base-en-v1.5` is downloaded automatically by the Python backend):
```bash
ollama pull llama3.1:8b         # LLM model        (~4.7 GB - default)
```

> 💡 You can use any other model (e.g. `llama3.2`, `llama3`, `mistral`, `phi3`). 
> Simply set the `LLM_MODEL` environment variable (or update the default in `backend/rag.py`) to match.

---

### Step 5 — Install Python dependencies

Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
```

Install backend dependencies:
```bash
cd backend
pip install -r requirements.txt
cd ..
```

Install frontend dependencies:
```bash
cd frontend
pip install -r requirements.txt
cd ..
```

---

## ▶️ Running the App

You need **three terminal windows** (or tabs):

**Terminal 1 — Ollama:**
```bash
ollama serve
```

**Terminal 2 — FastAPI backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```
Visit http://localhost:8000 — you should see `{"status":"ok",...}`.

**Terminal 3 — Streamlit frontend:**
```bash
cd frontend
streamlit run Home.py
```
Visit http://localhost:8501 in your browser.

---

## 🧪 Using the App

1. Open http://localhost:8501
2. On the **Home** page, upload a PDF and click **Create Embeddings**
3. Wait for the success message (may take 30–90 seconds depending on PDF size)
4. Click **Chat** in the sidebar
5. Ask questions about your document!

---

## ⚙️ Configuration

| Setting | File | Variable | Default |
|---|---|---|---|
| Database host | `backend/db.py` | `DB_HOST` | `localhost` |
| Database name | `backend/db.py` | `DB_NAME` | `ragdb` |
| DB user | `backend/db.py` | `DB_USER` | `postgres` |
| DB password | `backend/db.py` | `DB_PASSWORD` | `postgres` |
| LLM model | `backend/rag.py` | `LLM_MODEL` | `llama3.1:8b` |
| Chunk size | `backend/main.py` | `chunk_size` | `500` |
| Chunk overlap | `backend/main.py` | `overlap` | `50` |
| Retrieved chunks | `backend/rag.py` | `top_k` | `5` |

You can also set DB settings as environment variables before starting the backend.

---

## 🐛 Troubleshooting

**"Cannot connect to backend"**
→ Make sure `uvicorn main:app --reload --port 8000` is running in the backend folder.

**"Connection refused" on Ollama calls**
→ Run `ollama serve` in a separate terminal.

**"model not found" error**
→ Run `ollama pull llama3.1:8b`.

**"operator does not exist: vector" (pgvector error)**
→ Make sure pgvector is installed AND you ran `CREATE EXTENSION vector` in the `ragdb` database.

**PDF returns empty text**
→ The PDF may be scanned (image-only). Try a different, text-based PDF.

**Slow embedding generation**
→ This is normal — Ollama runs on CPU by default. A 10-page PDF takes about 1–3 minutes.

---

## 📚 Learning Resources

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Ollama documentation](https://ollama.com/docs)
- [FastAPI docs](https://fastapi.tiangolo.com)
- [Streamlit docs](https://docs.streamlit.io)
- [What is RAG? (Anthropic)](https://www.anthropic.com/index/claude-now-accessible-via-api)
