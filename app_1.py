import streamlit as st
import requests
import base64

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Databricks Secure Upload",
    layout="wide"
)

st.title("🧠 Project Chatbot – Secure File Upload")

# =========================================================
# DATABRICKS CONFIG
# =========================================================

DATABRICKS_HOST = "https://dbc-927300a1-adc8.cloud.databricks.com"

# ✅ Your Databricks Job ID (confirmed)
JOB_ID = "615973198764755"

# Token from Streamlit Secrets
if "DATABRICKS_TOKEN" not in st.secrets:
    st.error("❌ DATABRICKS_TOKEN missing in Streamlit secrets")
    st.stop()

DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]

# =========================================================
# HELPER : TRIGGER JOB WITH FILE CONTENT
# =========================================================

def trigger_upload_job(file_obj):
    """
    Sends file content (base64) to Databricks Job.
    Job will write file into Unity Catalog Volume.
    """

    # Read & encode file
    encoded_content = base64.b64encode(
        file_obj.getvalue()
    ).decode("utf-8")

    payload = {
        "job_id": JOB_ID,
        "notebook_params": {
            "file_name": file_obj.name,
            "file_base64": encoded_content
        }
    }

    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    resp = requests.post(
        f"{DATABRICKS_HOST}/api/2.1/jobs/run-now",
        headers=headers,
        json=payload,
        timeout=120
    )

    if resp.status_code != 200:
        raise RuntimeError(resp.text)

    return resp.json()

# =========================================================
# UI : FILE UPLOAD
# =========================================================

st.sidebar.header("📂 Upload Files to Databricks Volume")

uploaded_files = st.sidebar.file_uploader(
    "Select files",
    type=["pdf", "txt", "docx", "xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    if st.sidebar.button("🚀 Upload to Databricks"):
        for f in uploaded_files:
            try:
                trigger_upload_job(f)
                st.sidebar.success(f"✅ Uploaded: {f.name}")
            except Exception as e:
                st.sidebar.error(f"❌ {f.name} : {e}")

st.sidebar.info(
    """
🔐 Secure upload flow:
• Files are NOT written to DBFS
• File content sent to Databricks Job
• Job writes directly to UC Volume
"""
)

# =========================================================
# MAIN PAGE INFO
# =========================================================

st.markdown(
"""
### ✅ How this works (Secure – Enterprise Approved)

1. File selected in Streamlit
2. File content encoded (base64)
3. Databricks Job **615973198764755** triggered
4. Job writes file into  
   **/Volumes/llm/rag/pdf_vol**

This works even when:
- Public DBFS is disabled
- External REST write access is blocked
"""
)
