import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import init_db
from pdf_processor import extract_text_from_pdf, split_into_chunks
from rag import store_chunks, answer_question


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Called automatically by FastAPI when the server starts."""
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)



@app.get("/")
def health_check():
    return {"status": "ok", "message": "Simple RAG backend is running."}


@app.post("/upload")
def upload_pdf(file: UploadFile = File(...)):
   
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        raw_text = extract_text_from_pdf(save_path)

        if not raw_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from this PDF. It may be image-only (scanned)."
            )

        chunks = split_into_chunks(raw_text, chunk_size=500, overlap=50)

        num_stored = store_chunks(file.filename, chunks)

        return {
            "message": "PDF processed successfully!",
            "filename": file.filename,
            "num_chunks": num_stored,
        }

    except Exception as e:
        # Surface the error message to the frontend
        raise HTTPException(status_code=500, detail=str(e))



class QuestionRequest(BaseModel):
    question: str


@app.post("/chat")
def chat(request: QuestionRequest):
   
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        answer = answer_question(request.question)
        return {"answer": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
