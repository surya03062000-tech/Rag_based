import streamlit as st
import requests
import io
import json
import pdfplumber
import base64

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Databricks GPT-OSS Chatbot", layout="wide")
st.title("🧠 Project Chatbot (Databricks GPT-OSS via MLflow)")

DATABRICKS_HOST = "https://dbc-927300a1-adc8.cloud.databricks.com"

# Databricks Job ID (DBFS → UC Volume)
MOVE_JOB_ID = "615973198764755"

DBFS_TMP_PATH = "dbfs:/tmp/streamlit_uploads"

# ---- Token (MANDATORY) ----
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
# DBFS UPLOAD (EXTERNAL APPS ALLOWED)
# =========================================================

def upload_to_dbfs(file_obj):
    content = file_obj.getvalue()
    encoded = base64.b64encode(content).decode("utf-8")

    payload = {
        "path": f"{DBFS_TMP_PATH}/{file_obj.name}",
        "overwrite": True,
        "contents": encoded
    }

    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}"
    }

    resp = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/dbfs/put",
        headers=headers,
        json=payload,
        timeout=60
    )

    if resp.status_code != 200:
        raise RuntimeError(resp.text)

    return payload["path"]

# =========================================================
# TRIGGER DATABRICKS JOB (MOVE → VOLUME)
# =========================================================

def trigger_move_job():
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}"
    }

    payload = {
        "job_id": MOVE_JOB_ID
    }

    resp = requests.post(
        f"{DATABRICKS_HOST}/api/2.1/jobs/run-now",
        headers=headers,
        json=payload,
        timeout=60
    )

    if resp.status_code != 200:
        raise RuntimeError(resp.text)

    return resp.json()

# =========================================================
# CHAT HELPERS (UNCHANGED LOGIC)
# =========================================================

def extract_file_text(file):
    if not file:
        return ""
    content = file.read()

    if content[:4] == b"%PDF":
        pages = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, page in enumerate(pdf.pages):
                txt = page.extract_text()
                if txt:
                    pages.append(f"[page {i+1}]\n{txt}")
        return "\n\n".join(pages)

    return content.decode("utf-8", errors="ignore")


def call_serving_endpoint(prompt: str):
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {"inputs": prompt}

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
    if not response:
        return "❌ Empty response from model"

    if isinstance(response, dict):
        if response.get("predictions") is not None:
            preds = response["predictions"]
            return preds[0] if isinstance(preds, list) else str(preds)
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
# SIDEBAR (UPLOAD + SETTINGS)
# =========================================================

with st.sidebar:
    st.header("📂 Upload Documents")

    uploaded_files = st.file_uploader(
        "Select files (PDF / TXT / DOCX / XLSX)",
        type=["pdf", "txt", "docx", "xlsx"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("⬆️ Upload to Databricks (DBFS)"):
            for f in uploaded_files:
                try:
                    path = upload_to_dbfs(f)
                    st.success(f"Uploaded → {path}")
                except Exception as e:
                    st.error(str(e))

    if st.button("🚀 Move Files to UC Volume"):
        try:
            trigger_move_job()
            st.success("Databricks job triggered successfully")
        except Exception as e:
            st.error(str(e))

    st.divider()

    st.header("⚙️ Chat Settings")

    persona = st.selectbox(
        "Persona",
        ["Concise", "Detailed", "Troubleshooter"]
    )

    ui_lang = st.selectbox(
        "Language",
        ["English", "Tamil"]
    )

    uploaded_file = st.file_uploader(
        "Attach file for chat context (PDF / TXT)",
        type=["pdf", "txt"]
    )

    prepend_file = st.checkbox("Use file as context")

# =========================================================
# CHAT UI
# =========================================================

for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

user_question = st.chat_input("Ask your question...")

# =========================================================
# CHAT LOGIC
# =========================================================

if user_question:
    st.session_state.chat.append(("user", user_question))
    with st.chat_message("assistant"):
        try:
            file_context = ""
            if uploaded_file and prepend_file:
                file_context = extract_file_text(uploaded_file)[:3000]

            persona_map = {
                "Concise": "Answer concisely in bullet points.",
                "Detailed": "Provide detailed explanation with examples.",
                "Troubleshooter": "Explain root cause and resolution steps."
            }

            prompt = persona_map.get(persona, "")
            if ui_lang == "Tamil":
                prompt += "\nAlso provide a short Tamil explanation."
            if file_context:
                prompt += "\n\nContext:\n" + file_context

            prompt += "\n\nUser question:\n" + user_question

            response = call_serving_endpoint(prompt)
            answer = parse_model_response(response)

            st.markdown(answer)
            st.session_state.chat.append(("assistant", answer))

        except Exception as e:
            st.error(str(e))

# =========================================================
# FOOTER
# =========================================================

if st.button("Clear Chat"):
    st.session_state.chat = []
    st.rerun()
