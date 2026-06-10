import PyPDF2


def extract_pages_from_pdf(file_path: str) -> list[dict]:
    pages = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                pages.append({
                    "page_number": page_num + 1,
                    "text": page_text
                })
    return pages


def split_text_smart(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks = []
    current = []
    curr_len = 0
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if curr_len + len(p) + (2 if current else 0) <= chunk_size:
            current.append(p)
            curr_len += len(p) + (2 if len(current) > 1 else 0)
        else:
            if current:
                chunks.append("\n\n".join(current))
            if len(p) > chunk_size:
                words = p.split(" ")
                sub_chunk = []
                sub_len = 0
                for w in words:
                    if sub_len + len(w) + (1 if sub_chunk else 0) <= chunk_size:
                        sub_chunk.append(w)
                        sub_len += len(w) + (1 if len(sub_chunk) > 1 else 0)
                    else:
                        if sub_chunk:
                            chunks.append(" ".join(sub_chunk))
                        sub_chunk = [w]
                        sub_len = len(w)
                if sub_chunk:
                    current = [" ".join(sub_chunk)]
                    curr_len = len(current[0])
                else:
                    current = []
                    curr_len = 0
            else:
                current = [p]
                curr_len = len(p)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def split_pages_into_chunks(pages: list[dict], chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    all_chunks = []
    for page in pages:
        page_num = page["page_number"]
        page_text = page["text"]
        chunks = split_text_smart(page_text, chunk_size=chunk_size, overlap=overlap)
        for chunk in chunks:
            all_chunks.append({
                "page_number": page_num,
                "content": chunk
            })
    return all_chunks


def extract_text_from_pdf(file_path: str) -> str:
    pages = extract_pages_from_pdf(file_path)
    return "\n".join(p["text"] for p in pages)


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    return split_text_smart(text, chunk_size, overlap)
