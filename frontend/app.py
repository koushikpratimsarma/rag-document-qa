import os
import re
import zipfile
from io import BytesIO
from pathlib import Path
import uuid
import requests
import streamlit as st
from pypdf import PdfReader

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="RAG Document QA",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Document-first RAG assistant"},
)

st.markdown(
    """
    <style>
    :root {
        --bg-main: #070b16;
        --bg-sidebar: #080d1a;
        --bg-card: #101827;
        --bg-card-soft: #132033;
        --bg-input: #172235;
        --border: rgba(148, 163, 184, 0.18);
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --accent: #3b82f6;
        --accent-2: #10b981;
        --danger: #ef4444;
        --warning: #f59e0b;
    }

    .stApp {
        background: linear-gradient(135deg, #070b16 0%, #0f172a 55%, #111827 100%);
        color: var(--text-main);
    }

    .block-container {
        padding-top: 1.2rem;
        max-width: 1100px;
    }

    h1, h2, h3, h4, h5, h6, p, label, span, div {
        color: var(--text-main) !important;
    }

    [data-testid="stSidebar"] {
        background: var(--bg-sidebar);
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] * {
        color: var(--text-main) !important;
    }

    .hero-card {
        background: linear-gradient(135deg, rgba(59,130,246,0.22), rgba(16,185,129,0.12));
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: 28px;
        margin-bottom: 22px;
        box-shadow: 0 20px 45px rgba(0,0,0,0.25);
    }

    .hero-title {
        font-size: 34px;
        font-weight: 800;
        margin-bottom: 8px;
        background: linear-gradient(90deg, #60a5fa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
        color: var(--text-muted) !important;
        font-size: 15px;
        line-height: 1.6;
    }

    .badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 999px;
        background: rgba(16,185,129,0.16);
        color: #6ee7b7 !important;
        border: 1px solid rgba(16,185,129,0.25);
        font-size: 12px;
        font-weight: 700;
        margin-left: 8px;
    }

    .card {
        background: rgba(15, 23, 42, 0.88);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 14px 35px rgba(0,0,0,0.22);
    }

    .answer-card {
        background: rgba(20, 31, 50, 0.95);
        border: 1px solid rgba(59,130,246,0.25);
        border-radius: 18px;
        padding: 18px;
        margin-bottom: 14px;
    }

    .question-pill {
        background: rgba(59,130,246,0.18);
        border: 1px solid rgba(59,130,246,0.28);
        border-radius: 14px;
        padding: 12px;
        margin-bottom: 10px;
    }

    .highlight {
        background: rgba(245,158,11,0.13);
        border-left: 4px solid var(--warning);
        padding: 14px;
        border-radius: 12px;
    }

    .stTextInput input,
    .stTextArea textarea,
    [data-baseweb="select"] {
        background: var(--bg-input) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
    }

    .stButton button {
        background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        padding: 0.55rem 1rem !important;
    }

    .stButton button:hover {
        filter: brightness(1.1);
        transform: translateY(-1px);
    }

    [data-testid="stFileUploader"] {
        background: rgba(15, 23, 42, 0.85);
        border: 1px dashed rgba(148,163,184,0.35);
        border-radius: 18px;
        padding: 16px;
    }

    [data-testid="stChatInput"] {
        background: rgba(15, 23, 42, 0.95);
        border-top: 1px solid var(--border);
    }

    [data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid var(--border);
        border-radius: 14px;
    }

    code, pre {
        background: #020617 !important;
        color: #dbeafe !important;
        border-radius: 12px !important;
    }

    hr {
        border-color: var(--border);
    }

    .small-muted {
        color: var(--text-muted) !important;
        font-size: 13px;
    }

    .sidebar-brand {
        font-size: 22px;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .sidebar-sub {
        color: var(--text-muted) !important;
        font-size: 12px;
        margin-bottom: 18px;
    }


.sidebar-section-title {
    color: var(--text-muted) !important;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    margin: 14px 0 8px 0;
    letter-spacing: 0.06em;
}

[data-testid="stSidebar"] .stButton button {
    justify-content: flex-start !important;
    text-align: left !important;
    background: rgba(15, 23, 42, 0.75) !important;
    border: 1px solid rgba(148, 163, 184, 0.16) !important;
    color: var(--text-main) !important;
    margin-bottom: 6px !important;
}

[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(59, 130, 246, 0.22) !important;
    border-color: rgba(59, 130, 246, 0.45) !important;
}

    </style>
    """,
    unsafe_allow_html=True,
)


def init_state():
    defaults = {
        "username": None,
        "session_id": None,
        "documents": [],
        "history": [],
        "preview_map": {},
        "show_citations": True,
        "sessions": [],
        "selected_session": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


def make_request(endpoint, method="GET", data=None, files=None):
    headers = {}
    if st.session_state.username:
        headers["X-Username"] = st.session_state.username

    try:
        if method == "GET":
            return requests.get(f"{BACKEND_URL}{endpoint}", headers=headers, params=data, timeout=60)
        if method == "POST":
            if files:
                return requests.post(f"{BACKEND_URL}{endpoint}", headers=headers, files=files, timeout=60)
            return requests.post(f"{BACKEND_URL}{endpoint}", headers=headers, json=data, timeout=60)
        if method == "DELETE":
            return requests.delete(f"{BACKEND_URL}{endpoint}", headers=headers, json=data, timeout=60)
    except Exception as exc:
        st.sidebar.error(f"Connection error: {exc}")
        return None


def login_user(username, password):
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(password) < 6:
        return False, "Password must be at least 6 characters"

    response = make_request("/auth/login", method="POST", data={"username": username, "password": password})
    if response and response.status_code == 200:
        st.session_state.username = username
        st.session_state.session_id = None
        return True, "Login successful"

    try:
        return False, response.json().get("detail", "Login failed") if response else "Unable to reach backend"
    except Exception:
        return False, "Login failed"


def register_user(username, password):
    username = username.strip()
    response = make_request("/auth/register", method="POST", data={"username": username, "password": password})
    if response and response.status_code == 200:
        st.session_state.username = username
        st.session_state.session_id = None
        return True, "Registration successful"
    return False, (response.json().get("detail") if response else "Unable to reach backend")


def load_documents():
    data = {}

    if st.session_state.session_id:
        data["session_id"] = st.session_state.session_id

    response = make_request("/documents/list", method="GET", data=data)

    if response and response.status_code == 200:
        st.session_state.documents = response.json().get("documents", [])
    else:
        st.session_state.documents = []



def load_sessions():
    response = make_request("/history/sessions", method="GET")

    if response and response.status_code == 200:
        data = response.json()

        if isinstance(data, dict):
            st.session_state.sessions = (
                data.get("sessions")
                or data.get("data")
                or data.get("history")
                or []
            )
        elif isinstance(data, list):
            st.session_state.sessions = data
        else:
            st.session_state.sessions = []

        # temporary debug
        # st.sidebar.write("Sessions response:", data)

    else:
        st.session_state.sessions = []


def load_session_history(session_id):
    response = make_request("/history/", method="GET", data={"session_id": session_id})

    if response and response.status_code == 200:
        data = response.json()
        history = data.get("history", [])

        st.session_state.history = [
            {
                "question": item.get("query", ""),
                "answer": item.get("answer", ""),
                "citations": item.get("retrieved_chunks", [])
            }
            for item in reversed(history)
        ]

        st.session_state.session_id = session_id
        st.session_state.selected_session = session_id
        load_documents()


def delete_current_chat():
    if not st.session_state.session_id:
        st.session_state.history = []
        return

    make_request(
        f"/history/session/{st.session_state.session_id}/clear",
        method="POST"
    )

    st.session_state.session_id = None
    st.session_state.selected_session = None
    st.session_state.history = []
    load_sessions()



def delete_document(document_id):
    response = make_request("/documents/delete", method="DELETE", data={"document_id": document_id})
    if response and response.status_code == 200:
        load_documents()
        st.success("Document removed")
    else:
        st.error("Could not remove the document")


def extract_text_preview(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(uploaded_file.getvalue()))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)[:4000]
        except Exception:
            return "Preview unavailable"

    if suffix == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(uploaded_file.getvalue())) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
            cleaned = re.sub(r"<[^>]+>", " ", xml)
            return re.sub(r"\s+", " ", cleaned)[:4000]
        except Exception:
            return "Preview unavailable"

    if suffix == ".pptx":
        try:
            with zipfile.ZipFile(BytesIO(uploaded_file.getvalue())) as archive:
                parts = []
                for name in archive.namelist():
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                        xml = archive.read(name).decode("utf-8", errors="ignore")
                        parts.append(re.sub(r"<[^>]+>", " ", xml))
                return re.sub(r"\s+", " ", " ".join(parts))[:4000]
        except Exception:
            return "Preview unavailable"

    return uploaded_file.getvalue().decode("utf-8", errors="ignore")[:4000]


def upload_files(files):
    if not st.session_state.session_id:
        st.session_state.session_id = str(uuid.uuid4())

    form_data = [("files", (f.name, f.getvalue(), f.type)) for f in files]

    headers = {}
    if st.session_state.username:
        headers["X-Username"] = st.session_state.username

    data = {
        "session_id": st.session_state.session_id
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/documents/upload_batch",
            headers=headers,
            files=form_data,
            data=data,
            timeout=120,
        )

        if response and response.status_code == 200:
            load_documents()
            st.success(f"Uploaded {len(files)} file(s)")
        else:
            st.error("Upload failed")

    except Exception as exc:
        st.error(f"Upload error: {exc}")


def ask_question(question):
    response = make_request(
        "/documents/query",
        method="POST",
        data={"query": question, "top_k": 4, "session_id": st.session_state.session_id},
    )
    if response and response.status_code == 200:
        data = response.json()
        if not st.session_state.session_id:
            st.session_state.session_id = data.get("session_id")
        st.session_state.history.append({
            "question": question,
            "answer": data.get("answer", ""),
            "citations": data.get("citations", [])
        })

        load_sessions()
        return data
    st.error("Unable to answer right now")
    return None


def render_sidebar():
    with st.sidebar:
        if st.session_state.username:
            st.success(f"Signed in as {st.session_state.username}")
            if st.button("Logout"):
                st.session_state.username = None
                st.session_state.session_id = None
                st.session_state.documents = []
                st.session_state.history = []
                st.rerun()

        st.divider()

        st.markdown("### 💬 Conversations")

        load_sessions()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("➕ New Chat", use_container_width=True):
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.selected_session = None
                st.session_state.history = []
                st.session_state.documents = []
                st.rerun()

        with col2:
            if st.button("🗑 Delete", use_container_width=True):
                delete_current_chat()
                st.rerun()

        st.markdown("<div class='sidebar-section-title'>Recent chats</div>", unsafe_allow_html=True)

        if st.session_state.sessions:
            for session in st.session_state.sessions:
                sid = session.get("session_id")

                title = (
                    session.get("title")
                    or session.get("first_question")
                    or session.get("query")
                    or f"Chat {sid[:8]}"
                )

                is_active = sid == st.session_state.selected_session        

                if st.button(
                    f"💬 {title[:32]}",
                    key=f"session_{sid}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    load_session_history(sid)
                    st.rerun()
        else:
            st.caption("No previous chats yet")

def render_hero():
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">⚡RAG Document QA</div>
            <div class="hero-subtitle">
                Upload your documents and ask grounded questions. 
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_document_panel():
    with st.expander("📤 Upload or manage documents", expanded=not st.session_state.documents):
        uploaded_files = st.file_uploader(
            "Choose files",
            accept_multiple_files=True,
            type=["pdf", "docx", "txt", "ppt", "pptx", "md"],
        )

        if uploaded_files:
            st.markdown(
                f"<div class='card'>Selected files: <b>{len(uploaded_files)}</b></div>",
                unsafe_allow_html=True,
            )

            for uploaded_file in uploaded_files:
                preview = extract_text_preview(uploaded_file)
                st.session_state.preview_map[uploaded_file.name] = preview

                with st.expander(f"Preview: {uploaded_file.name}"):
                    st.code(preview[:2000] if len(preview) > 2000 else preview)

            if st.button("Upload files", type="primary"):
                upload_files(uploaded_files)
                st.rerun()

        st.divider()
        st.subheader("📄 Uploaded documents")

        if st.session_state.documents:
            for doc in st.session_state.documents:
                col1, col2 = st.columns([5, 1])

                with col1:
                    st.markdown(
                        f"""
                        <div class='card'>
                            <b>📄 {doc['document_name']}</b><br>
                            <span class='small-muted'>
                                {doc['document_type']} • {doc['chunk_count']} chunks • {doc['upload_date']}
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with col2:
                    if st.button("Delete", key=f"del_{doc['document_id']}"):
                        delete_document(doc["document_id"])
                        st.rerun()
        else:
            st.caption("No documents uploaded yet.")


def render_chat_area():
    # ---------------- Header ----------------

    if st.session_state.history:
        for entry in st.session_state.history:

            st.markdown(
                f"""
                <div class="question-pill">
                    <b>You:</b> {entry['question']}
                </div>

                <div class="answer-card">
                    <b>Assistant:</b><br>
                    {entry['answer']}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if entry.get("citations"):
                with st.expander("View Retrieved Chunks"):
                    for index, citation in enumerate(entry["citations"], 1):

                        escaped_text = (
                            citation["text"]
                            .replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )

                        st.markdown(
                            f"""
                            <div class="highlight">
                                <b>Chunk {index}</b><br><br>
                                <b>📄 Document:</b> {citation['document_name']}<br>
                                <b>🎯 Similarity Score:</b> {citation['score']:.4f}<br><br>
                                <b>Retrieved Chunk</b><br><br>
                                {escaped_text}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        st.markdown("---")

        # ---------------- Uploaded Documents Review ----------------

    if st.session_state.documents:
        with st.expander("📄 Uploaded documents", expanded=True):
            for doc in st.session_state.documents:
                st.markdown(
                    f"""
                    <div class="card">
                        <b>📄 {doc['document_name']}</b><br>
                        <span class="small-muted">
                            {doc['document_type']} • {doc['chunk_count']} chunks • {doc['upload_date']}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.caption("No documents uploaded yet.")


    prompt = st.chat_input(
        "Ask your documents anything...",
        accept_file="multiple",
        file_type=["pdf", "docx", "txt", "ppt", "pptx", "md"],
    )

    if prompt:

        question = prompt.text
        uploaded_files = prompt.files

        if uploaded_files:
            upload_files(uploaded_files)
            load_documents()

        if question.strip():

            if not st.session_state.documents:
                st.warning("Please upload a document first.")
                return

            with st.spinner("Searching your documents..."):
                ask_question(question)

            st.rerun()

def render_workspace():
    render_hero()
    render_chat_area()


def render_auth_page():
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">⚡RAG Document QA</div>
            <div class="hero-subtitle">
                Login or create an account to upload documents and chat with your knowledge base.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        st.markdown("<div class='card'><h3>Welcome back</h3></div>", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            username = st.text_input("Username", key="auth_login_username")
            password = st.text_input("Password", type="password", key="auth_login_password")

            if st.button("Login", use_container_width=True):
                success, message = login_user(username, password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

        with tab2:
            username = st.text_input("Create username", key="auth_register_username")
            password = st.text_input("Create password", type="password", key="auth_register_password")

            if st.button("Create account", use_container_width=True):
                if len(username.strip()) < 3:
                    st.error("Username must be at least 3 characters")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = register_user(username, password)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


def main():
    if not st.session_state.username:
        render_auth_page()
        return

    render_sidebar()
    load_documents()
    render_workspace()


main()