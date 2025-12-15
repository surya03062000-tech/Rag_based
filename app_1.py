import streamlit as st
import requests
import io
import json
import pdfplumber

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Databricks GPT-OSS Chatbot", layout="wide")
st.title("🧠 Project Chatbot (Databricks GPT-OSS via MLflow)")

# ---- Token (MANDATORY: Streamlit Secrets) ----
if "DATABRICKS_TOKEN" not in st.secrets:
    st.error("❌ DATABRICKS_TOKEN missing in Streamlit secrets")
    st.stop()

DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]

API_ENDPOINT = (
    "https://dbc-927300a1-adc8.cloud.databricks.com"
    "/serving-endpoints/Project_chatbot/invocations"
)

REQUEST_TIMEOUT = 120
MAX_LEN = 6000

# =========================================================
# HELPERS
# =========================================================

def extract_file_text(file):
    """Extract text from PDF or TXT."""
    if not file:
        return ""

    content = file.read()

    # PDF
    if content[:4] == b"%PDF":
        pages = []
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for i, page in enumerate(pdf.pages):
                    txt = page.extract_text()
                    if txt:
                        pages.append(f"[page {i+1}]\n{txt}")
        except Exception as e:
            return f"PDF parse error: {e}"

        return "\n\n".join(pages)

    # TXT
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def call_serving_endpoint(prompt: str):
    """
    Call Databricks Model Serving endpoint
    expecting STRING input → STRING output (MLflow pyfunc style)
    """
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    # 🔑 CRITICAL: STRING input only
    payload = {
        "inputs": prompt
    }

    resp = requests.post(
        API_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    if resp.status_code != 200:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")

    try:
        return resp.json()
    except Exception:
        return {"raw_text": resp.text}


def parse_model_response(response):
    """Safely extract text from MLflow-style response."""
    if not response:
        return "❌ Empty response from model"

    if isinstance(response, dict):
        # Expected MLflow output
        if response.get("predictions") is not None:
            preds = response["predictions"]
            if isinstance(preds, list) and len(preds) > 0:
                return str(preds[0])
            return str(preds)

        if response.get("raw_text"):
            return response["raw_text"]

        return json.dumps(response, indent=2)

    return str(response)

# =========================================================
# SESSION STATE
# =========================================================

if "chat" not in st.session_state:
    st.session_state.chat = []

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.header("⚙️ Settings")

    persona = st.selectbox(
        "Persona",
        ["Concise", "Detailed", "Troubleshooter"]
    )

    ui_lang = st.selectbox(
        "Language",
        ["English", "Tamil"]
    )

    uploaded_file = st.file_uploader(
        "Attach file (PDF / TXT)",
        type=["pdf", "txt"]
    )

    prepend_file = st.checkbox(
        "Use file as context",
        value=False
    )

# =========================================================
# CHAT HISTORY UI
# =========================================================

for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

user_question = st.chat_input("Ask your question...")

# =========================================================
# CHAT LOGIC
# =========================================================

if user_question:

    if len(user_question) > MAX_LEN:
        st.error("❌ Message too long")
        st.stop()

    # Show user message
    st.session_state.chat.append(("user", user_question))
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):

            try:
                # ---------- Context ----------
                file_context = ""
                if uploaded_file and prepend_file:
                    file_context = extract_file_text(uploaded_file)[:3000]

                persona_map = {
                    "Concise": "Answer concisely in clear bullet points.",
                    "Detailed": "Provide a detailed explanation with examples.",
                    "Troubleshooter": (
                        "Assume the user is troubleshooting. "
                        "Explain root cause and resolution steps."
                    )
                }

                system_prompt = persona_map.get(persona, "")

                if ui_lang == "Tamil":
                    system_prompt += (
                        "\nAfter the English answer, "
                        "also provide a short Tamil explanation."
                    )

                # ---------- FINAL STRING PROMPT ----------
                prompt_parts = []

                if system_prompt:
                    prompt_parts.append(system_prompt)

                if file_context:
                    prompt_parts.append("Context:\n" + file_context)

                prompt_parts.append("User question:\n" + user_question)

                final_prompt = "\n\n".join(prompt_parts)

                # ---------- CALL MODEL ----------
                response = call_serving_endpoint(final_prompt)

                answer = parse_model_response(response)

                st.markdown(answer)
                st.session_state.chat.append(("assistant", answer))

            except Exception as e:
                st.error(f"❌ Error: {e}")

# =========================================================
# FOOTER
# =========================================================

if st.button("Clear Chat"):
    st.session_state.chat = []
    st.rerun()
