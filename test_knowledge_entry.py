from dotenv import load_dotenv

from chat_agent.knowledge_client import (
    DifyKnowledgeClient,
    DifyKnowledgeConfig,
)


def main() -> None:
    load_dotenv(dotenv_path="chat_agent/.env", override=False)

    config = DifyKnowledgeConfig.from_env()
    client = DifyKnowledgeClient(config)

    email = "123"
    content = "This is a Test Entry"

    client.store_message(email=email, role="user", content=content)
    history = client.fetch_user_history(email=email, limit=20)
    print("Stored message:")
    print(f"  email: {email}")
    print(f"  content: {content}")

    print("\nRetrieved history:")
    for idx, message in enumerate(history, start=1):
        print(
            f"{idx:02d}. role={message.get('role')} "
            f"summary={message.get('summary')} "
            f"timestamp={message.get('timestamp')}"
        )

    matched = next(
        (message for message in reversed(history) if message.get("summary") == content),
        None,
    )

    print("\nLatest matching entry:")
    if matched:
        print(f"- role={matched.get('role')} summary={matched.get('summary')}")
    else:
        print("- matching entry not found in knowledge history")

    detected_name = client.get_known_name(email)
    print(f"\nDetected name tag: {detected_name!r}")


if __name__ == "__main__":
    main()
