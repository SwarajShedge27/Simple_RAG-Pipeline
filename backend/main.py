import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import init_db
from pdf_processor import extract_pages_from_pdf, split_pages_into_chunks
from rag import store_chunks, answer_question


@asynccontextmanager
async def lifespan(app: FastAPI):
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
def root():
    return {"status": "ok", "message": "Simple RAG backend is running."}


@app.post("/upload")
def upload_pdfs(files: list[UploadFile] = File(...)):
    results = []
    
    for file in files:
        if not file.filename.endswith(".pdf"):
            results.append({
                "filename": file.filename, 
                "status": "error", 
                "detail": "Only PDF files are accepted."
            })
            continue

        save_path = os.path.join(UPLOAD_DIR, file.filename)
        
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            pages = extract_pages_from_pdf(save_path)

            if not pages:
                results.append({
                    "filename": file.filename, 
                    "status": "error", 
                    "detail": "Could not extract text from this PDF."
                })
                continue

            chunks = split_pages_into_chunks(pages, chunk_size=500, overlap=60)
            num_stored = store_chunks(file.filename, chunks)

            results.append({
                "filename": file.filename, 
                "status": "success", 
                "num_chunks": num_stored
            })

        except Exception as e:
            results.append({
                "filename": file.filename, 
                "status": "error", 
                "detail": str(e)
            })

    return {
        "message": f"Processed {len(files)} files.",
        "results": results
    }


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
