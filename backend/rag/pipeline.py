from typing import TypedDict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.llms import HuggingFacePipeline
from langchain_openai import ChatOpenAI
from transformers import pipeline
from langgraph.graph import StateGraph, END

from backend.config import settings
from backend.rag.vector_store import search_documents


# Define the state schema for LangGraph workflow
class RAGState(TypedDict):
    query: str
    documents: Optional[list]
    context: Optional[str]
    answer: str


def get_llm():
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI LLM")
        return ChatOpenAI(
            model=settings.openai_model,
            openai_api_key=settings.openai_api_key,
            temperature=0.2,
        )
    else:
        # Use local model
        pipe = pipeline(
            "text2text-generation",
            model=settings.local_generation_model,
            max_length=256,
        )
        return HuggingFacePipeline(pipeline=pipe)


def retrieve_documents(state: RAGState) -> RAGState:
    """Node: Retrieve relevant documents from vector store"""
    query = state["query"]
    docs = search_documents(query)
    state["documents"] = docs
    return state


def check_documents(state: RAGState) -> str:
    """Conditional: Check if documents were found"""
    if state["documents"]:
        return "generate_answer"
    else:
        return "no_docs_answer"


def build_context(state: RAGState) -> RAGState:
    """Node: Build context from retrieved documents"""
    if state["documents"]:
        context = "\n\n".join([doc.page_content for doc in state["documents"]])
        state["context"] = context
    return state


def generate_answer_node(state: RAGState) -> RAGState:
    """Node: Generate answer using LLM with retrieved context"""
    prompt_template = (
        "Use the relevant document chunks below to answer the user's question. "
        "If the answer is not contained in the chunks, politely say you could not find sufficient information in the uploaded documents.\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}\nAnswer:"
    )
    prompt = prompt_template.format(context=state["context"], question=state["query"])

    llm = get_llm()
    if hasattr(llm, 'invoke'):  # LangChain v0.1+
        messages = [{"role": "user", "content": prompt}]
        response = llm.invoke(messages)
        answer = response.content if hasattr(response, 'content') else str(response)
    else:  # Older versions
        answer = llm(prompt)

    normalized = answer.strip()
    lower_answer = normalized.lower()
    if any(phrase in lower_answer for phrase in [
        "i don't know",
        "i do not know",
        "can't answer",
        "cannot answer",
        "unable to answer",
        "not enough information"
    ]):
        normalized = "I’m sorry, I could not find enough information in the uploaded documents to answer that question."

    state["answer"] = normalized
    return state


def no_docs_answer(state: RAGState) -> RAGState:
    """Node: Return default answer when no documents found"""
    state["answer"] = "I apologize, but I could not find relevant information in the documents to answer your question."
    return state


# Build the RAG workflow graph
def create_rag_graph():
    """Create the LangGraph workflow for RAG pipeline"""
    workflow = StateGraph(RAGState)

    # Add nodes
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("build_context", build_context)
    workflow.add_node("generate_answer", generate_answer_node)
    workflow.add_node("no_docs_answer", no_docs_answer)

    # Set entry point
    workflow.set_entry_point("retrieve")

    # Add edges and conditional routing
    workflow.add_edge("retrieve", "build_context")
    workflow.add_conditional_edges(
        "build_context",
        check_documents,
        {
            "generate_answer": "generate_answer",
            "no_docs_answer": "no_docs_answer",
        }
    )
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("no_docs_answer", END)

    return workflow.compile()


# Global graph instance
rag_graph = None


def get_rag_graph():
    """Get or create the RAG graph"""
    global rag_graph
    if rag_graph is None:
        rag_graph = create_rag_graph()
    return rag_graph


def generate_answer(query: str) -> str:
    """
    Generate an answer for the given query using the LangGraph RAG workflow.
    This is the main entry point for the pipeline.
    """
    graph = get_rag_graph()
    
    # Initialize state
    initial_state: RAGState = {
        "query": query,
        "documents": None,
        "context": None,
        "answer": ""
    }
    
    # Run the workflow
    final_state = graph.invoke(initial_state)
    
    return final_state["answer"]
