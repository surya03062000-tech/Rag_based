import streamlit as st
import requests
import io
import json
import pdfplumber

# =========================================================
# BASIC CONFIG
# =========================================================

st.set_page_config(page_title="Databricks RAG Chatbot", layout="wide")
st.title("🧠 Project Chatbot (Databricks GPT-OSS + Volume Upload)")

# =========================================================
# DATABRICKS CONFIG
# =========================================================

# Databricks Workspace
DATABRICKS_HOST = "https://dbc-927300a1-adc8.cloud.databricks.com"

# Serving endpoint (MLflow string-input model)
SERVING_ENDPOINT = f"{DATABRICKS_HOST}/serving-endpoints/Project_chatbot/invocations"

# Unity Catalog Volume path
VOLUME_PATH = "/Volumes/llm/rag/pdf_vol"

# Token from Streamlit Secrets
if "DATABRICKS_TOKEN" not in st.secrets:
    st.error("❌ DATABRICKS_TOKEN missing in Streamlit secrets")
    st.stop()

DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]

REQUEST_TIMEOUT = 120
MAX_LEN = 6000

# =========================================================
# HELPERS – FILE UPLOAD (UC VOLUME)
# =========================================================

def upload_file_to_volume(file_obj):
    """
    Upload file to Unity Catalog Volume using Databricks Files API
    """
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}"
    }

    target_path = f"{VOLUME_PATH}/{file_obj.name}"

    files = {
        "file": (file_obj.name, file_obj.getvalue())
    }

    params = {
        "path": target_path,
        "overwrite": "true"
    }

    resp = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/files/upload",
        headers=headers,
        files=files,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Upload failed for {file_obj.name}: {resp.text}"
        )

    return target_path

# =========================================================
# HELPERS – CHAT
# =========================================================

def call_serving_endpoint(prompt: str):
    """
    Call Databricks Serving Endpoint (MLflow string input)
    """
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt
    }

    resp = requests.post(
        SERVING_ENDPOINT,
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
    """
    Safely parse MLflow model response
    """
    if not response:
        return "❌ Empty response from model"

    if isinstance(response, dict):
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
# SIDEBAR – FILE UPLOAD + SETTINGS
# =========================================================

with st.sidebar:
    st.header("📂 Upload Files to Databricks Volume")

    uploaded_files = st.file_uploader(
        "Select files",
        type=["pdf", "txt", "docx", "xlsx"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("⬆️ Upload to /Volumes/llm/rag/pdf_vol"):
            for f in uploaded_files:
                try:
                    path = upload_file_to_volume(f)
                    st.success(f"✅ Uploaded: {path}")
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
                persona_map = {
                    "Concise": "Answer concisely in bullet points.",
                    "Detailed": "Provide detailed explanation with examples.",
                    "Troubleshooter": (
                        "Assume the user is troubleshooting. "
                        "Explain root cause and resolution steps."
                    )
                }

                system_prompt = persona_map.get(persona, "")

                if ui_lang == "Tamil":
                    system_prompt += (
                        "\nAfter the English answer, also provide a short Tamil explanation."
                    )

                final_prompt = f"{system_prompt}\n\nUser question:\n{user_question}"

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
