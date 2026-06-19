import sys
import os
import time
import csv
import json
import math
import re
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from backend.rag import retrieve_relevant_chunks, answer_question
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.output_parsers import PydanticOutputParser
from langchain_ollama import ChatOllama

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
RESULTS_CSV  = os.path.join(BASE_DIR, "reports", "results.csv")
REPORT_JSON  = os.path.join(BASE_DIR, "reports", "report.json")

TOP_K           = 7
TEMPERATURE     = 0.2
LLM_MODEL       = "llama3.1:8b"
EMBED_MODEL     = "BAAI/bge-base-en-v1.5"
USE_RERANK      = True
RERANK_TOP_N    = 4

test_cases = []
with open(DATASET_PATH, mode="r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        test_cases.append(row)

print(f"Loaded {len(test_cases)} questions.\n")

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

faithfulness.llm = ragas_llm
answer_relevancy.llm = ragas_llm
context_recall.llm = ragas_llm
answer_correctness.llm = ragas_llm

answer_relevancy.embeddings   = ragas_embeddings
answer_correctness.embeddings = ragas_embeddings

run_config = RunConfig(max_workers=1, max_retries=2, timeout=30)
for metric in [faithfulness, answer_relevancy, context_recall, answer_correctness]:
    metric.init(run_config)

results  = []
latencies = []
total    = len(test_cases)

for idx, case in enumerate(test_cases, 1):
    question        = case["question"].strip()
    expected_answer = case["expected_answer"].strip()

    print(f"[{idx}/{total}] {question[:70]}")

    start   = time.perf_counter()
    chunks  = retrieve_relevant_chunks(question, top_k=TOP_K, use_rerank=USE_RERANK, rerank_top_n=RERANK_TOP_N)
    answer  = answer_question(question, top_k=TOP_K, relevant_chunks=chunks, use_rerank=USE_RERANK, rerank_top_n=RERANK_TOP_N, temperature=TEMPERATURE, return_sources=False)

    latency = time.perf_counter() - start

    print(f"Latency : {latency:.2f}s")

    row = {
        "question": question,
        "answer": answer,
        "contexts": [c.get("content", "") for c in chunks],
        "ground_truth": expected_answer
    }

    def safe_score(metric, row):
        try:
            val = metric.score(row)
            return 0.0 if math.isnan(val) else val
        except Exception as e:
            print(f"[WARN] {metric.name} failed: {e}")
            return 0.0

    f_score  = safe_score(faithfulness, row)
    ar_score = safe_score(answer_relevancy,row)
    cr_score = safe_score(context_recall,row)
    ac_score = safe_score(answer_correctness, row)

    print(f"Faithfulness={f_score:.2f}  Relevancy={ar_score:.2f}  Recall={cr_score:.2f}  Correctness={ac_score:.2f}\n")

    results.append({
        "question" : question,
        "expected_answer": expected_answer,
        "generated_answer": answer,
        "faithfulness": f_score,
        "answer_relevance": ar_score,
        "context_recall": cr_score,
        "answer_correctness": ac_score,
        "latency_sec": latency
    })
    latencies.append(latency)
    time.sleep(1)

df = pd.DataFrame(results)
os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
df.to_csv(RESULTS_CSV, index=False)
print(f"Results saved -> {RESULTS_CSV}")

summary = {
    "total_questions"   : total,
    "faithfulness"      : round(df["faithfulness"].mean(),4),
    "answer_relevance"  : round(df["answer_relevance"].mean(),4),
    "context_recall"    : round(df["context_recall"].mean(),4),
    "answer_correctness": round(df["answer_correctness"].mean(),4),
    "latency": {
        "avg_sec": round(sum(latencies) / total, 3),
        "min_sec": round(min(latencies),3),
        "max_sec": round(max(latencies),3),
    }
}

os.makedirs(os.path.dirname(REPORT_JSON), exist_ok=True)
with open(REPORT_JSON, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)
print(f"Report  saved -> {REPORT_JSON}")

print("\n" + "="*20)
print("EVALUATION SUMMARY")
print("="*20)
print(f"Total Questions   : {summary['total_questions']}")
print(f"Faithfulness      : {summary['faithfulness']}")
print(f"Answer Relevance  : {summary['answer_relevance']}")
print(f"Context Recall    : {summary['context_recall']}")
print(f"Answer Correctness: {summary['answer_correctness']}")
print("-"*20)
print(f"Avg Latency       : {summary['latency']['avg_sec']}s")
print(f"Min Latency       : {summary['latency']['min_sec']}s")
print(f"Max Latency       : {summary['latency']['max_sec']}s")
print("="*20)
