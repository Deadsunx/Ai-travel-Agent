from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============== Chat Schemas ==============

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., description="User message")
    session_id: str = Field(..., description="Session ID for conversation tracking")
    user_id: Optional[str] = Field(None, description="Optional user ID")
    model: Optional[str] = Field("qwen3:8b", description="Model to use for the chat")
    planner: Optional[str] = Field(
        None,
        description="Planner to use: 'pipeline' (v1) or 'graph' (v2 multi-agent). "
                    "Defaults to the PLANNER setting.",
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    session_id: str
    itinerary: Optional[Dict[str, Any]] = None


class MessageSchema(BaseModel):
    """Schema for individual chat messages"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============== Itinerary Schemas ==============

class ActivitySchema(BaseModel):
    """Schema for an activity in the itinerary"""
    time: str
    activity: str
    location: Optional[str] = None
    duration: Optional[str] = None
    cost_estimate: Optional[float] = 0.0
    booking_link: Optional[str] = None


class MealSchema(BaseModel):
    """Schema for meal recommendations"""
    name: str
    rating: Optional[float] = None
    price_level: Optional[str] = None
    address: Optional[str] = None
    link: Optional[str] = None


class DayPlanSchema(BaseModel):
    """Schema for a single day's plan"""
    day: int
    date: Optional[str] = None
    morning: List[ActivitySchema] = []
    afternoon: List[ActivitySchema] = []
    evening: List[ActivitySchema] = []
    meals: Optional[Dict[str, MealSchema]] = None
    estimated_cost: float = 0.0


class FlightSchema(BaseModel):
    """Schema for flight information"""
    airline: str
    price: float
    currency: str = "INR"
    departure_time: str
    arrival_time: str
    duration: Optional[str] = None
    booking_link: Optional[str] = None


class HotelSchema(BaseModel):
    """Schema for hotel information"""
    name: str
    price_per_night: float
    currency: str = "INR"
    rating: Optional[float] = None
    address: Optional[str] = None
    amenities: List[str] = []
    booking_link: Optional[str] = None


class BudgetBreakdownSchema(BaseModel):
    """Schema for budget breakdown"""
    flights: float = 0.0
    accommodation: float = 0.0
    food: float = 0.0
    activities: float = 0.0
    miscellaneous: float = 0.0
    buffer: float = 0.0
    total: float = 0.0
    budget_limit: float = 0.0
    remaining: float = 0.0
    within_budget: bool = True


class ItinerarySchema(BaseModel):
    """Complete itinerary schema"""
    destination: str
    duration_days: int
    summary: Dict[str, Any]
    flights: List[FlightSchema] = []
    accommodation: List[HotelSchema] = []
    daily_plan: List[DayPlanSchema] = []
    budget_breakdown: Optional[BudgetBreakdownSchema] = None
    booking_links: Dict[str, str] = {}


class SaveItineraryRequest(BaseModel):
    """Request model for saving itinerary"""
    session_id: str
    user_id: Optional[str] = None
    itinerary_data: Dict[str, Any]


class SaveItineraryResponse(BaseModel):
    """Response model for saved itinerary"""
    success: bool
    itinerary_id: int
    message: str


# ============== Health Check Schemas ==============

class HealthCheckResponse(BaseModel):
    """Response model for health check"""
    status: str
    database: str
    redis: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
