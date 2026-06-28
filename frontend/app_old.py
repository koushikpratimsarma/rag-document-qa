import json
import requests
import streamlit as st

st.set_page_config(
    page_title="RAG Document QA System",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Professional RAG Document Q&A Engine"}
)

# Professional CSS styling
st.markdown("""
<style>
    * {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #e9ecef 100%);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        background: white;
        border-radius: 8px 8px 0 0;
        border: 1px solid #e0e0e0;
        margin-right: 2px;
        color: #495057;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        color: white !important;
        border: none;
    }
    
    .answer-container {
        background: white;
        padding: 25px;
        border-radius: 12px;
        border-left: 5px solid #3498db;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        margin: 20px 0;
    }
    
    .answer-text {
        font-size: 16px;
        line-height: 1.8;
        color: #2c3e50;
    }
    
    .upload-section {
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        margin: 20px 0;
    }
    
    .chunk-card {
        background: white;
        padding: 18px;
        border-radius: 10px;
        border-left: 4px solid #27ae60;
        margin: 15px 0;
        box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    }
    
    .chunk-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    
    .chunk-filename {
        font-weight: 600;
        color: #2c3e50;
        font-size: 15px;
    }
    
    .chunk-meta {
        display: flex;
        gap: 10px;
        margin: 10px 0;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
    }
    
    .badge-file {
        background: #e3f2fd;
        color: #1976d2;
    }
    
    .badge-source {
        background: #f3e5f5;
        color: #7b1fa2;
    }
    
    .chunk-content {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 6px;
        margin-top: 12px;
        color: #555;
        font-size: 14px;
        line-height: 1.6;
        border: 1px solid #e9ecef;
    }

    .header-section {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        padding: 40px 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
    }
    
    .header-title {
        font-size: 32px;
        font-weight: 700;
        margin: 0;
        color: white;
    }
    
    .header-subtitle {
        font-size: 14px;
        opacity: 0.9;
        margin: 8px 0 0 0;
        color: #e0e0e0;
    }
    
    .section-header {
        font-size: 20px;
        font-weight: 700;
        color: #2c3e50;
        margin: 25px 0 15px 0;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 10px 25px;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2980b9 0%, #1f618d 100%);
        box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
    }
    
    .sidebar-section {
        background: white;
        padding: 15px;
        border-radius: 10px;
        margin: 15px 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    }
    
    .success-box {
        background: #d4edda;
        border-left: 4px solid #28a745;
        padding: 15px;
        border-radius: 6px;
        color: #155724;
    }
    
    .error-box {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 15px;
        border-radius: 6px;
        color: #721c24;
    }

    .history-card {
        background: #ffffff;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #d8dee4;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        margin: 18px 0;
    }

    .history-meta {
        font-size: 13px;
        color: #555;
        margin-bottom: 10px;
    }

    .history-query {
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 12px;
    }

    .history-answer {
        font-size: 14px;
        color: #3b4b63;
        line-height: 1.7;
    }

    .top-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 20px;
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        color: white;
        padding: 14px 18px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.12);
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        margin-bottom: 16px;
    }

    .top-bar-left {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .top-bar-title {
        margin: 0;
        font-size: 20px;
        font-weight: 700;
        color: white;
    }

    .top-bar-subtitle {
        margin: 0;
        font-size: 13px;
        color: rgba(255,255,255,0.85);
    }

    .profile-widget {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 180px;
        justify-content: flex-end;
    }

    .profile-circle {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        font-weight: 700;
        color: white;
        background: linear-gradient(135deg, #3498db 0%, #2c3e50 100%);
        box-shadow: 0 4px 12px rgba(52, 152, 219, 0.18);
    }

    .profile-details {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 4px;
        text-align: right;
    }

    .profile-name {
        font-size: 13px;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
    }

    .profile-card {
        display: flex;
        align-items: center;
        gap: 10px;
        justify-content: flex-end;
    }

    .logout-small {
        background: rgba(255,255,255,0.15);
        color: white;
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        cursor: pointer;
        text-decoration: none;
        display: inline-block;
    }

    .logout-small:hover {
        background: rgba(255,255,255,0.22);
    }
    
    .info-text {
        color: #666;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar configuration
if "api_base" not in st.session_state:
    st.session_state.api_base = "http://localhost:8000"
if "document_uploaded" not in st.session_state:
    st.session_state.document_uploaded = False
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if "auth_token" not in st.session_state:
    st.session_state.auth_token = ""
if "username" not in st.session_state:
    st.session_state.username = ""
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
if "auth_message" not in st.session_state:
    st.session_state.auth_message = ""
if "history_data" not in st.session_state:
    st.session_state.history_data = []
if "history_message" not in st.session_state:
    st.session_state.history_message = ""
if "profile_menu_open" not in st.session_state:
    st.session_state.profile_menu_open = False

if not st.session_state.is_logged_in:
    st.sidebar.markdown("### ⚙️ Configuration")
    st.session_state.api_base = st.sidebar.text_input(
        "Backend URL",
        st.session_state.api_base,
        help="Enter the FastAPI backend URL"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 System Status")
    if st.sidebar.button("🔌 Check Connection"):
        try:
            response = requests.get(f"{st.session_state.api_base}/health", timeout=5)
            if response.ok:
                st.sidebar.success("✅ Backend is online and healthy")
            else:
                st.sidebar.error(f"❌ Backend returned status {response.status_code}")
        except Exception as e:
            st.sidebar.error(f"❌ Cannot reach backend: {str(e)}")

api_base = st.session_state.api_base

def load_saved_history():
    if not st.session_state.auth_token:
        return

    headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
    try:
        response = requests.get(f"{api_base}/history/", headers=headers, timeout=20)
        if response.ok:
            history_items = response.json().get("history", [])
            st.session_state.history_data = history_items
            st.session_state.chat_history = []
            st.session_state.display_history = []
            for item in history_items:
                st.session_state.chat_history.append({"role": "user", "content": item["query"]})
                st.session_state.display_history.append({"role": "user", "content": item["query"]})
                st.session_state.chat_history.append({"role": "assistant", "content": item["answer"]})
                st.session_state.display_history.append({"role": "assistant", "content": item["answer"]})
            st.session_state.history_message = ""
        else:
            st.session_state.history_message = response.json().get("detail", response.text)
    except Exception as e:
        st.session_state.history_message = str(e)


if st.session_state.is_logged_in:
    user_initial = st.session_state.username[:1].upper() if st.session_state.username else "U"
    st.markdown(
        f"<div class='top-bar'>"
        "<div class='top-bar-left'>"
        "<h2 class='top-bar-title'>RAG Document Q&A System</h2>"
        "<p class='top-bar-subtitle'>Ask questions about your documents with context-aware answers.</p>"
        "</div>"
        "<div class='profile-card' style='flex-direction: column; align-items: flex-end; gap: 10px;'>"
        "<div style='display: flex; align-items: center; gap: 12px; justify-content: flex-end;'>"
        f"<div class='profile-circle'>{user_initial}</div>"
        "<div class='profile-details'>"
        f"<p class='profile-name'>{st.session_state.username}</p>"
        "</div>"
        "</div>"
        "<a href='?logout=1' class='logout-small'>Logout</a>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

else:
    st.markdown('<h2 class="section-header">Welcome to RAG Document QA</h2>', unsafe_allow_html=True)
    st.markdown("<p class='info-text'>Please log in or register to continue to your document workspace.</p>", unsafe_allow_html=True)
    auth_tabs = st.tabs(["Login", "Register"])
    with auth_tabs[0]:
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", use_container_width=True, type="primary"):
            try:
                response = requests.post(
                    f"{api_base}/auth/login",
                    json={"username": login_username, "password": login_password},
                    timeout=20,
                )
                if response.ok:
                    data = response.json()
                    st.session_state.auth_token = data.get("access_token", "")
                    st.session_state.username = login_username
                    st.session_state.is_logged_in = True
                    st.session_state.auth_message = "Login successful."
                    load_saved_history()
                else:
                    st.session_state.auth_message = response.json().get("detail", response.text)
            except Exception as e:
                st.session_state.auth_message = str(e)
    with auth_tabs[1]:
        register_username = st.text_input("Username", key="register_username")
        register_password = st.text_input("Password", type="password", key="register_password")
        if st.button("Register", use_container_width=True, type="primary"):
            try:
                response = requests.post(
                    f"{api_base}/auth/register",
                    json={"username": register_username, "password": register_password},
                    timeout=20,
                )
                if response.ok:
                    data = response.json()
                    st.session_state.auth_token = data.get("access_token", "")
                    st.session_state.username = register_username
                    st.session_state.is_logged_in = True
                    st.session_state.auth_message = "Registration successful. You are now logged in."
                    load_saved_history()
                else:
                    st.session_state.auth_message = response.json().get("detail", response.text)
            except Exception as e:
                st.session_state.auth_message = str(e)
    if st.session_state.auth_message:
        st.info(st.session_state.auth_message)
    st.stop()

with st.sidebar:
    st.markdown("### 📄 Document Workspace")
    uploaded_file = st.file_uploader("Upload a PDF or text file", type=["pdf", "txt"])

    if uploaded_file is not None and uploaded_file.name != st.session_state.uploaded_file_name:
        if st.button("Upload Document", type="primary"):
            with st.spinner("Uploading..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                    response = requests.post(f"{api_base}/upload", files=files, timeout=30)
                    if response.ok:
                        st.session_state.document_uploaded = True
                        st.session_state.uploaded_file_name = uploaded_file.name
                        st.session_state.chat_history = []
                        st.session_state.display_history = []
                        load_saved_history()
                    else:
                        error_message = response.json().get("detail", response.text)
                        st.error(f"Upload failed: {error_message}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    st.markdown("---")
    st.markdown("### 🕘 Chat Summary")
    if st.session_state.chat_history:
        for message in st.session_state.chat_history[-10:]:
            role = "You" if message["role"] == "user" else "Assistant"
            st.write(f"**{role}:** {message['content'][:80]}{'...' if len(message['content']) > 80 else ''}")
    else:
        st.info("No conversation yet. Ask a question to see the history here.")

    if st.session_state.history_message:
        st.info(st.session_state.history_message)

    if st.session_state.history_data:
        if st.button("Clear My History", type="secondary"):
            try:
                headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
                response = requests.post(f"{api_base}/history/clear", headers=headers, timeout=20)
                if response.ok:
                    st.session_state.history_data = []
                    st.session_state.chat_history = []
                    st.session_state.display_history = []
                    st.session_state.document_uploaded = False
                    st.session_state.uploaded_file_name = None
                    st.session_state.history_message = "History cleared successfully."
                    st.rerun()
                else:
                    st.session_state.history_message = response.json().get("detail", response.text)
            except Exception as e:
                st.session_state.history_message = str(e)

for msg in st.session_state.display_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander("View source excerpts"):
                for i, (chunk, score) in enumerate(msg["sources"]):
                    st.markdown(f"**Excerpt {i+1}** — relevance score: `{score:.2f}`")
                    st.text(chunk[:400] + "..." if len(chunk) > 400 else chunk)

question = st.chat_input("Ask anything about the uploaded document...")
st.markdown("<div style='text-align: center; color: #999; font-size: 12px; margin-top: 15px; margin-bottom: 25px;'>RAG Document Q&A System v1.0 | Powered by LangChain & FastAPI</div>", unsafe_allow_html=True)

if question:
    with st.chat_message("user"):
        st.write(question)

    st.session_state.chat_history.append({"role": "user", "content": question})
    st.session_state.display_history.append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        with st.spinner("Searching document..."):
            try:
                payload = {"query": question, "top_k": 4}
                headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
                response = requests.post(f"{api_base}/query", json=payload, headers=headers, timeout=60)
                if response.ok:
                    data = response.json()
                    answer = data.get("answer", "I could not find an answer in the document.")
                    st.write(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                    st.session_state.display_history.append({"role": "assistant", "content": answer})
                    load_saved_history()
                    st.rerun()
                else:
                    error_message = response.json().get("detail", response.text)
                    st.error(f"{error_message}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

if not st.session_state.display_history and st.session_state.document_uploaded:
    st.info("Ask your first question to begin the document conversation.")
