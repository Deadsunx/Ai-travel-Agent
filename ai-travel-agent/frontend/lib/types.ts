export interface Message {
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
    data?: any
}

// ---- Multi-agent planner trace ------------------------------------------
// Populated from the agent_start / agent_result / critique / revision events
// the graph planner streams; empty for the pipeline planner.

export type AgentName = 'flight' | 'hotel' | 'local'
export type LaneState = 'idle' | 'dispatched' | 'reported'

export interface AgentChoice {
    name: string
    rationale: string
}

export interface AgentLane {
    state: LaneState
    count: number
    estimated: boolean
    /** What this desk picked, once it picks rather than just fetches. */
    choice?: AgentChoice
}

export interface PlannerIssue {
    severity: 'blocker' | 'warning' | 'note'
    category: string
    message: string
    action?: string | null
}

export interface AgentTrace {
    lanes: Record<AgentName, AgentLane>
    constraints: Record<string, any> | null
    verdict: 'pass' | 'revise' | 'give_up' | null
    issues: PlannerIssue[]
    rounds: { round: number; actions: string[] }[]
}

export const IDLE_TRACE: AgentTrace = {
    lanes: {
        flight: { state: 'idle', count: 0, estimated: false },
        hotel: { state: 'idle', count: 0, estimated: false },
        local: { state: 'idle', count: 0, estimated: false },
    },
    constraints: null,
    verdict: null,
    issues: [],
    rounds: [],
}

export interface Activity {
    time: string
    activity: string
    location?: string
    duration?: string
    cost?: number
    link?: string
    notes?: string
}

export interface DayPlan {
    day: number
    date?: string
    day_name?: string
    theme?: string
    morning: Activity[]
    afternoon: Activity[]
    evening: Activity[]
    meals?: {
        breakfast?: any
        lunch?: any
        dinner?: any
    }
    estimated_cost: number
}

export interface Flight {
    airline: string
    price: number
    currency: string
    departure_time: string
    arrival_time: string
    duration?: string
    booking_link?: string
}

export interface Hotel {
    name: string
    price_per_night: number
    total_price?: number
    currency: string
    rating?: number
    address?: string
    amenities?: string[]
    booking_link?: string
}

export interface Restaurant {
    name: string
    rating?: number
    price_level?: string
    cuisine?: string[]
    address?: string
    link?: string
}

export interface BudgetBreakdown {
    flights: number
    accommodation: number
    food: number
    activities: number
    miscellaneous: number
    buffer_10_percent: number
    total: number
    budget_limit: number
    remaining: number
    within_budget: boolean
}

export interface Itinerary {
    destination: string
    duration_days: number
    start_date?: string
    end_date?: string
    preferences?: string
    budget?: number
    summary?: {
        flight?: Flight
        accommodation?: Hotel
    }
    daily_plan: DayPlan[]
    collected_data?: {
        flights?: any
        hotels?: any
        restaurants?: any
        budget?: BudgetBreakdown
    }
    booking_links?: {
        flights?: { [key: string]: string }
        hotels?: { [key: string]: string }
        activities?: { [key: string]: string }
        food?: { [key: string]: string }
    }
    total_estimated_cost?: number
    budget_status?: string
}
