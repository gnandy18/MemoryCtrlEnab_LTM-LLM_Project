# HIE Support Agent - Architecture Diagram

## System Architecture Overview

```mermaid
graph TB
    subgraph "User Interface Layer"
        UI1[Streamlit Web UI<br/>streamlit_app.py]
        UI2[Console CLI<br/>main.py]
    end

    subgraph "Agent Layer"
        AGENT[DifyAgent<br/>agent.py<br/>- Conversation management<br/>- Response structuring]
    end

    subgraph "Service Layer"
        CHAT[DifyChatClient<br/>dify_client.py<br/>- Send messages<br/>- Extract citations]
        KNOWLEDGE[DifyKnowledgeClient<br/>knowledge_client.py<br/>- Store history<br/>- Fetch history]
        SUMMARIZER[DifySummarizer<br/>summarizer.py<br/>- Summarize messages<br/>- Extract PII/names<br/>- Flag HIE relevance]
    end

    subgraph "External Services - Dify Platform"
        DIFY_CHAT[Dify Chat API<br/>/v1/chat-messages<br/>- LLM conversation<br/>- RAG retrieval]
        DIFY_KB[Dify Knowledge Base<br/>/v1/datasets/.../segments<br/>- User history storage<br/>- JSON segments]
        DIFY_SUMMARY[Dify Summarizer API<br/>/v1/completion-messages<br/>- Privacy-aware summarization]
    end

    subgraph "Configuration"
        ENV[Environment Variables<br/>.env file<br/>- DIFY_URL<br/>- DIFY_API<br/>- DIFY_DATASET_ID<br/>- DIFY_DOCUMENT_ID<br/>- DIFY_KNOWLEDGE_API<br/>- DIFY_SUMMARY_API_KEY]
    end

    UI1 --> AGENT
    UI2 --> AGENT
    AGENT --> CHAT

    UI1 --> KNOWLEDGE
    KNOWLEDGE --> SUMMARIZER

    CHAT --> DIFY_CHAT
    KNOWLEDGE --> DIFY_KB
    SUMMARIZER --> DIFY_SUMMARY

    ENV -.-> CHAT
    ENV -.-> KNOWLEDGE
    ENV -.-> SUMMARIZER

    style UI1 fill:#667eea,stroke:#764ba2,stroke-width:3px,color:#fff
    style AGENT fill:#4a90e2,stroke:#2c5aa0,stroke-width:2px,color:#fff
    style CHAT fill:#48bb78,stroke:#2f855a,stroke-width:2px,color:#fff
    style KNOWLEDGE fill:#48bb78,stroke:#2f855a,stroke-width:2px,color:#fff
    style SUMMARIZER fill:#48bb78,stroke:#2f855a,stroke-width:2px,color:#fff
    style DIFY_CHAT fill:#ed8936,stroke:#c05621,stroke-width:2px,color:#fff
    style DIFY_KB fill:#ed8936,stroke:#c05621,stroke-width:2px,color:#fff
    style DIFY_SUMMARY fill:#ed8936,stroke:#c05621,stroke-width:2px,color:#fff
```

## Data Flow - User Message Journey

```mermaid
sequenceDiagram
    participant User
    participant StreamlitUI
    participant DifyAgent
    participant DifyChatClient
    participant DifyKnowledgeClient
    participant DifySummarizer
    participant DifyAPI
    participant DifyKB

    User->>StreamlitUI: Send message
    StreamlitUI->>DifyAgent: run(message)

    DifyAgent->>DifyChatClient: send_message(message, conversation_id)
    DifyChatClient->>DifyAPI: POST /v1/chat-messages
    DifyAPI-->>DifyChatClient: {answer, citations, metadata, conversation_id}
    DifyChatClient-->>DifyAgent: Parsed response
    DifyAgent-->>StreamlitUI: AgentResponse(answer, citations)

    StreamlitUI->>StreamlitUI: Display answer & citations

    par Store User Message
        StreamlitUI->>DifyKnowledgeClient: store_message(email, "user", content)
        DifyKnowledgeClient->>DifyKB: GET segments (find existing)
        DifyKB-->>DifyKnowledgeClient: Existing history JSON

        DifyKnowledgeClient->>DifySummarizer: summarize(role, message, existing_name)
        DifySummarizer->>DifyAPI: POST /v1/completion-messages
        DifyAPI-->>DifySummarizer: {summary, name, question_hie_related}
        DifySummarizer-->>DifyKnowledgeClient: Structured summary

        DifyKnowledgeClient->>DifyKnowledgeClient: Append to history
        DifyKnowledgeClient->>DifyKB: DELETE old segment
        DifyKnowledgeClient->>DifyKB: POST new segment (updated history)
        DifyKB-->>DifyKnowledgeClient: Success
    end

    par Store Assistant Response
        StreamlitUI->>DifyKnowledgeClient: store_message(email, "assistant", answer)
        Note over DifyKnowledgeClient,DifyKB: Same process as user message
    end

    StreamlitUI->>User: Display complete response
```

## User Experience Flow - Streamlit UI

```mermaid
stateDiagram-v2
    [*] --> PersonaSelection: App Launch

    PersonaSelection --> EmailEntry: Select Persona<br/>(Sarah/Marcus)
    EmailEntry --> PersonaSelection: Back Button
    EmailEntry --> LoadHistory: Valid Email Entered

    LoadHistory --> Chat: History Loaded<br/>(New or Returning User)

    state Chat {
        [*] --> WaitingInput
        WaitingInput --> Processing: User sends message
        Processing --> DisplayResponse: Agent responds
        DisplayResponse --> WaitingInput: Ready for next
    }

    Chat --> [*]: Exit App

    note right of PersonaSelection
        Two personas:
        - Sarah (NICU Stage)
        - Marcus (Early Intervention)
    end note

    note right of LoadHistory
        - Fetch user history from KB
        - Detect returning user
        - Personalized greeting
    end note

    note right of Chat
        - Show citations for HIE questions
        - Store all messages
        - Maintain conversation_id
    end note
```

## Data Model - Knowledge Base Storage

```mermaid
classDiagram
    class KnowledgeSegment {
        +string segment_id
        +dict metadata
        +string content
    }

    class SegmentMetadata {
        +string user_email
    }

    class SegmentContent {
        +string email
        +string name
        +list~HistoryEntry~ history
    }

    class HistoryEntry {
        +string timestamp
        +string role
        +string summary
        +string conversation_id
        +string question_hie_related
    }

    class AgentResponse {
        +string answer
        +string conversation_id
        +list~Citation~ citations
        +dict metadata
    }

    class Citation {
        +string title
        +string snippet
        +string source
    }

    KnowledgeSegment *-- SegmentMetadata
    KnowledgeSegment *-- SegmentContent
    SegmentContent *-- HistoryEntry
    AgentResponse *-- Citation
```

## Component Dependencies

```mermaid
graph LR
    subgraph "Python Modules"
        MAIN[main.py]
        STREAMLIT[streamlit_app.py]
        AGENT[agent.py]
        DIFY[dify_client.py]
        KNOWLEDGE[knowledge_client.py]
        SUMMARIZER[summarizer.py]
    end

    subgraph "External Libraries"
        REQUESTS[requests]
        ST[streamlit]
        DOTENV[python-dotenv]
    end

    MAIN --> AGENT
    MAIN --> DIFY

    STREAMLIT --> AGENT
    STREAMLIT --> DIFY
    STREAMLIT --> KNOWLEDGE
    STREAMLIT --> ST

    AGENT --> DIFY

    KNOWLEDGE --> SUMMARIZER
    KNOWLEDGE --> DIFY
    KNOWLEDGE --> REQUESTS

    DIFY --> REQUESTS
    DIFY --> DOTENV

    SUMMARIZER --> REQUESTS
    SUMMARIZER --> DIFY
```

## Configuration Flow

```mermaid
graph TD
    START[Application Start] --> LOAD_ENV[Load .env file<br/>python-dotenv]

    LOAD_ENV --> CONFIG_CHAT{DifyConfig.from_env}
    CONFIG_CHAT --> |Required| DIFY_URL[DIFY_URL]
    CONFIG_CHAT --> |Required| DIFY_API[DIFY_API]
    CONFIG_CHAT --> |Optional| DIFY_TIMEOUT[DIFY_TIMEOUT<br/>default: 30s]

    LOAD_ENV --> CONFIG_KB{DifyKnowledgeConfig.from_env}
    CONFIG_KB --> |Required| DIFY_DATASET[DIFY_DATASET_ID]
    CONFIG_KB --> |Required| DIFY_DOC[DIFY_DOCUMENT_ID]
    CONFIG_KB --> |Required| KB_API[DIFY_KNOWLEDGE_API]

    LOAD_ENV --> CONFIG_SUM{DifySummaryConfig.from_env}
    CONFIG_SUM --> |Required| SUM_API[DIFY_SUMMARY_API_KEY]
    CONFIG_SUM --> |Optional| SUM_URL[DIFY_SUMMARY_URL<br/>fallback to DIFY_URL]

    DIFY_URL --> CHAT_CLIENT[DifyChatClient]
    DIFY_API --> CHAT_CLIENT
    DIFY_TIMEOUT --> CHAT_CLIENT

    DIFY_DATASET --> KB_CLIENT[DifyKnowledgeClient]
    DIFY_DOC --> KB_CLIENT
    KB_API --> KB_CLIENT

    SUM_API --> SUMMARIZER_CLIENT[DifySummarizer]
    SUM_URL --> SUMMARIZER_CLIENT

    CHAT_CLIENT --> AGENT_READY[Agent Ready]
    KB_CLIENT --> AGENT_READY
    SUMMARIZER_CLIENT --> KB_CLIENT

    style START fill:#667eea,stroke:#764ba2,stroke-width:2px,color:#fff
    style AGENT_READY fill:#48bb78,stroke:#2f855a,stroke-width:3px,color:#fff
```

## Key Design Patterns

```mermaid
mindmap
  root((HIE Support<br/>Agent))
    Adapter Pattern
      DifyAgent wraps DifyChatClient
      Microsoft Agent Framework style
      Decouples UI from backend

    Repository Pattern
      DifyKnowledgeClient
      Abstract storage operations
      CRUD for user history

    Strategy Pattern
      Citation extraction
      Multiple format handlers
      Normalization pipeline

    Facade Pattern
      Streamlit UI
      Simplifies complex interactions
      Orchestrates multiple services

    Privacy by Design
      Summarization before storage
      PII extraction and preservation
      Minimal data retention
```

---

## Legend

- **Purple/Blue**: User Interface Components
- **Blue**: Agent Layer (Business Logic)
- **Green**: Service Layer (Integrations)
- **Orange**: External Dify Platform APIs
- **Dashed Lines**: Configuration Dependencies
- **Solid Lines**: Direct Dependencies/Calls

