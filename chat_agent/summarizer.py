import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

import requests

from chat_agent.dify_client import DifyClientError


logger = logging.getLogger(__name__)


class DifySummaryError(DifyClientError):
    """Raised when the Dify summarizer encounters an error."""


@dataclass
class DifySummaryConfig:
    base_url: str
    api_key: str
    timeout: float = 30.0

    @staticmethod
    def from_env() -> "DifySummaryConfig":
        base_url = os.getenv("DIFY_SUMMARY_URL") or os.getenv("DIFY_URL")
        api_key = os.getenv("DIFY_SUMMARY_API_KEY")

        if not base_url:
            raise ValueError("Environment variable DIFY_SUMMARY_URL or DIFY_URL is required.")
        if not api_key:
            raise ValueError("Environment variable DIFY_SUMMARY_API_KEY is required.")

        return DifySummaryConfig(base_url=base_url.rstrip("/"), api_key=api_key)


class DifySummarizer:
    """
    Lightweight wrapper around a Dify text generation app that produces
    structured summaries for chat messages.
    """

    def __init__(self, config: DifySummaryConfig):
        self._config = config
        self._endpoint = f"{config.base_url}/v1/completion-messages"

    def summarize(
        self,
        role: str,
        message: str,
        existing_name: str = "",
    ) -> Dict[str, str]:
        """
        Return a dictionary with keys:
            - summary: summarized message content focusing on personal info and HIE facts
            - name: detected user name (empty string if not present)
            - question_hie_related: "yes" if the text is about HIE, otherwise "no"
        """
        if not message:
            return {"summary": "", "name": existing_name, "question_hie_related": "yes"}

        instructions = (
            "You are a privacy-aware medical summarizer. Summarize each chat turn with special emphasis on:"
            "\n1. Any Personal Identifiable Information (PII) mentioned by the speaker."
            "\n2. Medical details related to hypoxic-ischemic encephalopathy (HIE) or neonatal care."
            "\nRules:"
            "\n- Preserve any personal names, dates, or HIE-specific terminology exactly as stated."
            "\n- If no new PII or HIE detail is present, provide a concise factual summary."
            "\n- Detect and report the user's name only if explicitly provided. Otherwise keep it empty."
            "\n- Decide whether the speaker's message is related to HIE. Output 'yes' only if the content is primarily"
            " about HIE, neonatal encephalopathy, or closely related medical care; otherwise output 'no'."
            "\n- Always respond with STRICT JSON using the following schema:"
            '\n  {"summary": "<concise summary>", "name": "<user name or empty string>", '
            '"question_hie_related": "yes" | "no"}'
            "\n- Do not add additional keys. Do not wrap the JSON in markdown fences."
        )

        existing_label = existing_name if existing_name else '""'
        prompt = (
            f"{instructions}\n\n"
            f"Existing known user name: {existing_label}\n"
            f"Speaker role: {role}\n"
            "Message:\n"
            f"<<<\n{message}\n>>>"
        )

        payload = {
            "inputs": {
                "query": prompt,
                "role": role,
                "message": message,
                "existing_name": existing_label,
            },
            "query": prompt,
            "response_mode": "blocking",
            "user": "summary-agent",
        }

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=self._config.timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise DifySummaryError("Summarizer request failed") from exc

        if response.status_code != 200:
            raise DifySummaryError(
                f"Summarizer request failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        answer = data.get("answer", "").strip()

        return self._parse_summary(answer, existing_name)

    @staticmethod
    def _parse_summary(answer: str, fallback_name: str) -> Dict[str, str]:
        if not answer:
            return {"summary": "", "name": fallback_name, "question_hie_related": "yes"}

        cleaned = answer.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.lstrip("`")
            # Remove possible language hints (e.g. ```json)
            cleaned = cleaned.split("```", 1)[0]

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Summarizer returned non-JSON response: %s", answer)
            return {
                "summary": cleaned,
                "name": fallback_name,
                "question_hie_related": "yes",
            }

        summary = payload.get("summary") or ""
        name = payload.get("name") or fallback_name or ""
        question_flag_raw = (payload.get("question_hie_related") or "").strip().lower()
        if question_flag_raw not in {"yes", "no"}:
            question_flag = "yes"
        else:
            question_flag = question_flag_raw

        return {
            "summary": summary,
            "name": name,
            "question_hie_related": question_flag,
        }
