import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


# Prevent SSL keylog paths requiring elevated permissions from breaking requests.
os.environ.pop("SSLKEYLOGFILE", None)

logger = logging.getLogger(__name__)


class DifyClientError(RuntimeError):
    """Raised when the Dify API returns an unexpected response."""


@dataclass
class DifyConfig:
    """Simple container for the Dify API configuration."""

    base_url: str
    api_key: str
    timeout: float = 30.0
    _ENV_LOADED = False

    @staticmethod
    def from_env(dotenv_path: Optional[str] = None) -> "DifyConfig":
        if not DifyConfig._ENV_LOADED:
            load_dotenv(dotenv_path=dotenv_path, override=False)
            DifyConfig._ENV_LOADED = True

        base_url = os.getenv("DIFY_URL")
        api_key = os.getenv("DIFY_API")

        if not base_url:
            raise ValueError("Environment variable DIFY_URL is required.")

        if not api_key:
            raise ValueError("Environment variable DIFY_API is required.")

        timeout_str = os.getenv("DIFY_TIMEOUT")
        if timeout_str:
            try:
                timeout = float(timeout_str)
            except ValueError as exc:
                raise ValueError(
                    "Environment variable DIFY_TIMEOUT must be a numeric value."
                ) from exc
        else:
            timeout = 30.0

        base_url = base_url.rstrip("/")
        logger.info("Configured Dify client base_url=%s timeout=%s", base_url, timeout)

        return DifyConfig(base_url=base_url, api_key=api_key, timeout=timeout)


class DifyChatClient:
    """Client wrapper around the Dify chat messages endpoint."""

    def __init__(self, config: DifyConfig):
        self._config = config

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        inputs: Optional[Dict[str, str]] = None,
        user: str = "local-user",
    ) -> Dict[str, Any]:
        """
        Send a message to Dify and return the parsed response payload.

        Parameters
        ----------
        message:
            The user's query prompt.
        conversation_id:
            An optional conversation id to keep session state.
        inputs:
            Optional structured inputs Dify flow expects.
        user:
            Arbitrary user identifier (displayed in Dify logs).
        """
        payload = {
            "inputs": inputs or {},
            "query": message,
            "response_mode": "blocking",
            "conversation_id": conversation_id,
            "user": user,
        }

        logger.debug("Sending request to Dify at %s", self._config.base_url)
        response = requests.post(
            f"{self._config.base_url}/v1/chat-messages",
            json=payload,
            headers={"Authorization": f"Bearer {self._config.api_key}"},
            timeout=self._config.timeout,
        )

        if response.status_code != 200:
            logger.error(
                "Dify API error: status=%s body=%s",
                response.status_code,
                response.text,
            )
            raise DifyClientError(
                f"Dify request failed with status {response.status_code}"
            )

        data = response.json()
        logger.debug("Received Dify payload: %s", data)

        metadata = data.get("metadata") or {}
        citations = self._extract_citations(data)

        return {
            "answer": data.get("answer"),
            "conversation_id": data.get("conversation_id", conversation_id),
            "metadata": metadata,
            "citations": citations,
            "raw": data,
        }

    @staticmethod
    def _extract_citations(payload: Dict[str, Any]) -> List[Dict[str, str]]:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return []

        candidates: List[Any] = []
        # Common keys seen across Dify RAG responses.
        for key in (
            "citations",
            "citation",
            "context",
            "contexts",
            "knowledge",
            "knowledge_context",
            "knowledge_contents",
            "retriever_resources",
        ):
            value = metadata.get(key)
            if value:
                candidates.append(value)

        rag_section = metadata.get("rag")
        if isinstance(rag_section, dict):
            for key in ("citations", "contexts"):
                value = rag_section.get(key)
                if value:
                    candidates.append(value)

        normalized: List[Dict[str, str]] = []
        for candidate in candidates:
            normalized.extend(DifyChatClient._normalize_citation(candidate))

        # Deduplicate by snippet/title combo to avoid noisy repeats.
        seen = set()
        unique: List[Dict[str, str]] = []
        for entry in normalized:
            key = (entry.get("title") or "", entry.get("snippet") or "")
            if key in seen:
                continue
            seen.add(key)
            unique.append(entry)

        return unique

    @staticmethod
    def _normalize_citation(candidate: Any) -> List[Dict[str, str]]:
        entries: List[Any]
        if isinstance(candidate, list):
            entries = candidate
        elif isinstance(candidate, dict):
            # Some responses wrap the list under a "data" property.
            if "data" in candidate and isinstance(candidate["data"], list):
                entries = candidate["data"]
            else:
                entries = [candidate]
        elif candidate:
            entries = [candidate]
        else:
            entries = []

        normalized: List[Dict[str, str]] = []
        for item in entries:
            if isinstance(item, dict):
                snippet = (
                    item.get("content")
                    or item.get("text")
                    or item.get("segment_content")
                    or ""
                )
                title = (
                    item.get("document_name")
                    or item.get("title")
                    or item.get("dataset_name")
                    or item.get("source")
                    or item.get("provider_name")
                    or ""
                )
                source = (
                    item.get("url")
                    or item.get("link")
                    or item.get("document_id")
                    or item.get("segment_id")
                    or ""
                )
            else:
                snippet = str(item)
                title = ""
                source = ""

            normalized.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "source": source,
                }
            )

        return normalized
