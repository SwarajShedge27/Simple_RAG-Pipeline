import PyPDF2


def extract_text_from_pdf(file_path: str) -> str:
    
    text = ""

    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)

        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()

            if page_text:                    
                text += page_text + "\n"      

    return text


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

       
        if chunk.strip():
            chunks.append(chunk.strip())

        start += chunk_size - overlap

    return chunks
