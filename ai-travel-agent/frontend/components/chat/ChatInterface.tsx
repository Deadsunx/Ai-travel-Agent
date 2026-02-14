'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'
import MessageBubble from './MessageBubble'
import StreamingIndicator from './StreamingIndicator'
import { sendMessageStreaming, generateSessionId, StreamEvent } from '@/lib/api-client'
import { Message } from '@/lib/types'

interface ChatInterfaceProps {
    onItineraryGenerated?: (data: any) => void
    selectedModel?: string
}

export default function ChatInterface({ onItineraryGenerated, selectedModel = 'qwen3:8b' }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [streamingStatus, setStreamingStatus] = useState('')
    const [streamingText, setStreamingText] = useState('')  // New: for word-by-word streaming
    const [sessionId, setSessionId] = useState<string>('')
    const [mounted, setMounted] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    // Generate session ID only on client-side to avoid hydration errors
    useEffect(() => {
        setSessionId(generateSessionId())
        setMounted(true)
    }, [])

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages, streamingStatus, streamingText])

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault()

        if (!input.trim() || isLoading || !sessionId) return

        const userMessage: Message = {
            role: 'user',
            content: input,
            timestamp: new Date()
        }

        setMessages(prev => [...prev, userMessage])
        setInput('')
        setIsLoading(true)
        setStreamingStatus('🔍 Connecting to AI agent...')
        setStreamingText('')  // Reset streaming text

        try {
            await sendMessageStreaming(
                {
                    message: input,
                    session_id: sessionId,
                    model: selectedModel
                },
                // onEvent
                (event: StreamEvent) => {
                    if (event.type === 'status') {
                        setStreamingStatus(event.message || '')
                    } else if (event.type === 'token') {
                        // Accumulate streaming text word-by-word
                        const content = (event as any).content || ''
                        setStreamingText(prev => prev + content)
                    } else if (event.type === 'result') {
                        const result = event.data

                        // Create assistant message with the FULL response
                        const assistantMessage: Message = {
                            role: 'assistant',
                            content: result.response || 'Trip plan generated successfully!',
                            timestamp: new Date(),
                            data: result
                        }

                        setMessages(prev => [...prev, assistantMessage])
                        setStreamingText('')  // Clear streaming text

                        // Pass itinerary to parent
                        if (onItineraryGenerated && result) {
                            onItineraryGenerated(result)
                        }

                        setStreamingStatus('')
                    } else if (event.type === 'error') {
                        setStreamingStatus('')
                        setStreamingText('')
                        setMessages(prev => [...prev, {
                            role: 'assistant',
                            content: `❌ Error: ${event.message}. Please try again.`,
                            timestamp: new Date()
                        }])
                    }
                },
                // onComplete
                () => {
                    setIsLoading(false)
                    setStreamingStatus('')
                    setStreamingText('')
                },
                // onError
                (error: string) => {
                    setIsLoading(false)
                    setStreamingStatus('')
                    setMessages(prev => [...prev, {
                        role: 'assistant',
                        content: `❌ Connection error: ${error}. Please check if the backend is running.`,
                        timestamp: new Date()
                    }])
                }
            )
        } catch (error) {
            setIsLoading(false)
            setStreamingStatus('')
        }
    }

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }

    const examplePrompts = [
        "Plan a 3-day trip to Goa under ₹10,000, focusing on food",
        "Weekend getaway to Mumbai for 2 days",
        "5-day Kerala trip with focus on nature and beaches"
    ]

    return (
        <div className="flex flex-col h-[600px]">
            {/* Header */}
            <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-800">Chat with Travel Agent</h2>
                {mounted && (
                    <span className="text-xs text-gray-500">
                        Session: {sessionId ? sessionId.slice(0, 12) + '...' : 'Initializing...'}
                    </span>
                )}
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2">
                {messages.length === 0 && (
                    <div className="text-center py-8">
                        <div className="text-4xl mb-3">👋</div>
                        <h3 className="text-lg font-medium text-gray-700 mb-2">
                            Hi! I'm your AI Travel Agent
                        </h3>
                        <p className="text-sm text-gray-500 mb-6">
                            Tell me about your dream trip and I'll plan it for you!
                        </p>

                        {/* Example prompts */}
                        <div className="space-y-2">
                            <p className="text-xs text-gray-400 uppercase tracking-wide">Try these examples:</p>
                            {examplePrompts.map((prompt, index) => (
                                <button
                                    key={index}
                                    onClick={() => setInput(prompt)}
                                    className="block w-full text-left px-4 py-2 text-sm text-gray-600 
                           bg-gray-50 rounded-lg hover:bg-primary-50 hover:text-primary-700
                           transition-colors duration-200"
                                >
                                    "{prompt}"
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((message, index) => (
                    <MessageBubble key={index} message={message} />
                ))}

                {isLoading && streamingStatus && (
                    <StreamingIndicator status={streamingStatus} />
                )}

                {/* Streaming Text Display - shows text as it arrives word-by-word */}
                {isLoading && streamingText && (
                    <div className="flex justify-start">
                        <div className="max-w-[80%] px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-none text-gray-800 dark:text-gray-200">
                            <p className="text-sm whitespace-pre-wrap">
                                {streamingText}
                                <span className="inline-block w-1.5 h-4 bg-primary-500 ml-0.5 animate-pulse" />
                            </p>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <form onSubmit={handleSubmit} className="flex gap-3">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Describe your ideal trip..."
                    className="input-field"
                    disabled={isLoading}
                />
                <button
                    type="submit"
                    disabled={isLoading || !input.trim()}
                    className="px-5 py-3 bg-gradient-to-r from-primary-600 to-primary-700 text-white 
                   rounded-xl font-medium shadow-lg shadow-primary-500/25
                   hover:shadow-xl hover:shadow-primary-500/30 
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transform hover:-translate-y-0.5 transition-all duration-200
                   flex items-center gap-2"
                >
                    {isLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                        <Send className="w-5 h-5" />
                    )}
                </button>
            </form>
        </div>
    )
}
