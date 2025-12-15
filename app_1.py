import streamlit as st
import requests
import os, io, json
from datetime import datetime
import pdfplumber

# ---------------- CONFIG ----------------
DATABRICKS_TOKEN = st.secrets.get("DATABRICKS_TOKEN", "dapic0f4a95b1ec9a487058dc18ec8144bf1")
API_ENDPOINT = "https://dbc-927300a1-adc8.cloud.databricks.com/serving-endpoints/Project_chatbot/invocations"

REQUEST_TIMEOUT = 120
MAX_LEN = 6000

st.set_page_config(page_title="Databricks Chatbot", layout="wide")
st.title("🧠 Project Chatbot (Databricks Serving Endpoint)")

# ---------------- HELPERS ----------------
def extract_file_text(file):
    if not file:
        return ""
    content = file.read()
    if content[:4] == b"%PDF":
        texts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, p in enumerate(pdf.pages):
                t = p.extract_text()
                if t:
                    texts.append(f"[page {i+1}]\n{t}")
        return "\n\n".join(texts)
    else:
        return content.decode("utf-8", errors="ignore")


def call_serving_endpoint(prompt, top_k, max_tokens, temperature, top_p):
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "top_k": top_k,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        }
    }
    resp = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()

# ---------------- SESSION STATE ----------------
if "chat" not in st.session_state:
    st.session_state.chat = []

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("⚙️ Settings")
    persona = st.selectbox("Persona", ["Concise", "Detailed", "Troubleshooter"])
    ui_lang = st.selectbox("Language", ["English", "Tamil"])
    top_k = st.slider("Retriever Top-K", 1, 8, 4)
    max_tokens = st.slider("Max Tokens", 100, 1000, 300)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.0)
    top_p = st.slider("Top-P", 0.1, 1.0, 1.0)
    uploaded_file = st.file_uploader("Attach file (PDF/TXT)", type=["pdf", "txt"])
    prepend_file = st.checkbox("Use file as context")

# ---------------- CHAT UI ----------------
for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

user_question = st.chat_input("Ask your question...")

if user_question:
    if len(user_question) > MAX_LEN:
        st.error("Message too long")
    else:
        st.session_state.chat.append(("user", user_question))
        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    file_context = ""
                    if uploaded_file and prepend_file:
                        file_context = extract_file_text(uploaded_file)[:3000]

                    persona_map = {
                        "Concise": "Answer briefly with steps.",
                        "Detailed": "Give detailed explanation.",
                        "Troubleshooter": "Assume troubleshooting mode."
                    }

                    prompt_parts = [
                        persona_map.get(persona, "")
                    ]
                    if file_context:
                        prompt_parts.append("CONTEXT:\n" + file_context)
                    if ui_lang == "Tamil":
                        prompt_parts.append("Provide Tamil translation also.")
                    prompt_parts.append("User question:\n" + user_question)

                    final_prompt = "\n\n".join(prompt_parts)

                    response = call_serving_endpoint(
                        final_prompt, top_k, max_tokens, temperature, top_p
                    )

                    if "predictions" in response:
                        answer = response["predictions"][0]
                        if isinstance(answer, dict):
                            answer = answer.get("text", json.dumps(answer))
                    elif "text" in response:
                        answer = response["text"]
                    else:
                        answer = json.dumps(response)

                    st.markdown(answer)
                    st.session_state.chat.append(("assistant", answer))

                except Exception as e:
                    st.error(f"Error: {e}")

# ---------------- FOOTER ----------------
if st.button("Clear Chat"):
    st.session_state.chat = []
    st.experimental_rerun()
