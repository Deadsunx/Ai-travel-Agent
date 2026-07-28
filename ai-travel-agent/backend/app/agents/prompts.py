"""Prompts for the Travel Planning Agent.

All prompt builders are functions so the current date is computed per request,
not frozen at import time.
"""

from datetime import datetime, timedelta


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _default_start_date() -> str:
    return (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")


def get_extraction_prompt(user_query: str, history_text: str = "") -> str:
    """Prompt for a single structured-output call that extracts trip parameters."""
    return f"""You are a parameter extractor for a travel planning system. Current date: {_today()}.

Read the conversation and the new user message, then output ONLY a JSON object (no markdown, no explanation) with these fields:

{{
  "intent": "plan_trip" | "refine" | "chat",
  "destination": string or null,
  "origin": string or null,
  "start_date": "YYYY-MM-DD" or null,
  "end_date": "YYYY-MM-DD" or null,
  "days": integer or null,
  "travelers": integer or null,
  "budget_limit": number or null,
  "interests": string or null,
  "cuisine": string or null
}}

Rules:
- "plan_trip" = user wants a trip planned and a destination is stated or clear from context.
- "refine" = user wants to change/ask about an already-planned trip in this conversation.
- "chat" = greeting, general question, or destination still unknown.
- Dates must be in the future (after {_today()}). If the user gave a past date or no date, use null.
- budget_limit is in INR. Convert "30k" to 30000, "1.5 lakh" to 150000.
- Do not invent values the user never implied. Use null.

Conversation so far:
{history_text if history_text else "(none)"}

New user message: {user_query}

JSON:"""


def get_synthesis_prompt(user_query: str, collected_data_json: str, has_mock_data: bool) -> str:
    """Prompt for the final answer, grounded in collected tool data."""
    mock_note = (
        "\n- IMPORTANT: Some data below is ESTIMATED/DEMO data (marked with source 'Mock Data'). "
        "Clearly tell the user those prices are estimates, not live prices."
        if has_mock_data
        else ""
    )
    return f"""You are an expert travel planner. Current date: {_today()}.

Write the final trip plan for the user, using ONLY the data provided below. Do not invent prices, hotel names, or restaurant names that are not in the data.{mock_note}

Format with these Markdown sections (skip a section only if there is no data for it):
### Trip Summary
### Budget Breakdown
### Flight Options
### Accommodation
### Day-by-Day Itinerary
### Booking Links

Guidelines:
- Keep descriptions concise; use bullet points and tables where helpful.
- In the Day-by-Day Itinerary, weave in the actual restaurant names from the data.
- Compare total cost against the user's budget limit if one was given, and say clearly whether the trip fits.
- Include every booking link present in the data.

User request: {user_query}

Collected data (JSON):
{collected_data_json}
"""


def get_chat_prompt(user_query: str, history_text: str = "", plan_context: str = "") -> str:
    """Prompt for conversational replies and refinements (no full re-plan needed)."""
    context_block = f"\nCurrent trip plan context:\n{plan_context}\n" if plan_context else ""
    return f"""You are a friendly, expert AI travel assistant. Current date: {_today()}.

- Answer the user's message helpfully and concisely, in Markdown.
- If they are refining an existing plan, use the plan context below and only describe what changes.
- If no destination is known yet, ask for the missing essentials (destination, dates, budget) in ONE short question.
- Never invent live prices; if asked for prices you don't have, say a fresh search is needed.
{context_block}
Conversation so far:
{history_text if history_text else "(none)"}

User message: {user_query}
"""
