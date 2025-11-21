import logging
from typing import Any, Dict, List, Optional, Set

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
        .chat-scroll {
            max-height: 70vh;
            overflow-y: auto;
            padding-right: 0.5rem;
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


def main() -> None:
    st.set_page_config(
        page_title="HIE: Support Agent",
        page_icon=":speech_balloon:",
        layout="centered",
    )
    st.title("HIE: Support Agent")
    st.caption("Powered by Dify & Dr. T. Sai & G. Nandy research lab")

    _ensure_session_state()
    _inject_chat_styles()

    if not st.session_state.user_email:
        st.subheader("Sign in to continue")
        email = st.text_input("Email address", placeholder="name@example.com")
        error_message = ""

        if st.button("Continue"):
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
        st.markdown(f"**Logged in as:** {st.session_state.user_email}")
        if st.session_state.user_name:
            st.markdown(f"**Name on record:** {st.session_state.user_name}")

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
