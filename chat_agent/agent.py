import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .dify_client import DifyChatClient

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    answer: str
    conversation_id: Optional[str]
    citations: List[Dict[str, str]]
    metadata: Dict[str, Any]


class DifyAgent:
    """
    Lightweight adapter that wires the Dify chat backend into a Microsoft Agent
    Framework style agent interface.

    The real Microsoft Agent Framework exposes a more feature rich agent base
    class. This helper keeps a minimal surface so the rest of the application
    can be written in a framework-friendly way without forcing the dependency
    during local development.
    """

    def __init__(self, dify_client: DifyChatClient):
        self._client = dify_client
        self._conversation_id: Optional[str] = None

    def run(self, user_message: str) -> AgentResponse:
        """
        Dispatch the user's message to Dify and return the assistant's reply.

        The conversation id returned by Dify is cached locally to keep
        the session cohesive across multiple questions.
        """
        logger.debug("Agent dispatching message to Dify: %s", user_message)
        result = self._client.send_message(
            message=user_message,
            conversation_id=self._conversation_id,
        )
        self._conversation_id = result.get("conversation_id")

        answer = result.get("answer") or ""
        logger.debug("Agent received answer from Dify: %s", answer)

        citations = result.get("citations") or []
        metadata = result.get("metadata") or {}

        return AgentResponse(
            answer=answer,
            conversation_id=self._conversation_id,
            citations=citations,
            metadata=metadata,
        )

    @property
    def conversation_id(self) -> Optional[str]:
        return self._conversation_id

    def set_conversation_id(self, conversation_id: Optional[str]) -> None:
        self._conversation_id = conversation_id
