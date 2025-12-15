import streamlit as st
import requests
import io
import json
import pdfplumber
import base64

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Databricks GPT-OSS Chatbot",
    layout="wide"
)

st.title("🧠 Project Chatbot + Secure File Upload")

# =========================================================
# DATABRICKS CONFIG
# =========================================================

DATABRICKS_HOST = "https://dbc-927300a1-adc8.cloud.databricks.com"
API_ENDPOINT = f"{DATABRICKS_HOST}/serving-endpoints/Project_chatbot/invocations"

JOB_ID = "615973198764755"

# Workspace path (must exist)
WORKSPACE_DIR = "/Workspace/Users/surya03062000@gmail.com/streamlit_uploads"

REQUEST_TIMEOUT = 120
MAX_LEN = 6000

# ---- Token ----
if "DATABRICKS_TOKEN" not in st.secrets:
    st.error("❌ DATABRICKS_TOKEN missing in Streamlit secrets")
    st.stop()

TOKEN = st.secrets["DATABRICKS_TOKEN"]

# =========================================================
# CHATBOT – SERVING ENDPOINT
# =========================================================

def call_serving_endpoint(prompt: str):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
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
# FILE UPLOAD → WORKSPACE
# =========================================================

def upload_to_workspace(file_obj):
    encoded = base64.b64encode(file_obj.getvalue()).decode("utf-8")

    payload = {
        "path": f"{WORKSPACE_DIR}/{file_obj.name}",
        "format": "AUTO",
        "overwrite": True,
        "content": encoded
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    resp = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/import",
        headers=headers,
        json=payload,
        timeout=120
    )

    if resp.status_code != 200:
        raise RuntimeError(resp.text)

    return payload["path"]

# =========================================================
# TRIGGER JOB (PATH ONLY)
# =========================================================

def trigger_job(workspace_file_path):
    payload = {
        "job_id": JOB_ID,
        "notebook_params": {
            "workspace_file_path": workspace_file_path
        }
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
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
# SESSION STATE
# =========================================================

if "chat" not in st.session_state:
    st.session_state.chat = []

# =========================================================
# SIDEBAR – FILE UPLOAD ONLY
# =========================================================

with st.sidebar:
    st.header("📂 Upload Documents")

    uploaded_files = st.file_uploader(
        "Select files (PDF / TXT / DOCX / XLSX)",
        type=["pdf", "txt", "docx", "xlsx"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("🚀 Upload to Databricks"):
            for f in uploaded_files:
                try:
                    ws_path = upload_to_workspace(f)
                    trigger_job(ws_path)
                    st.success(f"✅ Uploaded & Job Triggered: {f.name}")
                except Exception as e:
                    st.error(f"❌ {f.name}: {e}")

# =========================================================
# CHAT UI
# =========================================================

for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

user_question = st.chat_input("Ask your question...")

# =========================================================
# CHAT LOGIC (SIMPLE)
# =========================================================

if user_question:
    if len(user_question) > MAX_LEN:
        st.error("❌ Message too long")
        st.stop()

    st.session_state.chat.append(("user", user_question))
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = call_serving_endpoint(user_question)
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
