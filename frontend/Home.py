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

uploaded_files = st.file_uploader(
    label="Choose PDF files",
    type=["pdf"],
    accept_multiple_files=True,  
    help="Only text-based PDFs are supported.",
)

if uploaded_files:  
    st.success(f"**{len(uploaded_files)} file(s)** selected.")

    if st.button("Create Embeddings", use_container_width=True):
        with st.spinner("Processing PDFs and generating embeddings..."):
            try:
                
                files_payload = [
                    ("files", (f.name, f.getvalue(), "application/pdf"))
                    for f in uploaded_files
                ]
                
                response = requests.post(
                    url=f"{BACKEND_URL}/upload",
                    files=files_payload,
                    timeout=1200,  
                )

                if response.status_code == 200:
                    data = response.json()
                    st.success(f"**Batch processing complete!**")
                    
                    for res in data["results"]:
                        if res["status"] == "success":
                            st.write(f" `{res['filename']}`: Stored **{res['num_chunks']} chunks**")
                        else:
                            st.write(f" `{res['filename']}`: Error - {res['detail']}")
                            
                    st.info(" Head to the **Chat** page (sidebar) to ask questions about these documents.")
                else:
                    st.error(f"Error: {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to the backend. Make sure FastAPI is running on port 8000.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
else:
    st.info("Upload one or more PDFs above to get started.")


with st.sidebar:
    st.markdown("### How it works")
    st.markdown("""
1. Upload a PDF
2. Text is extracted & split into chunks
3. Each chunk is embedded with BAAI/bge-base-en-v1.5
4. Embeddings stored in PostgreSQL / pgvector
5. Go to Chat to ask questions!
    """)
