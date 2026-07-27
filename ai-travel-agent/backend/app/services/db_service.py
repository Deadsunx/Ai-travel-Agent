from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional, List
from datetime import datetime
import json

from app.config import settings
from app.models.database import Base, User, ChatSession, Itinerary, PlanRun, SearchCache

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session (dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def check_db_connection() -> bool:
    """Check if database is connected"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        print(f"Database connection error: {e}")
        return False


# ============== User Operations ==============

def get_or_create_user(db: Session, session_id: str, email: Optional[str] = None) -> User:
    """Get existing user or create new one"""
    user = db.query(User).filter(User.session_id == session_id).first()
    
    if not user:
        user = User(session_id=session_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


# ============== Chat Session Operations ==============

def get_or_create_chat_session(db: Session, session_id: str, user_id: Optional[int] = None) -> ChatSession:
    """Get existing chat session or create new one"""
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    
    if not session:
        session = ChatSession(session_id=session_id, user_id=user_id, messages=[])
        db.add(session)
        db.commit()
        db.refresh(session)
    
    return session


def save_chat_message(session_id: str, user_message: str, agent_response: dict) -> bool:
    """Save chat message to database"""
    try:
        db = SessionLocal()
        session = get_or_create_chat_session(db, session_id)
        
        messages = session.messages or []
        messages.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat()
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps(agent_response) if isinstance(agent_response, dict) else str(agent_response),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        session.messages = messages
        session.updated_at = datetime.utcnow()
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Error saving chat message: {e}")
        return False


def get_chat_history(session_id: str) -> Optional[List[dict]]:
    """Get chat history for session"""
    try:
        db = SessionLocal()
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        db.close()
        
        if session:
            return session.messages
        return None
    except Exception as e:
        print(f"Error getting chat history: {e}")
        return None


# ============== Itinerary Operations ==============

def save_itinerary(
    session_id: str,
    itinerary_data: dict,
    user_id: Optional[int] = None
) -> int:
    """Save generated itinerary to database"""
    try:
        db = SessionLocal()
        
        # Extract trip details from itinerary
        destination = itinerary_data.get("destination", "Unknown")
        duration_days = itinerary_data.get("duration", itinerary_data.get("duration_days", 1))
        budget = itinerary_data.get("budget", itinerary_data.get("summary", {}).get("budget", 0))
        total_cost = itinerary_data.get("total_cost", itinerary_data.get("summary", {}).get("total_cost", 0))
        preferences = itinerary_data.get("preferences", {})
        
        itinerary = Itinerary(
            session_id=session_id,
            user_id=user_id,
            destination=destination,
            duration_days=duration_days,
            budget=budget,
            preferences=preferences,
            itinerary_data=itinerary_data,
            total_cost=total_cost,
            is_saved=True
        )
        
        db.add(itinerary)
        db.commit()
        itinerary_id = itinerary.id
        db.close()
        
        return itinerary_id
    except Exception as e:
        print(f"Error saving itinerary: {e}")
        raise e


def get_itinerary_by_id(itinerary_id: int) -> Optional[dict]:
    """Get itinerary by ID"""
    try:
        db = SessionLocal()
        itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
        db.close()
        
        if itinerary:
            return {
                "id": itinerary.id,
                "session_id": itinerary.session_id,
                "destination": itinerary.destination,
                "duration_days": itinerary.duration_days,
                "budget": itinerary.budget,
                "total_cost": itinerary.total_cost,
                "itinerary_data": itinerary.itinerary_data,
                "created_at": itinerary.created_at.isoformat()
            }
        return None
    except Exception as e:
        print(f"Error getting itinerary: {e}")
        return None


def get_user_itineraries(user_id: int) -> List[dict]:
    """Get all itineraries for a user"""
    try:
        db = SessionLocal()
        itineraries = db.query(Itinerary).filter(Itinerary.user_id == user_id).all()
        db.close()
        
        return [
            {
                "id": it.id,
                "destination": it.destination,
                "duration_days": it.duration_days,
                "budget": it.budget,
                "total_cost": it.total_cost,
                "created_at": it.created_at.isoformat()
            }
            for it in itineraries
        ]
    except Exception as e:
        print(f"Error getting user itineraries: {e}")
        return []


def save_plan_run(
    run_id: str,
    session_id: str,
    planner: str,
    model_name: str,
    collected: Optional[dict],
    latency_ms: int,
    succeeded: bool = True,
    verdict: Optional[str] = None,
) -> bool:
    """Record one planning run for later comparison between planners.

    Never raises: telemetry must not be able to fail a user's request.
    """
    collected = collected or {}
    budget = collected.get("budget") or {}

    try:
        db = SessionLocal()
        db.add(PlanRun(
            run_id=run_id,
            session_id=session_id,
            planner=planner,
            model_name=model_name,
            params=collected.get("trip_params") or {},
            choices=collected.get("choices") or [],
            issues=collected.get("issues") or [],
            revisions=collected.get("revisions") or 0,
            verdict=verdict,
            budget_total=budget.get("total_with_buffer"),
            budget_limit=budget.get("budget_limit"),
            within_budget=budget.get("within_budget"),
            latency_ms=latency_ms,
            succeeded=succeeded,
        ))
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Error saving plan run: {e}")
        return False
