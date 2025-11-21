import logging
from typing import Optional

from .agent import AgentResponse, DifyAgent
from .dify_client import DifyChatClient, DifyConfig


def configure_logging(verbose: bool = False, log_path: str = "chat_agent.log") -> None:
    handlers = [logging.FileHandler(log_path, encoding="utf-8")]
    handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def build_agent() -> DifyAgent:
    config = DifyConfig.from_env()
    dify_client = DifyChatClient(config)
    return DifyAgent(dify_client)


def run_cli(agent: DifyAgent, initial_prompt: Optional[str] = None) -> None:
    print("Microsoft Agent Framework + Dify demo")
    print("Type 'exit' or 'quit' to end the conversation.\n")

    if initial_prompt:
        _handle_exchange(agent, initial_prompt)

    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEnding conversation.")
            break

        if user_text.lower() in {"exit", "quit"}:
            print("Conversation finished.")
            break

        if not user_text:
            continue

        _handle_exchange(agent, user_text)


def _handle_exchange(agent: DifyAgent, message: str) -> None:
    try:
        response = agent.run(message)
    except Exception as exc:  # pragma: no cover - surface to user
        logging.getLogger(__name__).exception("Chat exchange failed")
        print(f"[error]: {exc}")
        return

    if not response or not isinstance(response, AgentResponse):
        print("Agent: [empty response]")
        return

    if response.answer:
        print(f"Agent: {response.answer}")
    else:
        print("Agent: [empty response]")

    if response.citations:
        print("Sources:")
        for idx, citation in enumerate(response.citations, start=1):
            title = citation.get("title") or citation.get("source") or f"Citation {idx}"
            snippet = citation.get("snippet") or ""
            if title and snippet:
                print(f"  [{idx}] {title}: {snippet}")
            elif title:
                print(f"  [{idx}] {title}")
            elif snippet:
                print(f"  [{idx}] {snippet}")


if __name__ == "__main__":
    configure_logging(verbose=False)
    agent = build_agent()
    run_cli(agent)
