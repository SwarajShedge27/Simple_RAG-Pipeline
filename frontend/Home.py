import streamlit as st
import requests

BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Simple RAG - Upload",
    page_icon="📄",
    layout="centered",
)

st.title("Simple RAG Application")
st.subheader("Step 1: Upload a PDF Document")
st.write("Upload any PDF and we'll extract its text, generate embeddings, and store them so you can chat with it.")

st.divider()


# File uploader


uploaded_file = st.file_uploader(
    label="Choose a PDF file",
    type=["pdf"],
    help="Only text-based PDFs are supported (not scanned images).",
)


# "Create Embeddings" button


if uploaded_file is not None:
    st.success(f"File selected: **{uploaded_file.name}**")

    if st.button("Create Embeddings", use_container_width=True):

        with st.spinner("Processing PDF and generating embeddings... This may take a minute."):
            try:
                
                response = requests.post(
                    url=f"{BACKEND_URL}/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                    timeout=900,   
                )

                if response.status_code == 200:
                    data = response.json()
                    st.success(f"Done! Stored **{data['num_chunks']} chunks** from `{data['filename']}`.")
                    st.info(" Head to the **Chat** page (sidebar) to ask questions about this document.")
                else:
                    
                    error_detail = response.json().get("detail", "Unknown error")
                    st.error(f"Error: {error_detail}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to the backend. Make sure FastAPI is running on port 8000.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
else:
    st.info("Upload a PDF above to get started.")


with st.sidebar:
    st.markdown("### How it works")
    st.markdown("""
1. Upload a PDF
2. Text is extracted & split into chunks
3. Each chunk is embedded with nomic-embed-text
4. Embeddings stored in PostgreSQL / pgvector
5. Go to Chat to ask questions!
    """)
