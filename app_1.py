import streamlit as st
import requests
import base64
import json
import time

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Project Chatbot",
    layout="wide"
)

# Theme toggle (Streamlit built-in)
if "theme" not in st.session_state:
    st.session_state.theme = "light"

st.markdown(
    f"""
    <style>
    body {{
        background-color: {"#0e1117" if st.session_state.theme=="dark" else "white"};
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# PROFILE NAME
# =========================================================

if "profile_name" not in st.session_state:
    st.session_state.profile_name = "surya"

st.title(f"🧠 Project Chatbot – {st.session_state.profile_name}")

# =========================================================
# DATABRICKS CONFIG
# =========================================================

DATABRICKS_HOST = "https://dbc-927300a1-adc8.cloud.databricks.com"
API_ENDPOINT = f"{DATABRICKS_HOST}/serving-endpoints/Project_chatbot/invocations"

JOB_ID = "615973198764755"
WORKSPACE_DIR = "/Workspace/Users/surya03062000@gmail.com/streamlit_uploads"

REQUEST_TIMEOUT = 120
MAX_LEN = 6000

if "DATABRICKS_TOKEN" not in st.secrets:
    st.error("❌ DATABRICKS_TOKEN missing")
    st.stop()

TOKEN = st.secrets["DATABRICKS_TOKEN"]

# =========================================================
# JOB HELPERS
# =========================================================

def run_job(params: dict):
    payload = {
        "job_id": JOB_ID,
        "notebook_params": params
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(
        f"{DATABRICKS_HOST}/api/2.1/jobs/run-now",
        headers=headers,
        json=payload,
        timeout=60
    )

    if r.status_code != 200:
        raise RuntimeError(r.text)

    return r.json()["run_id"]


def get_job_output(run_id):
    # wait a bit for job to finish
    time.sleep(4)

    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = requests.get(
        f"{DATABRICKS_HOST}/api/2.1/jobs/runs/get-output?run_id={run_id}",
        headers=headers,
        timeout=60
    )

    if r.status_code != 200:
        raise RuntimeError(r.text)

    return r.json().get("notebook_output", {}).get("result", "")

# =========================================================
# WORKSPACE UPLOAD
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

    r = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/import",
        headers=headers,
        json=payload,
        timeout=120
    )

    if r.status_code != 200:
        raise RuntimeError(r.text)

    return payload["path"]

# =========================================================
# CHAT MODEL
# =========================================================

def call_serving_endpoint(prompt: str):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {"inputs": prompt}

    r = requests.post(
        API_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    if r.status_code != 200:
        raise RuntimeError(r.text)

    return r.json()


def parse_response(resp):
    if isinstance(resp, dict) and resp.get("predictions"):
        preds = resp["predictions"]
        return preds[0] if isinstance(preds, list) else str(preds)
    return json.dumps(resp, indent=2)

# =========================================================
# SESSION STATE
# =========================================================

if "chat" not in st.session_state:
    st.session_state.chat = []

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.header("👤 Profile")
    st.session_state.profile_name = st.text_input(
        "Profile name",
        value=st.session_state.profile_name
    )

    st.divider()

    st.header("🌗 Theme")
    if st.button("Toggle Light / Dark"):
        st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"
        st.rerun()

    st.divider()

    st.header("📂 Upload Documents")
    files = st.file_uploader(
        "Select files",
        type=["pdf", "txt", "docx", "xlsx"],
        accept_multiple_files=True
    )

    if files and st.button("⬆️ Upload"):
        for f in files:
            try:
                ws_path = upload_to_workspace(f)
                run_job({"action": "ingest", "workspace_file_path": ws_path})
                st.success(f"Uploaded: {f.name}")
            except Exception as e:
                st.error(e)

    st.divider()

    st.header("📊 Files in Volume")

    if st.button("🔄 Refresh File List"):
        run_id = run_job({"action": "list"})
        output = get_job_output(run_id)
        st.session_state.files = output.splitlines()

    files_in_volume = st.session_state.get("files", [])

    if files_in_volume:
        selected_file = st.selectbox("Select file", files_in_volume)

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🗑 Delete"):
                run_job({"action": "delete", "file_name": selected_file})
                st.success("Deleted. Refresh list.")

        with col2:
            if st.button("🔁 Reprocess"):
                run_job({"action": "reprocess", "file_name": selected_file})
                st.success("Reprocess triggered.")

# =========================================================
# CHAT UI
# =========================================================

for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

question = st.chat_input("Ask your question...")

if question:
    st.session_state.chat.append(("user", question))
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = call_serving_endpoint(question)
                answer = parse_response(resp)
                st.markdown(answer)
                st.session_state.chat.append(("assistant", answer))
            except Exception as e:
                st.error(e)

if st.button("Clear Chat"):
    st.session_state.chat = []
    st.rerun()
