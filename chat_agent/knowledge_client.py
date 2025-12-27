import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from chat_agent.dify_client import DifyClientError
from chat_agent.summarizer import (
    DifySummarizer,
    DifySummaryConfig,
    DifySummaryError,
)


logger = logging.getLogger(__name__)


class DifyKnowledgeClientError(DifyClientError):
    """Raised when knowledge API calls fail."""


@dataclass
class DifyKnowledgeConfig:
    base_url: str
    api_key: str
    dataset_id: str
    document_id: str

    @staticmethod
    def from_env() -> "DifyKnowledgeConfig":
        base_url = os.getenv("DIFY_KNOWLEDGE_URL") or os.getenv("DIFY_URL")
        api_key = os.getenv("DIFY_KNOWLEDGE_API") or os.getenv("DIFY_API")
        dataset_id = os.getenv("DIFY_DATASET_ID")
        document_id = os.getenv("DIFY_DOCUMENT_ID")

        missing = [
            name
            for name, value in [
                ("DIFY_KNOWLEDGE_URL or DIFY_URL", base_url),
                ("DIFY_KNOWLEDGE_API or DIFY_API", api_key),
                ("DIFY_DATASET_ID", dataset_id),
                ("DIFY_DOCUMENT_ID", document_id),
            ]
            if not value
        ]

        if missing:
            raise ValueError(
                "Missing knowledge configuration environment variables: "
                + ", ".join(missing)
            )

        return DifyKnowledgeConfig(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            dataset_id=dataset_id,
            document_id=document_id,
        )


class DifyKnowledgeClient:
    """
    Client that persists summarized chat history in a Dify knowledge base.

    Each user/email combination is stored as a single JSON payload containing:
        {
            "email": "...",
            "name": "<detected user name or empty string>",
            "history": [
                {
                    "timestamp": "...",
                    "role": "user|assistant",
                    "summary": "...",
                    "conversation_id": "..."  # optional
                },
                ...
            ]
        }
    """

    def __init__(self, config: DifyKnowledgeConfig):
        self._config = config
        self._headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        self._summarizer: Optional[DifySummarizer] = None
        self._known_names: Dict[str, str] = {}

        try:
            summary_config = DifySummaryConfig.from_env()
        except ValueError as exc:
            logger.info("Summarizer disabled (missing env): %s", exc)
        else:
            try:
                self._summarizer = DifySummarizer(summary_config)
            except DifySummaryError as exc:
                logger.warning("Unable to initialize summarizer: %s", exc)
                self._summarizer = None

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

    # --------------------------------------------------------------------- #
    # Persistence
    # --------------------------------------------------------------------- #

    def store_message(
        self,
        email: str,
        role: str,
        content: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        if not content:
            return {}

        try:
            segment, payload = self._find_existing_segment(email)
        except DifyKnowledgeClientError:
            raise
        except Exception as exc:  # pragma: no cover - guard rails
            raise DifyKnowledgeClientError(str(exc)) from exc

        existing_name = ""
        history: List[Dict[str, Optional[str]]] = []

        if payload is not None:
            existing_name, history = self._parse_record(payload)

        summary_text, detected_name, question_flag = self._summarize(
            role=role,
            content=content,
            existing_name=existing_name,
        )

        new_entry = self._build_history_entry(
            role=role,
            summary=summary_text,
            conversation_id=conversation_id,
            question_hie_related=question_flag if role == "user" else None,
        )

        history.append(new_entry)
        updated_name = detected_name or existing_name or ""
        self._known_names[email] = updated_name

        if segment:
            self._replace_segment(
                segment_id=segment["id"],
                email=email,
                history=history,
            name=updated_name,
        )
        else:
            self._create_new_entry(
                email=email,
                history=history,
                name=updated_name,
            )

        return new_entry

    def _summarize(
        self,
        role: str,
        content: str,
        existing_name: str,
    ) -> Tuple[str, str, str]:
        if not self._summarizer:
            return content, existing_name, "yes"

        try:
            result = self._summarizer.summarize(
                role=role,
                message=content,
                existing_name=existing_name,
            )
        except DifySummaryError as exc:
            logger.warning("Summarizer request failed (%s); using raw text", exc)
            return content, existing_name, "yes"
        except Exception as exc:  # pragma: no cover - unexpected
            logger.exception("Unexpected summarizer failure")
            return content, existing_name, "yes"

        summary = result.get("summary") or content
        name = result.get("name") or existing_name or ""
        question_raw = (result.get("question_hie_related") or "").strip().lower()
        if question_raw not in {"yes", "no"}:
            question_flag = "yes"
        else:
            question_flag = question_raw
        return summary, name, question_flag

    def _find_existing_segment(
        self, email: str
    ) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, Any]]]:
        url = (
            f"{self._config.base_url}/v1/datasets/"
            f"{self._config.dataset_id}/documents/{self._config.document_id}/segments"
        )
        params = {"limit": 100, "offset": 0}

        try:
            response = requests.get(
                url, headers=self._headers, params=params, timeout=30
            )
        except requests.RequestException as exc:
            logger.error("Knowledge lookup request failed: %s", exc)
            raise DifyKnowledgeClientError("Knowledge lookup request failed") from exc

        if response.status_code >= 400:
            logger.error(
                "Knowledge lookup failed: status=%s body=%s",
                response.status_code,
                response.text,
            )
            raise DifyKnowledgeClientError(
                f"Knowledge lookup failed with status {response.status_code}"
            )

        data = response.json()
        for segment in data.get("data", []):
            metadata = segment.get("metadata") or {}
            candidate_email = metadata.get("user_email")

            try:
                decoded = json.loads(segment.get("content") or "")
            except json.JSONDecodeError:
                decoded = {}

            decoded_email = decoded.get("email") if isinstance(decoded, dict) else ""
            effective_email = candidate_email or decoded_email

            if effective_email == email:
                return segment, decoded if isinstance(decoded, dict) else {}

        return None, None

    def _build_history_entry(
        self,
        role: str,
        summary: str,
        conversation_id: Optional[str],
        question_hie_related: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        entry: Dict[str, Optional[str]] = {
            "timestamp": self._timestamp(),
            "role": role,
            "summary": summary,
        }
        if conversation_id:
            entry["conversation_id"] = conversation_id
        if question_hie_related:
            entry["question_hie_related"] = question_hie_related
        return entry

    def _parse_record(
        self, payload: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Optional[str]]]]:
        if not isinstance(payload, dict):
            return "", []

        name = str(payload.get("name") or "")
        history_data = payload.get("history")
        history: List[Dict[str, Optional[str]]] = []

        if isinstance(history_data, list):
            for item in history_data:
                entry = self._coerce_history_entry(item)
                if entry:
                    history.append(entry)
        else:
            entry = self._coerce_history_entry(payload)
            if entry:
                history.append(entry)

        return name, history

    def _coerce_history_entry(
        self, data: Any
    ) -> Optional[Dict[str, Optional[str]]]:
        if not isinstance(data, dict):
            return None

        summary = data.get("summary") or data.get("content") or ""
        role = data.get("role", "user")
        timestamp = data.get("timestamp") or self._timestamp()
        conversation_id = data.get("conversation_id") or ""

        entry: Dict[str, Optional[str]] = {
            "summary": summary,
            "role": role,
            "timestamp": timestamp,
        }
        if conversation_id:
            entry["conversation_id"] = conversation_id
        return entry

    def _replace_segment(
        self,
        segment_id: str,
        email: str,
        history: List[Dict[str, Optional[str]]],
        name: str,
    ) -> None:
        self._delete_segment(segment_id)
        self._create_new_entry(email=email, history=history, name=name)

    def _delete_segment(self, segment_id: str) -> None:
        url = (
            f"{self._config.base_url}/v1/datasets/{self._config.dataset_id}"
            f"/documents/{self._config.document_id}/segments/{segment_id}"
        )

        try:
            response = requests.delete(url, headers=self._headers, timeout=30)
        except requests.RequestException as exc:
            logger.error("Knowledge delete request failed: %s", exc)
            raise DifyKnowledgeClientError("Knowledge delete request failed") from exc

        if response.status_code not in {200, 202, 204, 404}:
            logger.error(
                "Knowledge delete failed: status=%s body=%s",
                response.status_code,
                response.text,
            )
            raise DifyKnowledgeClientError(
                f"Knowledge delete failed with status {response.status_code}"
            )

    def _create_new_entry(
        self,
        email: str,
        history: List[Dict[str, Optional[str]]],
        name: str,
    ) -> None:
        message_blob = {
            "email": email,
            "name": name or "",
            "history": history,
        }

        url = (
            f"{self._config.base_url}/v1/datasets/"
            f"{self._config.dataset_id}/documents/{self._config.document_id}/segments"
        )
        payload = {
            "segments": [
                {
                    "content": json.dumps(message_blob),
                    "answer": "",
                    "metadata": {"user_email": email},
                }
            ]
        }

        try:
            response = requests.post(
                url, json=payload, headers=self._headers, timeout=30
            )
        except requests.RequestException as exc:
            logger.error("Knowledge create request failed: %s", exc)
            raise DifyKnowledgeClientError("Knowledge create request failed") from exc

        if response.status_code >= 400:
            logger.error(
                "Knowledge create failed: status=%s body=%s",
                response.status_code,
                response.text,
            )
            raise DifyKnowledgeClientError(
                f"Knowledge create failed with status {response.status_code}"
            )

    # --------------------------------------------------------------------- #
    # Retrieval
    # --------------------------------------------------------------------- #

    def fetch_user_history(
        self, email: str, limit: int = 100
    ) -> List[Dict[str, Union[str, float]]]:
        """
        Retrieve stored entries for the given email, ordered oldest to newest.
        """
        url = (
            f"{self._config.base_url}/v1/datasets/"
            f"{self._config.dataset_id}/documents/{self._config.document_id}/segments"
        )
        params = {"limit": limit, "offset": 0}

        try:
            response = requests.get(
                url, headers=self._headers, params=params, timeout=30
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            logger.error("Knowledge fetch request failed: %s", exc)
            raise DifyKnowledgeClientError("Knowledge fetch request failed") from exc

        if response.status_code == 404:
            logger.info("Knowledge document not found; starting with empty history")
            return []

        if response.status_code >= 400:
            logger.error(
                "Failed to fetch chat history from Dify knowledge: status=%s body=%s",
                response.status_code,
                response.text,
            )
            raise DifyKnowledgeClientError(
                f"Knowledge fetch failed with status {response.status_code}"
            )

        data = response.json()
        segments: List[Dict[str, Any]] = data.get("data") or []

        combined_history: List[Dict[str, Union[str, float]]] = []

        for segment in segments:
            metadata = segment.get("metadata") or {}
            raw_content = segment.get("content") or ""

            metadata_email = metadata.get("user_email")
            try:
                decoded = json.loads(raw_content)
            except json.JSONDecodeError:
                logger.debug(
                    "Non-JSON segment encountered for %s; skipping", email
                )
                continue

            if not isinstance(decoded, dict):
                continue

            decoded_email = decoded.get("email")
            effective_email = metadata_email or decoded_email
            if effective_email != email:
                continue

            name, history_entries = self._parse_record(decoded)
            if name:
                self._known_names[email] = name

            for entry in history_entries:
                combined_history.append(
                    {
                        "role": entry.get("role", "user"),
                        "summary": entry.get("summary") or entry.get("content") or "",
                        "content": entry.get("summary") or entry.get("content") or "",
                        "timestamp": entry.get("timestamp") or "",
                        "conversation_id": entry.get("conversation_id") or "",
                    }
                )

        def _sort_key(item: Dict[str, Union[str, float]]) -> Union[str, float]:
            timestamp = item.get("timestamp")
            if isinstance(timestamp, (int, float)):
                return timestamp
            if isinstance(timestamp, str):
                return timestamp
            return ""

        combined_history.sort(key=_sort_key)
        return combined_history

    def get_known_name(self, email: str) -> str:
        return self._known_names.get(email, "")

    def delete_user_data(self, email: str) -> bool:
        """
        Delete all stored data for the given email.

        Returns True if data was found and deleted, False if no data existed.
        """
        try:
            segment, _ = self._find_existing_segment(email)
        except DifyKnowledgeClientError:
            raise
        except Exception as exc:
            raise DifyKnowledgeClientError(str(exc)) from exc

        if not segment:
            return False

        self._delete_segment(segment["id"])
        if email in self._known_names:
            del self._known_names[email]
        return True

    def get_stored_info_summary(self, email: str) -> Dict[str, Any]:
        """
        Get a summary of what information is stored for a user.

        Returns a dictionary with:
        - has_data: bool indicating if any data exists
        - name: stored user name (if any)
        - message_count: number of stored messages
        - first_interaction: timestamp of first message (if any)
        - last_interaction: timestamp of last message (if any)
        - sample_topics: list of a few summarized topics from history
        """
        try:
            segment, payload = self._find_existing_segment(email)
        except DifyKnowledgeClientError:
            raise
        except Exception as exc:
            raise DifyKnowledgeClientError(str(exc)) from exc

        if not segment or not payload:
            return {
                "has_data": False,
                "name": "",
                "message_count": 0,
                "first_interaction": None,
                "last_interaction": None,
                "sample_topics": [],
            }

        name, history = self._parse_record(payload)
        message_count = len(history)

        first_interaction = None
        last_interaction = None
        sample_topics: List[str] = []

        if history:
            timestamps = [
                entry.get("timestamp") for entry in history if entry.get("timestamp")
            ]
            if timestamps:
                first_interaction = min(timestamps)
                last_interaction = max(timestamps)

            # Get sample topics from user messages (up to 3)
            user_messages = [
                entry.get("summary", "")
                for entry in history
                if entry.get("role") == "user" and entry.get("summary")
            ]
            sample_topics = user_messages[-3:] if user_messages else []

        return {
            "has_data": True,
            "name": name,
            "message_count": message_count,
            "first_interaction": first_interaction,
            "last_interaction": last_interaction,
            "sample_topics": sample_topics,
        }
