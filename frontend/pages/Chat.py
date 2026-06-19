import streamlit as st
import requests

BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Simple RAG - Chat",
    page_icon="💬",
    layout="centered",
)

st.title("chat with Your Document")
st.write("Ask any question about the PDF you uploaded on the Home page.")
st.divider()


if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_question = st.chat_input("Ask a question about your document...")

if user_question:

    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.write(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    url=f"{BACKEND_URL}/chat",
                    json={"question": user_question},
                    timeout=1200,
                )

                if response.status_code == 200:
                    answer = response.json()["answer"]
                else:
                    error_detail = response.json().get("detail", "Unknown error")
                    answer = f" Backend error: {error_detail}"

            except requests.exceptions.ConnectionError:
                answer = "Cannot connect to the backend. Make sure FastAPI is running on port 8000."
            except Exception as e:
                answer = f" Unexpected error: {e}"

        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})


with st.sidebar:   
    st.markdown("### Tips")
    st.markdown("""
- Upload a PDF on the **Home** page first
- Ask specific questions about the document content
- The LLM only uses information from your PDF
    """)
