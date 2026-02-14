export interface Message {
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
    data?: any
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
