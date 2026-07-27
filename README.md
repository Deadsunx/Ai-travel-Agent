# AI Travel Agent - Project Overview

This repository contains the **AI-powered Travel Planning Agent**, a robust full-stack application designed to generate personalized, budget-conscious travel itineraries using real-time data from multiple external APIs.

## 🚀 Current Project State

The project is currently in an advanced development state with a fully functional core architecture and integrated AI agents.

### 🏗️ Architecture & Tech Stack

The application is built using a modern, scalable stack:

- **Frontend**: Next.js 14 (App Router) with TypeScript and Tailwind CSS (Shadcn UI).
- **Backend**: FastAPI (Python 3.11+) orchestration.
- **AI Agent Layer**: two selectable planners over the same tools — a deterministic
  pipeline (default) and a LangGraph multi-agent orchestrator (see
  [MULTI_AGENT_SPEC.md](MULTI_AGENT_SPEC.md)).
- **Models**: local Ollama models (Qwen3, Gemma) with Google Gemini as a cloud option.
- **Database**: PostgreSQL for persistent storage of itineraries and chat sessions.
- **Caching**: Redis for API response caching and rate limiting.
- **Containerization**: Fully orchestrated using Docker and Docker Compose.

### 📡 API Integration Status

The system uses a **Hybrid Integration** model to ensure reliability while providing real-world data:

| Tool | Source | Purpose | Status |
|------|--------|---------|--------|
| **Flight Search** | SerpAPI (Google Flights) | Real-time flight pricing and links | ✅ Integrated with Mock Fallback |
| **Hotel Search** | RapidAPI (Booking.com) | Real-time accommodation search | ✅ Integrated with Mock Fallback |
| **Places Search** | Foursquare API | Local attraction and dining info | ✅ Integrated with Mock Fallback |
| **General Search**| Google Search | Information on activities and tips | ✅ Integrated |

> [!NOTE]
> The "Mock Fallback" system ensures the agent remains functional even if API keys are missing or rate limits are reached, by providing realistic estimated data.

### 🧭 Planners

| Planner | Selected by | What it does |
|---------|-------------|--------------|
| `pipeline` (default) | `PLANNER=pipeline` | Extract parameters → fetch all sources in parallel → cost the trip → write the answer. Fast and fully deterministic. |
| `graph` | `PLANNER=graph`, or the **Multi-agent** switch in the header | Same work as a LangGraph state machine: a supervisor sets budget-derived constraints, three specialist desks run in parallel, and a critic can send the plan back for a bounded revision round. |

Either planner can be picked per request (`"planner"` in the chat payload), so the
two can be compared on the same query:

```bash
docker compose exec backend python -m evals.run_evals --compare
```

### ✨ Key Features Implemented

- **Conversational Planning**: Interactive chat interface for refining trip requirements.
- **Intelligent Itineraries**: Day-by-day breakdowns with morning, afternoon, and evening activities.
- **Budget Management**: Real-time cost estimation and budget compliance checking.
- **Direct Booking**: links to Google Flights and Booking.com generated dynamically.
- **Persistent Sessions**: Chat history and generated itineraries saved to PostgreSQL.

### 📁 Project Structure

```text
AI Travel Agent PBL ANTGVT/
├── ai-travel-agent/           # Core Application Code
│   ├── frontend/              # Next.js Application
│   ├── backend/               # FastAPI & LangChain Agents
│   ├── scripts/               # Utility and Setup Scripts
│   ├── docker-compose.yml     # Infrastructure Orchestration
│   ├── .env                   # API keys (never commit — see .env.example)
│   └── test_apis.py           # API Verification Utility
└── README.md                  # This file
```

---

## 🛠️ Getting Started

### Prerequisites

- Docker & Docker Compose
- API Keys for OpenAI, SerpAPI, RapidAPI, and Foursquare

### Quick Run

1. Navigate to the core directory:

   ```bash
   cd ai-travel-agent
   ```

2. Copy `.env.example` to `.env` and fill in your API keys (never commit this file).
3. Start the entire stack:

   ```bash
   docker-compose up --build
   ```

4. Access the application at `http://localhost:3000`.

---
*Built as a Project-Based Learning (PBL) initiative focusing on Agentic AI and Real-time API Orchestration.*
