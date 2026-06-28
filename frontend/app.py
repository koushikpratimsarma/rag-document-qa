import json
import os
import requests
import streamlit as st
from datetime import datetime

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Page config
st.set_page_config(
    page_title="RAG Document QA System",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Professional RAG Document Q&A Engine with Advanced Search"}
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
    
    .chunk-card {
        background: white;
        padding: 18px;
        border-radius: 10px;
        border-left: 4px solid #27ae60;
        margin: 15px 0;
        box-shadow: 0 1px 6px rgba(0,0,0,0.08);
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
    
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        margin-right: 8px;
        margin-bottom: 8px;
    }
    
    .badge-file {
        background: #e3f2fd;
        color: #1976d2;
    }
    
    .badge-info {
        background: #f3e5f5;
        color: #7b1fa2;
    }
    
    .success-message {
        background: #d4edda;
        border-left: 4px solid #28a745;
        padding: 15px;
        border-radius: 6px;
        color: #155724;
        margin: 10px 0;
    }
    
    .error-message {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 15px;
        border-radius: 6px;
        color: #721c24;
        margin: 10px 0;
    }
    
    .info-message {
        background: #d1ecf1;
        border-left: 4px solid #0c5460;
        padding: 15px;
        border-radius: 6px;
        color: #0c5460;
        margin: 10px 0;
    }
    
    .history-card {
        background: white;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #d8dee4;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        margin: 18px 0;
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
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        color: white;
        padding: 14px 18px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.12);
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        margin-bottom: 16px;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 10px 25px;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2980b9 0%, #1f618d 100%);
        box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
    }
</style>
""", unsafe_allow_html=True)


# Session state management
def init_session_state():
    if "token" not in st.session_state:
        st.session_state.token = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []


init_session_state()


# Helper functions
def make_request(endpoint, method="GET", data=None, files=None):
    """Make request to backend API"""
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    
    url = f"{BACKEND_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=data)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, files=files)
            else:
                response = requests.post(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, json=data)
        
        return response
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None


def login_user(username, password):
    """Login user and get token"""
    response = make_request("/auth/login", method="POST", data={"username": username, "password": password})
    if response and response.status_code == 200:
        data = response.json()
        st.session_state.token = data["access_token"]
        st.session_state.username = username
        st.session_state.session_id = None
        return True, "Login successful"
    elif response:
        return False, response.json().get("detail", "Login failed")
    return False, "Connection error"


def register_user(username, password):
    """Register new user"""
    response = make_request("/auth/register", method="POST", data={"username": username, "password": password})
    if response and response.status_code == 200:
        data = response.json()
        st.session_state.token = data["access_token"]
        st.session_state.username = username
        st.session_state.session_id = None
        return True, "Registration successful"
    elif response:
        return False, response.json().get("detail", "Registration failed")
    return False, "Connection error"


def upload_document(files):
    """Upload one or more documents"""
    if len(files) == 1:
        endpoint = "/upload"
    else:
        endpoint = "/upload_batch"
    
    file_data = [("file", (f.name, f.getvalue(), f.type)) for f in files]
    response = make_request(endpoint, method="POST", files=file_data)
    return response


def query_documents(query, use_hybrid=True, use_reranking=True, metadata_filters=None):
    """Query documents"""
    data = {
        "query": query,
        "top_k": 5,
        "session_id": st.session_state.session_id,
        "use_hybrid_search": use_hybrid,
        "use_reranking": use_reranking,
        "metadata_filters": metadata_filters or {}
    }
    response = make_request("/query", method="POST", data=data)
    return response


def get_history():
    """Get user's query history"""
    response = make_request("/history/", method="GET")
    return response


def get_sessions():
    """Get user's conversation sessions"""
    response = make_request("/history/sessions", method="GET")
    return response


# Main UI
def render_auth_page():
    """Render authentication page"""
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class="header-section">
            <h1 class="header-title">RAG Document QA</h1>
            <p class="header-subtitle">Upload documents and ask intelligent questions powered by advanced search</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.subheader("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login", key="login_btn"):
                success, message = login_user(username, password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        
        with tab2:
            st.subheader("Register")
            username = st.text_input("Username", key="reg_username")
            password = st.text_input("Password", type="password", key="reg_password")
            password_confirm = st.text_input("Confirm Password", type="password", key="reg_password_confirm")
            
            if st.button("Register", key="register_btn"):
                if password != password_confirm:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = register_user(username, password)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    # Demo info
    st.info("📝 Create an account to save your query history and conversation sessions across sessions.")


def render_main_app():
    """Render main application"""
    # Top bar with user info
    st.markdown(f"""
    <div class="top-bar">
        <div>
            <h3 class="header-title" style="margin: 0; font-size: 24px;">RAG Document QA</h3>
            <p style="margin: 8px 0 0 0; font-size: 12px; color: #e0e0e0;">
                Advanced Search with Hybrid Methods & Re-ranking
            </p>
        </div>
        <div style="text-align: right; color: white;">
            <p style="margin: 0; font-size: 13px;"><strong>{st.session_state.username}</strong></p>
            <p style="margin: 4px 0 0 0; font-size: 12px; color: #e0e0e0;">Authenticated User</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Logout", key="logout_btn", help="Logout from your account"):
        st.session_state.token = None
        st.session_state.username = None
        st.session_state.session_id = None
        st.session_state.conversation_history = []
        st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload Documents", "❓ Query Documents", "📜 History", "⚙️ Settings"])
    
    with tab1:
        st.header("Upload Documents")
        st.info("Upload PDF or text documents to build your knowledge base. Multiple file upload is supported.")
        
        uploaded_files = st.file_uploader(
            "Choose documents to upload",
            type=["pdf", "txt"],
            accept_multiple_files=True,
            help="Upload one or more PDF or text files"
        )
        
        if uploaded_files:
            st.write(f"**Files selected:** {len(uploaded_files)}")
            for f in uploaded_files:
                st.write(f"- {f.name} ({f.size / 1024:.1f} KB)")
            
            if st.button("Upload", type="primary"):
                with st.spinner("Uploading documents..."):
                    response = upload_document(uploaded_files)
                    
                    if response and response.status_code in [200, 201]:
                        data = response.json()
                        if isinstance(data, list):
                            total_chunks = sum(d.get("added_chunks", 0) for d in data)
                            st.success(f"✅ Uploaded {len(data)} file(s) with {total_chunks} total chunks")
                        else:
                            st.success(f"✅ Document uploaded! Added {data.get('added_chunks', 0)} chunks")
                    else:
                        error_msg = response.json().get("detail", "Upload failed") if response else "Connection error"
                        st.error(f"❌ Upload failed: {error_msg}")
    
    with tab2:
        st.header("Query Documents")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            query = st.text_area(
                "Ask your question",
                placeholder="What would you like to know about your documents?",
                height=100
            )
        
        with col2:
            st.subheader("Search Options")
            use_hybrid = st.checkbox("🔀 Hybrid Search", value=True, help="Combine BM25 and vector search")
            use_reranking = st.checkbox("📊 Re-ranking", value=True, help="Re-rank results for accuracy")
        
        # Metadata filtering
        with st.expander("🏷️ Advanced Filters"):
            filter_by_type = st.multiselect("Document Type", ["pdf", "txt", "all"], default=["all"])
            filter_by_date = st.date_input("Upload Date (from)", value=None)
        
        if st.button("Search", type="primary"):
            if not query.strip():
                st.warning("Please enter a question")
            else:
                with st.spinner("Searching your documents..."):
                    metadata_filters = {}
                    if filter_by_type and "all" not in filter_by_type:
                        metadata_filters["document_type"] = {"value": filter_by_type[0], "operator": "equals"}
                    
                    response = query_documents(
                        query,
                        use_hybrid=use_hybrid,
                        use_reranking=use_reranking,
                        metadata_filters=metadata_filters if metadata_filters else None
                    )
                    
                    if response and response.status_code == 200:
                        data = response.json()
                        st.session_state.session_id = data.get("session_id")
                        
                        # Display answer
                        st.markdown(f"""
                        <div class="answer-container">
                            <div class="answer-text">{data['answer']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Display retrieved chunks
                        if data.get("top_chunks"):
                            st.subheader("Retrieved Chunks")
                            for chunk in data["top_chunks"]:
                                with st.expander(f"📄 {chunk['metadata'].get('document_name', 'Document')}"):
                                    st.markdown(f"""
                                    <div>
                                        <span class="badge badge-file">{chunk['metadata'].get('document_type', 'doc')}</span>
                                        <span class="badge badge-info">Chunk {chunk['metadata'].get('chunk_index', 0)}</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    st.write(chunk['text'])
                    else:
                        error_msg = response.json().get("detail", "Query failed") if response else "Connection error"
                        st.error(f"❌ Query failed: {error_msg}")
    
    with tab3:
        st.header("Query History & Conversations")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            tab_history, tab_sessions = st.tabs(["Recent Queries", "Sessions"])
            
            with tab_history:
                with st.spinner("Loading history..."):
                    response = get_history()
                    if response and response.status_code == 200:
                        data = response.json()
                        if data.get("history"):
                            for item in data["history"][:20]:
                                timestamp = item.get("timestamp", "")
                                if timestamp:
                                    dt = datetime.fromisoformat(timestamp)
                                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                                else:
                                    time_str = "Unknown"
                                
                                st.markdown(f"""
                                <div class="history-card">
                                    <div style="font-size: 12px; color: #888;">{time_str}</div>
                                    <div class="history-query">Q: {item['query']}</div>
                                    <div class="history-answer">A: {item['answer'][:300]}...</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("No query history yet. Start by asking a question!")
                    else:
                        st.error("Failed to load history")
            
            with tab_sessions:
                with st.spinner("Loading sessions..."):
                    response = get_sessions()
                    if response and response.status_code == 200:
                        data = response.json()
                        if data.get("sessions"):
                            for session in data["sessions"]:
                                st.write(f"**Session:** {session['session_id'][:8]}...")
                                st.write(f"Messages: {session['messages']} | Last: {session['last_message'][:10]}")
                        else:
                            st.info("No conversation sessions yet.")
                    else:
                        st.error("Failed to load sessions")
        
        with col2:
            if st.button("🗑️ Clear History"):
                if st.button("Confirm Clear"):
                    response = make_request("/history/clear", method="POST")
                    if response and response.status_code == 200:
                        st.success("History cleared")
                        st.rerun()
    
    with tab4:
        st.header("Settings")
        
        st.subheader("Search Configuration")
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("🔀 **Hybrid Search**: Combines BM25 keyword search with semantic vector search for better results")
            st.info("📊 **Re-ranking**: Uses cross-encoders to re-rank results based on relevance")
        
        with col2:
            st.info("🏷️ **Metadata Filtering**: Filter documents by type, upload date, and user")
            st.info("💾 **Session Tracking**: Automatic conversation session management for multi-turn QA")
        
        st.subheader("Account Information")
        if st.button("View Profile"):
            response = make_request("/auth/me", method="GET")
            if response and response.status_code == 200:
                profile = response.json()
                st.json(profile)


# Main app logic
def main():
    if st.session_state.token and st.session_state.username:
        render_main_app()
    else:
        render_auth_page()


if __name__ == "__main__":
    main()
