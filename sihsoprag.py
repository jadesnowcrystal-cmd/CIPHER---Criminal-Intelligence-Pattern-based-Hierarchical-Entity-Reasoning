"""
Shared SOP / Legal RAG core connected directly to the sidebar system.
"""
import re
import streamlit as st
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Sidebar-accessible configuration parameters
SCORE_THRESHOLD = 0.5
VECTOR_DB_DIR = "./legal_vector_db"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "deepseek-r1:1.5b"

SYSTEM_PROMPT = (
    "You are a legal investigation assistant for police officers.\n"
    "Answer ONLY using the numbered excerpts below. Do not infer, assume, or "
    "extrapolate beyond what is explicitly written.\n"
    "If a specific Act, Section, or Rule number appears in the excerpts, quote it "
    "exactly as written — do not paraphrase legal citations.\n"
    "After your answer, list which excerpt number(s) you used, e.g. (Source: Excerpt 2).\n"
    "If the excerpts do not contain a clear answer, you MUST respond exactly: "
    "'Information not found in database.' Do not guess or fill gaps with general knowledge.\n\n"
    "Excerpts:\n{context}\n\n"
    "Question: {question}"
)
_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)


@st.cache_resource
def load_components():
    """Load embeddings, vectorstore, and LLM once per Streamlit session."""
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    vectorstore = Chroma(persist_directory=VECTOR_DB_DIR, embedding_function=embeddings)
    llm = ChatOllama(model=LLM_MODEL)
    return vectorstore, llm


def get_context_and_docs(vectorstore, query, k=3, score_threshold=SCORE_THRESHOLD):
    try:
        results = vectorstore.similarity_search_with_relevance_scores(query, k=k)
    except Exception as e:
        raise RuntimeError(f"Vector search failed: {e}") from e

    strong_hits = [(doc, score) for doc, score in results if score >= score_threshold]
    return strong_hits, results


def format_numbered_context(strong_hits):
    parts = []
    for i, (doc, score) in enumerate(strong_hits, start=1):
        parts.append(f"[Excerpt {i}]\n{doc.page_content}")
    return "\n\n".join(parts)


def run_query(vectorstore, llm, user_query, k=3, score_threshold=SCORE_THRESHOLD):
    try:
        strong_hits, all_hits = get_context_and_docs(
            vectorstore, user_query, k=k, score_threshold=score_threshold
        )
    except RuntimeError as e:
        return None, [], [], str(e)

    if not strong_hits:
        return "Information not found in database.", [], all_hits

    context = format_numbered_context(strong_hits)
    chain = _prompt | llm | StrOutputParser()

    try:
        raw_answer = chain.invoke({"context": context, "question": user_query})
    except Exception as e:
        return None, [], all_hits, str(e)

    clean_answer = re.sub(r"<think>.*?</think>", "", raw_answer, flags=re.DOTALL).strip()
    return clean_answer, strong_hits, all_hits


def render_sidebar_sop_rag():
    """Renders the SOP RAG Assistant UI controls directly inside the Streamlit Sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚖️ SOP / Legal Assistant")
    
    try:
        vectorstore, llm = load_components()
    except Exception as e:
        st.sidebar.error(f"Failed to load RAG components: {e}")
        return

    query = st.sidebar.text_input("Ask SOP / Legal Question:", key="sidebar_sop_query")
    
    if st.sidebar.button("Search Database", key="sidebar_sop_btn"):
        if query.strip():
            with st.spinner("Searching DB..."):
                answer, strong_hits, all_hits = run_query(vectorstore, llm, query)
                st.session_state["sidebar_sop_result"] = {
                    "answer": answer,
                    "strong_hits": strong_hits,
                    "all_hits": all_hits,
                }
        else:
            st.sidebar.warning("Please enter a question.")

    if "sidebar_sop_result" in st.session_state:
        res = st.session_state["sidebar_sop_result"]
        st.sidebar.markdown("**Answer:**")
        st.sidebar.write(res["answer"])
        
        with st.sidebar.expander("View Source Excerpts"):
            for doc, score in res["strong_hits"]:
                st.caption(f"Score: {score:.2f}")
                st.text(doc.page_content[:200] + "...")
