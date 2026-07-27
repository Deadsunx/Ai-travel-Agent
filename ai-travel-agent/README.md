# 🌍 AI Travel Agent

An AI-powered travel planning agent that creates comprehensive, budget-conscious itineraries with real-time data for flights, hotels, and restaurants.

## ✨ Features

- **AI-Powered Chat**: Conversational interface over local or cloud models
- **Two planners**: a deterministic pipeline, or a multi-agent graph with a plan critic
- **Real-Time Prices**: Live flight and hotel data from SerpAPI, RapidAPI
- **Restaurant Recommendations**: Local dining spots via OpenStreetMap
- **Budget Management**: Smart budget calculator with recommendations
- **Day-by-Day Itinerary**: Complete trip planning with activities
- **Streaming Responses**: Real-time progress updates during planning

## 🛠️ Tech Stack

### Backend

- **FastAPI** - High-performance Python web framework
- **LangGraph** - multi-agent orchestration (the `graph` planner)
- **Ollama / Google Gemini** - local and cloud language models
- **PostgreSQL** - Database
- **Redis** - Caching & session management

### Frontend

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Lucide Icons** - Beautiful icons

### External APIs

- **Ollama** - local models over an OpenAI-compatible endpoint
- **Google Gemini** - optional cloud model
- **SerpAPI** - Google search results
- **RapidAPI** - Skyscanner flights, Booking.com hotels
- **OpenStreetMap (Overpass)** - Restaurants and sights; no API key needed

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

### 1. Clone and Setup

```bash
cd ai-travel-agent
```

### 2. Configure Environment

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
OPENAI_API_KEY=your_openai_key
SERPAPI_KEY=your_serpapi_key
RAPIDAPI_KEY=your_rapidapi_key
FOURSQUARE_API_KEY=your_foursquare_key
```

### 3. Run with Docker

```bash
docker-compose up --build
```

This starts:

- PostgreSQL on port 5432
- Redis on port 6379
- Backend API on <http://localhost:8000>
- Frontend on <http://localhost:3000>

### 4. Access the App

Open your browser to: **<http://localhost:3000>**

## 📁 Project Structure

```
ai-travel-agent/
├── backend/
│   ├── app/
│   │   ├── agents/         # LangChain agent
│   │   ├── api/routes/     # FastAPI routes
│   │   ├── models/         # Database & schemas
│   │   ├── services/       # Redis, DB services
│   │   ├── tools/          # LangChain tools
│   │   ├── config.py       # Settings
│   │   └── main.py         # FastAPI app
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/                # Next.js pages
│   ├── components/         # React components
│   ├── lib/                # Utilities & API client
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── .env
```

## 🔧 Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/` | Chat with AI agent (streaming) |
| POST | `/api/chat/sync` | Chat without streaming |
| GET | `/api/chat/history/{session_id}` | Get chat history |
| POST | `/api/itinerary/save` | Save itinerary |
| GET | `/api/itinerary/{id}` | Get saved itinerary |
| GET | `/health/` | Health check |

## 💬 Example Prompts

- "Plan a 3-day trip to Goa under ₹10,000, I love food"
- "Weekend getaway to Mumbai for 2 days with family"
- "5-day Kerala trip focusing on backwaters and beaches"
- "Honeymoon in Maldives for 1 week, budget ₹2 lakhs"

## 🔑 Getting API Keys

1. **OpenAI**: <https://platform.openai.com/api-keys>
2. **SerpAPI**: <https://serpapi.com/>
3. **RapidAPI**: <https://rapidapi.com/> (subscribe to Skyscanner and Booking.com)
4. **OpenStreetMap**: no key required (public Overpass and Nominatim endpoints)

## 🐛 Troubleshooting

### Docker Issues

```bash
# Rebuild containers
docker-compose down -v
docker-compose up --build
```

### Connection Errors

- Ensure all services are running: `docker-compose ps`
- Check backend logs: `docker-compose logs backend`
- Verify environment variables are set

### Rate Limiting

- 20 requests per hour per user
- Clear rate limit: Restart Redis container

## 📄 License

MIT License

---

Built with ❤️ using LangChain, FastAPI, and Next.js
