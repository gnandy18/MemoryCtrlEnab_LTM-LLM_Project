import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from chat_agent.agent import AgentResponse, DifyAgent
from chat_agent.dify_client import DifyChatClient, DifyConfig
from chat_agent.knowledge_client import (
    DifyKnowledgeClient,
    DifyKnowledgeClientError,
    DifyKnowledgeConfig,
)

logger = logging.getLogger(__name__)


def _inject_chat_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        * {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        .chat-scroll {
            max-height: 70vh;
            overflow-y: auto;
            padding-right: 0.5rem;
        }

        .landing-header {
            text-align: center !important;
            margin-bottom: 3rem;
            padding: 2rem 0;
        }

        .landing-header * {
            text-align: center !important;
        }

        .landing-title {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
            letter-spacing: -0.02em;
        }

        .landing-subtitle {
            font-size: 1.1rem;
            color: #64748b;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        .landing-description {
            font-size: 0.95rem;
            color: #94a3b8;
            max-width: 700px;
            margin: 0 auto !important;
            line-height: 1.6;
            text-align: center !important;
            display: block;
            padding: 0 2rem;
        }

        .persona-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 1rem;
        }

        .persona-card {
            border: 2px solid #e2e8f0;
            border-radius: 16px;
            padding: 28px;
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            height: 550px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            overflow-y: auto;
            position: relative;
        }

        .persona-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px 16px 0 0;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .persona-card:hover {
            border-color: #667eea;
            box-shadow: 0 20px 25px -5px rgba(102, 126, 234, 0.15), 0 10px 10px -5px rgba(118, 75, 162, 0.08);
            transform: translateY(-4px) scale(1.01);
        }

        .persona-card:hover::before {
            opacity: 1;
        }

        .persona-card.selected {
            border-color: #667eea;
            background: linear-gradient(135deg, #f0f4ff 0%, #e8f0ff 100%);
            box-shadow: 0 20px 25px -5px rgba(102, 126, 234, 0.2), 0 10px 10px -5px rgba(118, 75, 162, 0.1);
            transform: scale(1.02);
        }

        .persona-card.selected::before {
            opacity: 1;
        }

        .persona-avatar {
            font-size: 64px;
            text-align: center;
            margin-bottom: 16px;
            filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.1));
            animation: float 3s ease-in-out infinite;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }

        .persona-title {
            font-size: 24px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 8px;
            text-align: center;
            letter-spacing: -0.01em;
        }

        .persona-subtitle {
            font-size: 15px;
            color: #667eea;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 13px;
        }

        .persona-details {
            font-size: 14.5px;
            line-height: 1.8;
            color: #475569;
            font-weight: 500;
            flex-grow: 1;
            text-align: justify;
            padding: 16px;
            background: rgba(255, 255, 255, 0.6);
            border-radius: 12px;
            border: 1px solid #f1f5f9;
        }

        .persona-details p {
            margin: 0;
        }

        /* Custom scrollbar for persona cards */
        .persona-card::-webkit-scrollbar {
            width: 6px;
        }

        .persona-card::-webkit-scrollbar-track {
            background: #f1f5f9;
            border-radius: 10px;
        }

        .persona-card::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 10px;
        }

        .persona-card::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }

        /* Enhanced button styles */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 12px 24px !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 6px -1px rgba(102, 126, 234, 0.3) !important;
            letter-spacing: 0.02em !important;
        }

        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 10px 15px -3px rgba(102, 126, 234, 0.4) !important;
        }

        .stButton > button:active {
            transform: translateY(0px) !important;
        }

        /* Divider styling */
        hr {
            margin: 2rem 0;
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
        }

        /* Badge styling */
        .persona-badge {
            display: inline-block;
            padding: 4px 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 8px;
        }

        /* Responsive design */
        @media (max-width: 768px) {
            .landing-title {
                font-size: 2rem;
            }
            .persona-card {
                height: auto;
                min-height: 450px;
            }
        }

        /* Smooth page load animation */
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .persona-container {
            animation: fadeIn 0.6s ease-out;
        }

        .landing-header {
            animation: fadeIn 0.8s ease-out;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages: List[Dict[str, Any]] = []
    if "agent" not in st.session_state:
        st.session_state.agent: Optional[DifyAgent] = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = ""
    if "history_loaded" not in st.session_state:
        st.session_state.history_loaded = False
    if "knowledge_client" not in st.session_state:
        st.session_state.knowledge_client: Optional[DifyKnowledgeClient] = None
    if "knowledge_available" not in st.session_state:
        st.session_state.knowledge_available = True
    if "user_name" not in st.session_state:
        st.session_state.user_name = ""
    if "context_history" not in st.session_state:
        st.session_state.context_history: List[Dict[str, Any]] = []
    if "greeted" not in st.session_state:
        st.session_state.greeted = False
    if "pending_hie_related" not in st.session_state:
        st.session_state.pending_hie_related = True
    if "selected_persona" not in st.session_state:
        st.session_state.selected_persona = None


def _bootstrap_agent() -> DifyAgent:
    if st.session_state.agent is None:
        config = DifyConfig.from_env()
        st.session_state.agent = DifyAgent(DifyChatClient(config))
    return st.session_state.agent


def _ensure_knowledge_client() -> None:
    if st.session_state.knowledge_client or not st.session_state.knowledge_available:
        return

    try:
        knowledge_config = DifyKnowledgeConfig.from_env()
    except ValueError as exc:
        st.session_state.knowledge_available = False
        st.session_state.history_loaded = True
        logger.info("Knowledge features disabled (config missing): %s", exc)
        return

    st.session_state.knowledge_client = DifyKnowledgeClient(knowledge_config)


def _render_history() -> None:
    st.markdown('<div class="chat-scroll">', unsafe_allow_html=True)
    for message in st.session_state.get("messages", []):
        with st.chat_message(message.get("role", "user")):
            st.markdown(message.get("content", ""))
            if message.get("show_sources", True):
                _render_citations(message.get("citations"))
    st.markdown("</div>", unsafe_allow_html=True)


def _render_citations(citations: Optional[List[Dict[str, str]]]) -> None:
    if not citations:
        return

    seen: Set[str] = set()
    ordered_sources: List[str] = []

    for citation in citations:
        source = citation.get("source") or ""
        title = citation.get("title") or ""

        source_stripped = source.strip()
        title_stripped = title.strip()

        if source_stripped and (
            source_stripped.lower().startswith(("http://", "https://"))
            or source_stripped.lower().endswith(".pdf")
        ):
            display_value = source_stripped
        elif title_stripped:
            display_value = title_stripped
        else:
            display_value = source_stripped or ""

        if not display_value:
            display_value = f"Source {len(ordered_sources) + 1}"

        if display_value in seen:
            continue
        seen.add(display_value)
        ordered_sources.append(display_value)

    if not ordered_sources:
        return

    st.caption("Sources")
    for idx, display_value in enumerate(ordered_sources, start=1):
        st.markdown(f"{idx}. {display_value}")


def _append_message(
    role: str,
    content: str,
    conversation_id: Optional[str] = None,
    citations: Optional[List[Dict[str, str]]] = None,
    show_citations: bool = True,
) -> None:
    message: Dict[str, Any] = {
        "role": role,
        "content": content,
        "show_sources": show_citations,
    }
    if conversation_id:
        message["conversation_id"] = conversation_id
    if citations:
        message["citations"] = citations

    st.session_state.messages.append(message)

    if role == "user" and not st.session_state.knowledge_available:
        st.session_state.pending_hie_related = True
        return

    if not st.session_state.knowledge_available:
        return

    client: Optional[DifyKnowledgeClient] = st.session_state.get("knowledge_client")
    if not client:
        if role == "user":
            st.session_state.pending_hie_related = True
        return

    try:
        context_entry = client.store_message(
            email=st.session_state.user_email,
            role=role,
            content=content,
            conversation_id=conversation_id,
        )
        stored_name = client.get_known_name(st.session_state.user_email)
        if stored_name:
            st.session_state.user_name = stored_name
        if context_entry:
            st.session_state.context_history.append(context_entry)
            if role == "user":
                flag = (context_entry.get("question_hie_related") or "").strip().lower()
                st.session_state.pending_hie_related = flag == "yes" or flag == ""
        elif role == "user":
            st.session_state.pending_hie_related = True
    except DifyKnowledgeClientError:
        st.session_state.knowledge_available = False
        logger.exception("Disabling knowledge persistence due to error")
        if role == "user":
            st.session_state.pending_hie_related = True


def _load_history_from_knowledge() -> None:
    if (
        st.session_state.history_loaded
        or not st.session_state.user_email
        or not st.session_state.knowledge_available
    ):
        return

    client: Optional[DifyKnowledgeClient] = st.session_state.get("knowledge_client")
    if not client:
        return

    try:
        history = client.fetch_user_history(st.session_state.user_email)
    except DifyKnowledgeClientError:
        st.session_state.knowledge_available = False
        logger.exception("Disabling knowledge features due to fetch failure")
        st.session_state.history_loaded = True
        return

    st.session_state.context_history = history or []
    st.session_state.messages = []
    st.session_state.greeted = False

    if st.session_state.knowledge_client:
        stored_name = st.session_state.knowledge_client.get_known_name(
            st.session_state.user_email
        )
        if stored_name:
            st.session_state.user_name = stored_name

    st.session_state.history_loaded = True


def _sync_agent_conversation(agent: DifyAgent) -> None:
    for message in reversed(st.session_state.context_history + st.session_state.messages):
        conversation_id = message.get("conversation_id") or ""
        if conversation_id:
            agent.set_conversation_id(conversation_id)
            break


def _render_persona_selection() -> None:
    st.markdown(
        """
        <div class="landing-header">
            <h1 class="landing-title">Welcome to HIE Support Agent</h1>
            <p class="landing-subtitle">Personalized AI-Powered Support for Parents</p>
            <p class="landing-description">
                Choose the persona that best matches your current journey. Our AI assistant is designed to provide
                tailored guidance and support based on your specific stage and needs.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2, gap="large")

    personas = {
        "sarah": {
            "avatar": "👩",
            "name": "Sarah",
            "stage": "NICU Stage Parent",
            "subtitle": "Information seeking to learn more about HIE",
            "description": "Sarah is a 32-year-old parent whose baby, Emma (born October 22, 2025), was diagnosed with Hypoxic-Ischemic Encephalopathy (HIE) shortly after birth three weeks ago. Emma is currently 3 weeks old. Seeking support and information, Sarah has been using an AI Large Language Model (LLM) chatbot designed specifically for parents of children with HIE. Over the past three weeks, Sarah has asked the chatbot ten questions about her baby's condition, treatments, and developmental milestones. Sarah has a follow-up appointment coming up soon with her baby's neonatologist.",
        },
        "marcus": {
            "avatar": "👨",
            "name": "Marcus",
            "stage": "Early Intervention Stage Parent",
            "subtitle": "Focused more on learning and attention",
            "description": "Marcus is a 38-year-old parent whose daughter, Zara (born September 10, 2021), was diagnosed with Hypoxic-Ischemic Encephalopathy (HIE) shortly after birth four years ago. Zara is now 4 years, 2 months old and receives multiple early intervention services including physical therapy, occupational therapy, and speech therapy. She has been diagnosed with spastic cerebral palsy and has expressive language delays. Seeking ongoing support and information, Marcus has been using an AI Large Language Model (LLM) chatbot designed specifically for parents of children with HIE. Over the past three months, Marcus has asked the chatbot ten questions about his daughter's therapies, development, and educational planning. Marcus has an upcoming IEP meeting to discuss Zara's transition from preschool special education to kindergarten.",
        }
    }

    with col1:
        persona = personas["sarah"]
        selected_class = "selected" if st.session_state.selected_persona == "sarah" else ""

        st.markdown(f"""
        <div class="persona-card {selected_class}">
            <div class="persona-avatar">{persona['avatar']}</div>
            <div class="persona-title">{persona['name']}</div>
            <div class="persona-subtitle">{persona['stage']}</div>
            <div class="persona-details">
                <p>{persona['description']}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Continue as Sarah", key="btn_sarah", use_container_width=True):
            st.session_state.selected_persona = "sarah"
            st.rerun()

    with col2:
        persona = personas["marcus"]
        selected_class = "selected" if st.session_state.selected_persona == "marcus" else ""

        st.markdown(f"""
        <div class="persona-card {selected_class}">
            <div class="persona-avatar">{persona['avatar']}</div>
            <div class="persona-title">{persona['name']}</div>
            <div class="persona-subtitle">{persona['stage']}</div>
            <div class="persona-details">
                <p>{persona['description']}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Continue as Marcus", key="btn_marcus", use_container_width=True):
            st.session_state.selected_persona = "marcus"
            st.rerun()

    # Footer
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0 1rem 0; color: #94a3b8; font-size: 0.9rem;">
            <p style="margin: 0;">🧠 Powered by Dify AI & Dr. T. Tsai & G. Nandy Research Lab</p>
            <p style="margin: 0.5rem 0 0 0; font-size: 0.85rem; color: #cbd5e1;">
                Advanced AI technology for personalized HIE parent support
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )


def main() -> None:
    st.set_page_config(
        page_title="HIE Support Agent - Personalized AI Assistance",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Hide Streamlit default elements for cleaner look
    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    _ensure_session_state()
    _inject_chat_styles()

    # Step 1: Persona Selection
    if not st.session_state.selected_persona:
        _render_persona_selection()
        return

    # Step 2: Email Authentication
    if not st.session_state.user_email:
        # Show selected persona info
        persona_name = st.session_state.selected_persona.capitalize()
        persona_emoji = "👩" if st.session_state.selected_persona == "sarah" else "👨"
        persona_stage = "NICU Stage Parent" if st.session_state.selected_persona == "sarah" else "Early Intervention Stage Parent"

        st.markdown(
            f"""
            <div class="landing-header">
                <h1 class="landing-title">Almost There!</h1>
                <p class="landing-subtitle">{persona_emoji} Continuing as {persona_name} - {persona_stage}</p>
                <p class="landing-description">
                    Please enter your email address to access your personalized support experience.
                    Your information is secure and private.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Center the form
        col_left, col_center, col_right = st.columns([1, 2, 1])

        with col_center:
            email = st.text_input("Email address", placeholder="name@example.com", label_visibility="collapsed")
            error_message = ""

            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button("Continue to Chat", use_container_width=True):
                    candidate = email.strip()
                    if (
                        "@" not in candidate
                        or candidate.count("@") != 1
                        or candidate.startswith("@")
                        or candidate.endswith("@")
                    ):
                        error_message = "Please enter a valid email address."
                    else:
                        st.session_state.user_email = candidate
                        st.rerun()

            with col2:
                if st.button("← Back", use_container_width=True):
                    st.session_state.selected_persona = None
                    st.rerun()

            if error_message:
                st.error(error_message)

        return

    _ensure_knowledge_client()
    _load_history_from_knowledge()

    agent = _bootstrap_agent()
    _sync_agent_conversation(agent)

    should_greet = (
        st.session_state.history_loaded
        and bool(st.session_state.context_history)
        and not st.session_state.greeted
    )
    if should_greet:
        greeting = (
            f"Hello {st.session_state.user_name}, Nice to talk to you again. "
            "How can I help you this time?"
            if st.session_state.user_name
            else "Hello there, how can I help you today?"
        )
        st.session_state.messages = [
            {"role": "assistant", "content": greeting, "show_sources": False}
        ] + st.session_state.messages
        st.session_state.greeted = True

    header_container = st.container()
    history_container = st.container()

    with header_container:
        # Display persona and user info
        persona_emoji = "👩" if st.session_state.selected_persona == "sarah" else "👨"
        persona_name = st.session_state.selected_persona.capitalize()
        persona_stage = "NICU Stage Parent" if st.session_state.selected_persona == "sarah" else "Early Intervention Stage Parent"

        st.markdown(f"{persona_emoji} **Persona:** {persona_name} ({persona_stage})")
        st.markdown(f"**Logged in as:** {st.session_state.user_email}")
        if st.session_state.user_name:
            st.markdown(f"**Name on record:** {st.session_state.user_name}")
        st.divider()

    with history_container:
        _render_history()

    prompt = st.chat_input("Ask something...")
    if not prompt:
        return

    with st.chat_message("user"):
        st.markdown(prompt)

    current_conversation_id = agent.conversation_id
    _append_message("user", prompt, current_conversation_id)
    should_show_sources = st.session_state.get("pending_hie_related", True)

    try:
        with st.spinner("Thinking..."):
            agent_response = agent.run(prompt)
    except Exception as exc:  # pragma: no cover - surface to UI
        logger.exception("Streamlit chat exchange failed")
        agent_response = AgentResponse(
            answer=f"[error] Unable to fetch response: {exc}",
            conversation_id=agent.conversation_id,
            citations=[],
            metadata={},
        )

    with st.chat_message("assistant"):
        st.markdown(agent_response.answer or "_No response returned._")
        if should_show_sources:
            _render_citations(agent_response.citations)

    _append_message(
        "assistant",
        agent_response.answer,
        agent.conversation_id,
        citations=agent_response.citations,
        show_citations=should_show_sources,
    )

    st.rerun()


if __name__ == "__main__":
    main()
