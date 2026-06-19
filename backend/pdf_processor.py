import PyPDF2
import re
from collections import Counter
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Document

def extract_pages_from_pdf(file_path: str) -> list[dict]:
    pages = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()

            if page_text:
                page_text = page_text.replace("\x00", "")

            if page_text and page_text.strip():
                lines = [line.strip() for line in page_text.split("\n") if line.strip()]
                pages.append({
                    "page_number": page_num + 1,
                    "lines": lines
                })
    
    if not pages:
        return []

    top_candidates = []
    bottom_candidates = []
    
    for page in pages:
        lines = page["lines"]
        if len(lines) >= 1:
            top_candidates.append(lines[0])
            if len(lines) >= 2:
                top_candidates.append(lines[1])
        if len(lines) >= 1:
            bottom_candidates.append(lines[-1])
            if len(lines) >= 2:
                bottom_candidates.append(lines[-2])

    top_counts = Counter(top_candidates)
    bottom_counts = Counter(bottom_candidates)
    
    min_occurrence = max(2, int(len(pages) * 0.15))
    repeating_headers = {line for line, count in top_counts.items() if count >= min_occurrence}
    repeating_footers = {line for line, count in bottom_counts.items() if count >= min_occurrence}

    page_num_patterns = [
        r"^(\bPage\b\s*)?[-–—]?\s*\d+\s*[-–—]?$", 
        r"^(\bPage\b\s*)?\d+\s*/\s*\d+$",         
        r"^(\bPage\b\s*)?\d+\s*of\s*\d+$"        
    ]
    
    def is_page_number(line: str) -> bool:
        return any(re.match(pat, line, re.IGNORECASE) for pat in page_num_patterns)

    cleaned_pages = []
    for page in pages:
        lines = page["lines"]
        cleaned_lines = []
        
        for idx, line in enumerate(lines):
           
            is_header_pos = idx < 2

            is_footer_pos = idx >= len(lines) - 2

            should_filter = False
            
            if is_header_pos and (line in repeating_headers or is_page_number(line)):
                should_filter = True
            elif is_footer_pos and (line in repeating_footers or is_page_number(line)):
                should_filter = True
            elif is_page_number(line): 
                should_filter = True

            if not should_filter:
                cleaned_lines.append(line)
        
        cleaned_pages.append({
            "page_number": page["page_number"],
            "text": "\n".join(cleaned_lines)
        })

    return cleaned_pages


def split_pages_into_chunks(pages: list[dict], chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    splitter = SentenceSplitter(chunk_size=chunk_size,chunk_overlap=overlap)

    all_chunks = []
    for page in pages:
        page_num = page["page_number"]
        page_text = page["text"]

        llama_doc = Document(text=page_text)
        nodes = splitter.get_nodes_from_documents([llama_doc])

        for node in nodes:
            all_chunks.append({
                "page_number": page_num,
                "content": node.get_content()
            })

    return all_chunks

def extract_text_from_pdf(file_path: str) -> str:
    pages = extract_pages_from_pdf(file_path)
    return "\n".join(p["text"] for p in pages)
