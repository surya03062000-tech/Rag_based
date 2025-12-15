import streamlit as st
import requests
import base64
import os

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Databricks Secure Upload", layout="wide")
st.title("🧠 Project Chatbot – Secure File Upload (Workspace → Volume)")

DATABRICKS_HOST = "https://dbc-927300a1-adc8.cloud.databricks.com"
JOB_ID = "615973198764755"   # your job id

# Workspace path (external REST allowed)
WORKSPACE_DIR = "/Workspace/Users/surya03062000@gmail.com/streamlit_uploads"

if "DATABRICKS_TOKEN" not in st.secrets:
    st.error("❌ DATABRICKS_TOKEN missing in Streamlit secrets")
    st.stop()

TOKEN = st.secrets["DATABRICKS_TOKEN"]

# =========================================================
# 1️⃣ UPLOAD TO WORKSPACE FILES
# =========================================================

def upload_to_workspace(file_obj):
    content = base64.b64encode(file_obj.getvalue()).decode("utf-8")

    payload = {
        "path": f"{WORKSPACE_DIR}/{file_obj.name}",
        "format": "AUTO",
        "overwrite": True,
        "content": content
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
# 2️⃣ TRIGGER JOB (ONLY PATH PASSED – SMALL)
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
# UI
# =========================================================

st.sidebar.header("📂 Upload Files")

uploaded_files = st.sidebar.file_uploader(
    "Select files (PDF / TXT / DOCX / XLSX)",
    type=["pdf", "txt", "docx", "xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    if st.sidebar.button("🚀 Upload to Databricks"):
        for f in uploaded_files:
            try:
                ws_path = upload_to_workspace(f)
                trigger_job(ws_path)
                st.sidebar.success(f"✅ Uploaded & Job Triggered: {f.name}")
            except Exception as e:
                st.sidebar.error(f"❌ {f.name}: {e}")

st.markdown(
"""
### ✅ Secure upload flow (FINAL)

1. File uploaded to **Databricks Workspace**
2. Job triggered with **file path only**
3. Job copies file to  
   **/Volumes/llm/rag/pdf_vol**

✔ No DBFS  
✔ No large params  
✔ No forbidden APIs  
✔ Enterprise-safe
"""
)

