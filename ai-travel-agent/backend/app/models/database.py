from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    session_id = Column(String(255), unique=True, index=True)  # For anonymous users
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user")
    itineraries = relationship("Itinerary", back_populates="user")


class ChatSession(Base):
    """Chat session model for storing conversation history"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(255), unique=True, index=True)
    messages = Column(JSON, default=list)  # Store conversation history
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")


class Itinerary(Base):
    """Itinerary model for storing generated travel plans"""
    __tablename__ = "itineraries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(255), index=True)
    
    # Trip Details
    destination = Column(String(255), nullable=False)
    duration_days = Column(Integer, nullable=False)
    budget = Column(Float, nullable=False)
    preferences = Column(JSON)  # Food, adventure, relaxation, etc.
    
    # Generated Itinerary
    itinerary_data = Column(JSON, nullable=False)  # Complete day-by-day plan
    total_cost = Column(Float)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    is_saved = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="itineraries")


class PlanRun(Base):
    """One planning run, kept so the planners can be compared over time.

    A demo shows that the critic fired once; this table is what answers how
    often it fires, what it asks for, and whether the revision helped —
    across every run rather than the one on screen.
    """
    __tablename__ = "plan_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), unique=True, index=True)
    session_id = Column(String(255), index=True)

    planner = Column(String(16), index=True)      # 'pipeline' | 'graph'
    model_name = Column(String(64))

    params = Column(JSON)         # resolved trip parameters
    choices = Column(JSON)        # what each specialist picked, and why
    issues = Column(JSON)         # what the critic still objected to
    revisions = Column(Integer, default=0)
    verdict = Column(String(16))  # 'pass' | 'give_up' | None for the pipeline

    budget_total = Column(Float)
    budget_limit = Column(Float)
    within_budget = Column(Boolean)

    latency_ms = Column(Integer)
    succeeded = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SearchCache(Base):
    """Search cache model for long-term caching beyond Redis TTL"""
    __tablename__ = "search_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(512), unique=True, index=True)
    cache_value = Column(JSON)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
