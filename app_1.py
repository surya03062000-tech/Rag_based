import streamlit as st
import requests
import io, json
import pdfplumber

# =========================================================
# CONFIG
# =========================================================

if "DATABRICKS_TOKEN" not in st.secrets:
    st.error("❌ DATABRICKS_TOKEN not found in Streamlit secrets")
    st.stop()

DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]
DATABRICKS_TOKEN = "dapic0f4a95b1ec9a487058dc18ec8144bf1"

API_ENDPOINT = (
    "https://dbc-927300a1-adc8.cloud.databricks.com"
    "/serving-endpoints/Project_chatbot/invocations"
)

REQUEST_TIMEOUT = 120
MAX_LEN = 6000

st.set_page_config(page_title="Databricks GPT-OSS Chatbot", layout="wide")
st.title("🧠 Project Chatbot (databricks-gpt-oss-120b)")

# =========================================================
# HELPERS
# =========================================================

def extract_file_text(file):
    if not file:
        return ""
    content = file.read()

    # PDF
    if content[:4] == b"%PDF":
        pages = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    pages.append(f"[page {i+1}]\n{text}")
        return "\n\n".join(pages)

    # TXT
    return content.decode("utf-8", errors="ignore")


def call_chat_endpoint(messages, max_tokens, temperature, top_p):
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "top_p": float(top_p)
    }

    resp = requests.post(
        API_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    if resp.status_code != 200:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")

    return resp.json()

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
                # File context
                file_context = ""
                if uploaded_file and prepend_file:
                    file_context = extract_file_text(uploaded_file)[:3000]

                # Persona instruction
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

                messages = []

                if system_prompt:
                    messages.append({
                        "role": "system",
                        "content": system_prompt
                    })

                if file_context:
                    messages.append({
                        "role": "system",
                        "content": f"Context from uploaded file:\n{file_context}"
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

                # -------- Parse GPT-OSS response --------
                answer = "No response"

                if "choices" in response:
                    answer = response["choices"][0]["message"]["content"]
                elif "output" in response:
                    answer = response["output"]
                else:
                    answer = json.dumps(response)

                st.markdown(answer)
                st.session_state.chat.append(("assistant", answer))

            except Exception as e:
                st.error(f"❌ Error: {e}")

# =========================================================
# FOOTER
# =========================================================

if st.button("Clear Chat"):
    st.session_state.chat = []
    st.experimental_rerun()

