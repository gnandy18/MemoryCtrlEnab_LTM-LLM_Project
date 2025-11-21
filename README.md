# Microsoft Agent Framework + Dify Chat Demo

This repository contains a minimal Python console application that wires the **Microsoft Agent Framework** style agent pattern to a Dify hosted chatbot.

The app reads the `DIFY_URL` (base REST endpoint of the Dify app) and `DIFY_API` (API key) environment variables, sends user input to Dify, and streams the assistant's response back to the console.

## Quick start

```powershell
# Install dependencies
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure your Dify credentials (replace with your actual values)
$env:DIFY_URL = "https://your-dify-app-url"
$env:DIFY_API = "dify-api-key"
$env:DIFY_TIMEOUT = "60"  # Optional: increase HTTP wait time if your app is slow

# Launch the chat loop
python -m chat_agent.main
```

The application will keep a running conversation by reusing the conversation id returned by Dify. Type `exit` or press `Ctrl+C` to end the chat session.

## Notes

- The helper class in `chat_agent/agent.py` keeps the code layout compatible with the Microsoft Agent Framework concepts. If you already have the real framework in your environment you can swap out the adapter for the concrete agent implementation.
- The Streamlit UI (`chat_agent/streamlit_app.py`) renders citations returned by Dify knowledge retrieval right beneath each assistant message so users can see which document snippets informed a response.
- Logging is configured at `INFO` level by default. Set `verbose=True` in `configure_logging` inside `chat_agent/main.py` to see raw request/response details while debugging.
