import streamlit as st
import requests
import io, json
import pdfplumber

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Databricks GPT-OSS Chatbot", layout="wide")
st.title("🧠 Project Chatbot (databricks-gpt-oss-120b)")

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


def call_chat_endpoint(messages, max_tokens, temperature, top_p):
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    # 🔥 THIS IS THE CRITICAL FIX
    payload = {
        "inputs": {
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "top_p": float(top_p)
        }
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
    if response is None:
        return "❌ Model returned empty response"

    if isinstance(response, dict):

        # MLflow / Databricks standard
        if response.get("predictions"):
            pred = response["predictions"][0]
            if isinstance(pred, dict):
                return pred.get("content") or pred.get("text") or json.dumps(pred)
            return str(pred)

        # OpenAI-style
        if response.get("choices"):
            return response["choices"][0]["message"]["content"]

        if response.get("raw_text"):
            return response["raw_text"]

        return json.dumps(response)

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

    max_tokens = st.slider(
        "Max Tokens",
        100, 1000, 300, step=50
    )

    temperature = st.slider(
        "Temperature",
        0.0, 1.0, 0.0, step=0.05
    )

    top_p = st.slider(
        "Top-P",
        0.1, 1.0, 1.0, step=0.05
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
# CHAT HISTORY
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
                    "Concise": "Answer concisely in bullet points.",
                    "Detailed": "Provide detailed explanation with examples.",
                    "Troubleshooter": "Explain root cause and resolution steps."
                }

                system_prompt = persona_map.get(persona, "")

                if ui_lang == "Tamil":
                    system_prompt += (
                        "\nAfter English answer, also provide short Tamil explanation."
                    )

                messages = []

                if system_prompt:
                    messages.append({
                        "role": "system",
                        "content": system_prompt
                    })

                if file_context:
                    messages.append({
                        "role": "system",
                        "content": f"Context:\n{file_context}"
                    })

                messages.append({
                    "role": "user",
                    "content": user_question
                })

                response = call_chat_endpoint(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p
                )

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
