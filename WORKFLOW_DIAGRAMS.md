# AI Travel Agent — Workflow Diagrams

---

## 1. Current State

```mermaid
flowchart TD
    U["👤 User"] --> M{"Select Mode"}
    
    M -->|"AI Chat"| C["Type natural language query"]
    M -->|"Manual Form"| F["Fill trip form"]

    C --> SSE["POST /api/chat (SSE Stream)"]
    F --> MP["POST /api/manual-plan"]

    SSE --> RL{"Rate Limit Check
    (Redis, 20 req/hr)"}
    RL -->|"Exceeded"| E1["❌ 429 Error"]
    RL -->|"OK"| AGENT["LangChain ReAct Agent"]

    AGENT --> LOOP["Thought → Action → Observation Loop"]
    LOOP --> T1["🔍 google_search (SerpAPI)"]
    LOOP --> T2["✈️ flight_search (SerpAPI)"]
    LOOP --> T3["🏨 hotel_search (RapidAPI)"]
    LOOP --> T4["🍽️ restaurant_finder (Foursquare)"]
    LOOP --> T5["💰 budget_calculator"]
    LOOP --> T6["📋 itinerary_builder"]

    MP --> T2 & T3 & T4 & T5 & T6

    T1 & T2 & T3 & T4 & T5 & T6 --> CACHE{"Redis Cache Hit?"}
    CACHE -->|"Yes"| CACHED["Return cached data"]
    CACHE -->|"No"| API["Call external API"]
    API -->|"Success"| STORE["Cache result in Redis"]
    API -->|"Fail"| MOCK["⚠️ Return mock data"]

    CACHED & STORE & MOCK --> RES["Aggregate results"]
    RES --> SAVE["Save to PostgreSQL + Redis"]
    SAVE --> RESP["Stream/Return response to frontend"]
    RESP --> DISPLAY["📊 Render ItineraryDisplay"]
```

---

## 2. Suggested Solution Architecture

```mermaid
flowchart LR
    subgraph Frontend["🖥️ Frontend (Next.js 14)"]
        UI["App Shell
        Theme / Model Selector"]
        CHAT["ChatInterface
        SSE Streaming"]
        FORM["ManualPlanningForm"]
        ITIN["ItineraryDisplay
        DayPlan / Budget / PDF"]
    end

    subgraph Backend["⚙️ Backend (FastAPI)"]
        API["REST API
        /chat /manual-plan /itinerary /health"]
        AGT["TravelPlanningAgent
        ReAct Pattern"]
        TOOLS["Tool Layer
        6 LangChain Tools"]
        SVC["Services
        DB + Redis"]
    end

    subgraph Infra["🗄️ Infrastructure"]
        PG["PostgreSQL 15"]
        RD["Redis 7"]
        OL["Ollama (Local)
        Qwen3 / Gemma2"]
        GM["Gemini API (Cloud)"]
    end

    subgraph ExtAPIs["🌐 External APIs"]
        S["SerpAPI"]
        R["RapidAPI"]
        FQ["Foursquare"]
    end

    UI --> CHAT & FORM
    CHAT & FORM --> API
    API --> AGT --> TOOLS
    API --> TOOLS
    TOOLS --> SVC
    SVC --> PG & RD
    AGT --> OL & GM
    TOOLS --> S & R & FQ
    API --> ITIN
```

---

## 3. Improvements to Reach Final State

```mermaid
flowchart TD
    subgraph Current["🟡 Current State"]
        C1["Single-page app"]
        C2["Anonymous sessions only"]
        C3["Mock data fallback (no real prices)"]
        C4["No booking integration"]
        C5["No itinerary sharing"]
        C6["Basic error handling"]
        C7["No trip history dashboard"]
    end

    subgraph Improvements["🔧 Improvements Needed"]
        I1["🔐 Add user authentication
        (OAuth / JWT login)"]
        I2["💳 Integrate real booking
        (affiliate links / Stripe)"]
        I3["📱 Mobile-responsive polish
        + PWA support"]
        I4["📊 User dashboard
        (saved trips, history, favorites)"]
        I5["🔔 Price alerts & notifications
        (fare drops, deal tracking)"]
        I6["🌍 Multi-currency & i18n
        (USD, EUR, INR auto-detect)"]
        I7["🧪 Test suite
        (unit + integration + E2E)"]
        I8["🚀 CI/CD pipeline
        (GitHub Actions → staging → prod)"]
    end

    subgraph Final["🟢 Final State"]
        F1["Full-featured travel platform"]
        F2["Authenticated users with profiles"]
        F3["Real-time pricing + booking"]
        F4["Trip sharing & collaboration"]
        F5["Production-grade deployment"]
        F6["Monitoring & observability"]
    end

    C1 --> I4 --> F1
    C2 --> I1 --> F2
    C3 --> I6 --> F3
    C4 --> I2 --> F3
    C5 --> I3 --> F4
    C6 --> I7 --> F5
    C7 --> I4 --> F1
    I8 --> F5
    I5 --> F6
```

---

## 4. Request-Response Lifecycle (Concise)

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant BE as Backend
    participant LLM as Ollama / Gemini
    participant APIs as External APIs
    participant DB as PostgreSQL
    participant Cache as Redis

    User->>FE: Enter trip request
    FE->>BE: POST /api/chat (SSE)
    BE->>Cache: Check rate limit
    Cache-->>BE: OK
    BE->>LLM: Send ReAct prompt
    
    loop ReAct Loop (up to 25 iterations)
        LLM-->>BE: Thought + Action
        BE->>Cache: Check tool cache
        alt Cache miss
            BE->>APIs: Call SerpAPI / RapidAPI / Foursquare
            APIs-->>BE: Results
            BE->>Cache: Store (30-60 min TTL)
        else Cache hit
            Cache-->>BE: Cached results
        end
        BE->>LLM: Observation
    end

    LLM-->>BE: Final Answer
    BE->>DB: Save conversation
    BE->>Cache: Update session
    BE-->>FE: SSE stream (tokens + result)
    FE-->>User: Rendered itinerary
```
