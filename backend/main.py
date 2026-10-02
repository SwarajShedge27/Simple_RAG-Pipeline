import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import shutil
import logging
from contextlib import asynccontextmanager

import random
import asyncio
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from prometheus_fastapi_instrumentator import Instrumentator

from db import init_db
from pdf_processor import extract_pages_from_pdf, split_pages_into_chunks
from rag import store_chunks, answer_question
from aiops_agent import process_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down application...")

app = FastAPI(lifespan=lifespan)

# Prometheus Observability Instrumentator
Instrumentator().instrument(app).expose(app)

# Hyrum's Law Defense: Chaos/Jitter Middleware
# Injects a randomized delay to prevent clients from relying on fixed response timings.
@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    jitter = random.uniform(0.01, 0.15) # 10ms to 150ms
    await asyncio.sleep(jitter)
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["*"],
    allow_headers=["*"],
)

v1_router = APIRouter(prefix="/v1")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def root():
    return {"status": "ok", "message": "Simple RAG backend is running."}


@v1_router.post("/webhook/alert")
async def alert_webhook(payload: dict):
    logger.info(f"Received Alert Webhook Payload: {payload}")
    # Process through the LangGraph AI Brain
    result = process_alert(payload)
    return {"status": "processed", "ai_brain_result": result}


@v1_router.post("/upload")
def upload_pdfs(files: list[UploadFile] = File(...)):
    logger.info(f"Received upload request for {len(files)} file(s).")
    results = []
    
    for file in files:
        if not file.filename.endswith(".pdf"):
            logger.warning(f"Rejected non-PDF file: {file.filename}")
            results.append({
                "filename": file.filename, 
                "status": "error", 
                "detail": "Only PDF files are accepted."
            })
            continue

        safe_filename = os.path.basename(file.filename)
        save_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        logger.info(f"Saving uploaded file to {save_path}...")
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            logger.info(f"Extracting text from {safe_filename}...")
            pages = extract_pages_from_pdf(save_path)

            if not pages:
                logger.error(f"No text extracted from {safe_filename}.")
                results.append({
                    "filename": file.filename, 
                    "status": "error", 
                    "detail": "Could not extract text from this PDF."
                })
                continue

            logger.info(f"Chunking text for {safe_filename}...")
            chunks = split_pages_into_chunks(pages, chunk_size=500, overlap=60)
            
            logger.info(f"Generating embeddings and storing {len(chunks)} chunks for {safe_filename}...")
            num_stored = store_chunks(file.filename, chunks)
            logger.info(f"Successfully stored {num_stored} chunks for {safe_filename}.")

            results.append({
                "filename": file.filename, 
                "status": "success", 
                "num_chunks": num_stored
            })

        except Exception as e:
            logger.error(f"Failed to process {safe_filename}: {e}", exc_info=True)
            results.append({
                "filename": file.filename, 
                "status": "error", 
                "detail": str(e)
            })
        finally:
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                    logger.debug(f"Cleaned up temporary file {save_path}")
                except OSError as e:
                    logger.warning(f"Failed to clean up {save_path}: {e}")

    return {
        "message": f"Processed {len(files)} files.",
        "results": results
    }

# Hyrum's Law Defense: Strict Schema (forbid extra fields)
class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str


@v1_router.post("/chat")
def chat(request: QuestionRequest):
    if not request.question.strip():
        logger.warning("Received empty chat question.")
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    logger.info(f"Received chat question: '{request.question}'")
    try:
        answer = answer_question(request.question)
        logger.info("Successfully generated answer.")
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Failed to answer question '{request.question}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(v1_router)
