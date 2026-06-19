import sys
import os
import time
import csv
import json
import math
import re
import requests
import optuna
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from backend.rag import retrieve_relevant_chunks, answer_question, store_chunks
from backend.pdf_processor import extract_pages_from_pdf, split_pages_into_chunks
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.output_parsers import PydanticOutputParser


def clean_and_parse_json(text: str, class_name: str):
    default_values = {
        "StatementsAnswers": [],
        "StatementFaithfulnessAnswers": [],
        "ContextRecallClassificationAnswers": [],
        "AnswerRelevanceClassification": {"question": "", "noncommittal": 0},
        "AnswerCorrectnessClassification": {"TP": [], "FP": [], "FN": []}
    }
    default_val = default_values.get(class_name, {})

    match = re.search(r'(\{.*\}|\[.*\])', text.strip(), re.DOTALL)
    cand = match.group(1) if match else text.strip()

    try:
        data = json.loads(cand)
        if isinstance(data, dict) and "type" in data and ("items" in data or "properties" in data):
            return default_val
        return data
    except Exception:
        return default_val


original_pydantic_parse = PydanticOutputParser.parse


def patched_pydantic_parse(self, text: str):
    pydantic_name = getattr(self, "pydantic_object", None)
    class_name = pydantic_name.__name__ if pydantic_name else "None"
    data = clean_and_parse_json(text, class_name)
    return original_pydantic_parse(self, json.dumps(data))


PydanticOutputParser.parse = patched_pydantic_parse

from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import faithfulness, answer_relevancy, context_recall, answer_correctness
from ragas.run_config import RunConfig

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", os.environ.get("EVAL_DATASET", "evaluation_dataset.csv"))
PDF_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "uploads", "Notes.pdf"))

LLM_MODEL = "llama3.1:8b"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"

ragas_llm = LangchainLLMWrapper(
    ChatOllama(
        model=os.environ.get("LLM_MODEL", "llama3.1:8b"),
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.0
    )
)

ragas_embeddings = LangchainEmbeddingsWrapper(
    GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001", 
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        output_dimensionality=768
    )
)

faithfulness.llm        = ragas_llm
answer_relevancy.llm    = ragas_llm
context_recall.llm      = ragas_llm
answer_correctness.llm  = ragas_llm

answer_relevancy.embeddings   = ragas_embeddings
answer_correctness.embeddings = ragas_embeddings

run_config = RunConfig(max_workers=1, max_retries=2, timeout=30)
for metric in [faithfulness, answer_relevancy, context_recall, answer_correctness]:
    metric.init(run_config)


def load_tuning_dataset(limit: int = 5) -> list[dict]:
    test_cases = []
    with open(DATASET_PATH, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            test_cases.append(row)
    return test_cases[:limit]


print(f"Extracting pages from PDF: {PDF_PATH}...")
pdf_pages = extract_pages_from_pdf(PDF_PATH)

test_cases = load_tuning_dataset(limit=5)

print("Finding relevant pages for tuning questions from existing database...")
validation_pages = set()
for case in test_cases:
    try:
        chunks = retrieve_relevant_chunks(case["question"].strip(), top_k=3)
        for c in chunks:
            p_num = c.get("page_number")
            if p_num:
                validation_pages.add(p_num)
    except Exception:
        pass

if not validation_pages:
    validation_pages = set(range(1, min(16, len(pdf_pages) + 1)))

print(f"Tuning will focus on re-chunking and re-embedding {len(validation_pages)} relevant pages: {sorted(list(validation_pages))}\n")


def objective(trial):
    chunk_size = trial.suggest_int("chunk_size", 300, 900, step=100)
    overlap = trial.suggest_int("overlap", 30, 90, step=30)
    temperature = trial.suggest_float("temperature", 0.0, 0.5, step=0.1)
    top_k = trial.suggest_int("top_k", 3, 10)
    use_rerank = trial.suggest_categorical("use_rerank", [True, False])
    rerank_top_n = trial.suggest_int("rerank_top_n", 1, 5)

    if use_rerank and rerank_top_n > top_k:
        rerank_top_n = top_k

    trial_overlap = overlap if overlap < chunk_size else chunk_size // 10

    print(f"\n--- Starting Trial #{trial.number} ---")
    print(f"Parameters: chunk_size={chunk_size}, overlap={trial_overlap}, temperature={temperature:.1f}, top_k={top_k}, use_rerank={use_rerank}, rerank_top_n={rerank_top_n}")


    print(f"  Re-chunking and embedding {len(validation_pages)} relevant pages...")
    pages_to_chunk = [p for p in pdf_pages if p["page_number"] in validation_pages]
    chunks = split_pages_into_chunks(pages_to_chunk, chunk_size=chunk_size, overlap=trial_overlap)
    store_chunks("Notes.pdf", chunks)
    print(f"  Stored {len(chunks)} temporary chunks in database.")
    
    trial_scores = []
    
    for idx, case in enumerate(test_cases, 1):
        question = case["question"].strip()
        expected_answer = case["expected_answer"].strip()

        print(f"  [{idx}/{len(test_cases)}] {question[:50]}...")

        chunks_retrieved = retrieve_relevant_chunks(question, top_k=top_k, use_rerank=use_rerank, rerank_top_n=rerank_top_n)
        answer = answer_question(question,top_k=top_k,relevant_chunks=chunks_retrieved,use_rerank=use_rerank,rerank_top_n=rerank_top_n,temperature=temperature,return_sources=False)

        row = {
            "question": question,
            "answer": answer,
            "contexts": [c.get("content", "") for c in chunks_retrieved],
            "ground_truth": expected_answer
        }

        def safe_score(metric, row_data):
            try:
                val = metric.score(row_data)
                return 0.0 if math.isnan(val) else val
            except Exception:
                return 0.0

        f_val = safe_score(faithfulness, row)
        ar_val = safe_score(answer_relevancy, row)
        ac_val = safe_score(answer_correctness, row)
        
        combined_score = (f_val + ar_val + ac_val) / 3.0
        trial_scores.append(combined_score)
        time.sleep(1)
        
    avg_score = sum(trial_scores) / len(trial_scores) if trial_scores else 0.0
    print(f"Trial #{trial.number} finished with Average Score: {avg_score:.4f}")
    return avg_score


if __name__ == "__main__":
    print("==========================================================")
    print("          Optuna Hyperparameter Tuning Script")
    print("==========================================================")
    print(f"Loading dataset from: {DATASET_PATH}")
    
    n_trials = 10
    
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    
    print("\n" + "="*18)
    print("TUNING SUMMARY")
    print("="*18)
    print(f"Best Trial Score : {study.best_value:.4f}")
    print("Best Parameters  :")
    for key, value in study.best_params.items():
        print(f"  {key}: {value}")
    print("="*18)

    best_params = study.best_params
    best_chunk_size = best_params.get("chunk_size", 500)
    best_overlap = best_params.get("overlap", 50)
    if best_overlap >= best_chunk_size:
        best_overlap = best_chunk_size // 10

    print(f"\nRestoring entire database chunks using best parameters (chunk_size={best_chunk_size}, overlap={best_overlap})...")
    best_chunks = split_pages_into_chunks(pdf_pages, chunk_size=best_chunk_size, overlap=best_overlap)
    store_chunks("Notes.pdf", best_chunks)
    print("Database chunks successfully restored to optimal settings!\n")
