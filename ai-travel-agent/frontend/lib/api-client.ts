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
}

export interface StreamEvent {
    type: 'status' | 'result' | 'error' | 'token' | 'cancelled'
    message?: string
    data?: any
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
