const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ChatMessage {
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
}

export interface ChatRequest {
    message: string
    session_id: string
    user_id?: string
    model?: string
    /** 'pipeline' (v1) or 'graph' (v2 multi-agent). Omitted = server default. */
    planner?: string
}

/**
 * Events the backend streams over SSE.
 *
 * The first five are the original pipeline events; agent_start / agent_result
 * / critique / revision are added by the multi-agent planner. Handlers must
 * ignore unknown types so either planner can drive this client.
 */
export interface StreamEvent {
    type:
        | 'status' | 'result' | 'error' | 'token' | 'cancelled'
        | 'agent_start' | 'agent_result' | 'critique' | 'revision'
    message?: string
    data?: any
    // agent_start / agent_result
    agent?: string
    section?: string
    count?: number
    source?: string
    constraints?: Record<string, any>
    // critique / revision
    verdict?: string
    issues?: any[]
    round?: number
    actions?: string[]
}

/**
 * Send a message to the chat API with SSE streaming
 */
export async function sendMessageStreaming(
    request: ChatRequest,
    onEvent: (event: StreamEvent) => void,
    onComplete: () => void,
    onError: (error: string) => void,
    signal?: AbortSignal
): Promise<void> {
    try {
        const response = await fetch(`${API_URL}/api/chat/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
            signal,
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
            throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()

            if (done) {
                onComplete()
                break
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6))
                        onEvent(data as StreamEvent)
                    } catch (e) {
                        console.error('Error parsing SSE data:', e)
                    }
                }
            }
        }
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            onComplete()
            return
        }
        onError(error instanceof Error ? error.message : 'Unknown error')
    }
}

/**
 * Request cancellation of an in-progress streaming response.
 */
export async function cancelStreaming(sessionId: string): Promise<void> {
    await fetch(`${API_URL}/api/chat/cancel/${sessionId}`, {
        method: 'POST',
    })
}

/**
 * Send a message to the sync chat API (non-streaming)
 */
export async function sendMessageSync(request: ChatRequest): Promise<any> {
    const response = await fetch(`${API_URL}/api/chat/sync`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    })

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
}

export interface ManualPlanRequest {
    origin: string
    destination: string
    departure_date: string
    return_date: string
    passengers: number
    budget: number
    preferences: string
    trip_style: string
}

/**
 * Build a plan from the form, without the AI agent.
 */
export async function createManualPlan(request: ManualPlanRequest): Promise<any> {
    const response = await fetch(`${API_URL}/api/manual-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
        throw new Error(data?.detail || `Request failed (${response.status})`)
    }

    return data
}

/**
 * Save an itinerary
 */
export async function saveItinerary(data: {
    session_id: string
    user_id?: string
    itinerary_data: any
}): Promise<{ success: boolean; itinerary_id: number; message: string }> {
    const response = await fetch(`${API_URL}/api/itinerary/save`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
    })

    if (!response.ok) {
        throw new Error('Failed to save itinerary')
    }

    return response.json()
}

/**
 * Get chat history for a session
 */
export async function getChatHistory(sessionId: string): Promise<ChatMessage[]> {
    const response = await fetch(`${API_URL}/api/chat/history/${sessionId}`)

    if (!response.ok) {
        return []
    }

    const data = await response.json()
    return data.messages || []
}

/**
 * Check API health
 */
export async function checkHealth(): Promise<{
    status: string
    database: string
    redis: string
}> {
    const response = await fetch(`${API_URL}/health/`)
    return response.json()
}

/**
 * Generate a unique session ID
 */
export function generateSessionId(): string {
    return 'session_' + Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15)
}
