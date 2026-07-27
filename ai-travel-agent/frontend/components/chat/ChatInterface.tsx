'use client'

import { useState, useRef, useEffect } from 'react'
import { ArrowDown, ArrowRight, Square } from 'lucide-react'
import MessageBubble from './MessageBubble'
import StreamingIndicator from './StreamingIndicator'
import { sendMessageStreaming, generateSessionId, StreamEvent, cancelStreaming } from '@/lib/api-client'
import { AgentTrace, IDLE_TRACE, Message } from '@/lib/types'
import { IDLE_SOURCES, SourceKey, SourceMap } from '@/components/ui/SourceLedger'
import AgentTimeline, { reduceTrace } from '@/components/agents/AgentTimeline'
import Prose from './Prose'

interface ChatInterfaceProps {
    onItineraryGenerated?: (data: any) => void
    onSourcesChange?: (sources: SourceMap) => void
    selectedModel?: string
    selectedPlanner?: string
}

/**
 * The backend streams one status per resolved source, e.g.
 *   "✈️ Flights: found 2 options (estimated)"
 * Map those onto the ledger rows so the hero reflects real pipeline state.
 */
function readSourceStatus(status: string): { key: SourceKey; count: number; estimated: boolean } | null {
    const match = status.match(/(Flights|Hotels|Restaurants|Sights):\s*found\s+(\d+)/i)
    if (!match) return null

    const keyByLabel: Record<string, SourceKey> = {
        flights: 'flights',
        hotels: 'stays',
        restaurants: 'eateries',
        sights: 'sights',
    }

    return {
        key: keyByLabel[match[1].toLowerCase()],
        count: parseInt(match[2], 10),
        estimated: /estimated/i.test(status),
    }
}

const EXAMPLES = [
    'Three days in Goa from Mumbai, under ₹30,000',
    'Five days in Kerala for two, focused on food',
    'A weekend in Jaipur from Delhi',
]

export default function ChatInterface({
    onItineraryGenerated,
    onSourcesChange,
    selectedModel = 'qwen3:8b',
    selectedPlanner,
}: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [streamingStatus, setStreamingStatus] = useState('')
    const [streamingText, setStreamingText] = useState('')
    const [trace, setTrace] = useState<AgentTrace>(IDLE_TRACE)
    const [sessionId, setSessionId] = useState<string>('')
    const [mounted, setMounted] = useState(false)
    const [pinnedToBottom, setPinnedToBottom] = useState(true)
    const scrollRef = useRef<HTMLDivElement>(null)
    const abortControllerRef = useRef<AbortController | null>(null)
    const stoppedByUserRef = useRef(false)
    const stopMessageAddedRef = useRef(false)
    const streamingTextRef = useRef('')
    const sourcesRef = useRef<SourceMap>(IDLE_SOURCES)

    useEffect(() => {
        setSessionId(generateSessionId())
        setMounted(true)
    }, [])

    // Reading back while the answer streams must not be interrupted.
    //
    // Scrolling is applied to the container itself — scrollIntoView() also
    // scrolls every ancestor, which dragged the whole page down on each token.
    //
    // Whether to follow is decided from the DOM at the moment content lands,
    // never from a flag set earlier. Scroll events are dispatched
    // asynchronously, so a token arriving in the same frame as the reader's
    // scroll would be handled with a stale pin and yank them back down —
    // exactly the glitch this replaces.
    const prevHeightRef = useRef(0)
    const isNearBottom = (el: HTMLDivElement, justAdded = 0) =>
        el.scrollHeight - el.scrollTop - el.clientHeight - justAdded < 80

    const handleScroll = () => {
        const el = scrollRef.current
        if (el) setPinnedToBottom(isNearBottom(el))
    }

    useEffect(() => {
        const el = scrollRef.current
        if (!el) return

        // Discount the content this update just appended, so growth alone
        // never reads as "the reader scrolled away".
        const justAdded = Math.max(0, el.scrollHeight - prevHeightRef.current)
        prevHeightRef.current = el.scrollHeight

        const follow = isNearBottom(el, justAdded)
        if (follow) el.scrollTop = el.scrollHeight
        setPinnedToBottom(follow)
    }, [messages, streamingStatus, streamingText])

    const jumpToLatest = () => {
        const el = scrollRef.current
        if (el) el.scrollTop = el.scrollHeight
        setPinnedToBottom(true)
    }

    useEffect(() => {
        streamingTextRef.current = streamingText
    }, [streamingText])

    const setSources = (next: SourceMap) => {
        sourcesRef.current = next
        onSourcesChange?.(next)
    }

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault()
        if (!input.trim() || isLoading || !sessionId) return

        const userMessage: Message = { role: 'user', content: input, timestamp: new Date() }

        setMessages(prev => [...prev, userMessage])
        setInput('')
        setIsLoading(true)
        // follow the answer they just asked for
        setPinnedToBottom(true)
        setStreamingStatus('Reading your request')
        setStreamingText('')
        setTrace(IDLE_TRACE)
        stoppedByUserRef.current = false
        stopMessageAddedRef.current = false
        abortControllerRef.current = new AbortController()

        // Every source goes back to searching for a fresh plan.
        setSources({
            flights: { state: 'searching', count: 0 },
            stays: { state: 'searching', count: 0 },
            eateries: { state: 'searching', count: 0 },
            sights: { state: 'searching', count: 0 },
        })

        try {
            await sendMessageStreaming(
                {
                    message: input,
                    session_id: sessionId,
                    model: selectedModel,
                    planner: selectedPlanner,
                },
                (event: StreamEvent) => {
                    // The multi-agent planner's own events; a no-op for the
                    // pipeline planner, which never emits them.
                    setTrace(prev => reduceTrace(prev, event))

                    if (event.type === 'status') {
                        const status = event.message || ''
                        setStreamingStatus(status)

                        const resolved = readSourceStatus(status)
                        if (resolved) {
                            setSources({
                                ...sourcesRef.current,
                                [resolved.key]: {
                                    state: resolved.estimated ? 'est' : 'live',
                                    count: resolved.count,
                                },
                            })
                        }
                    } else if (event.type === 'token') {
                        setStreamingText(prev => prev + ((event as any).content || ''))
                    } else if (event.type === 'result') {
                        const result = event.data
                        setMessages(prev => [...prev, {
                            role: 'assistant',
                            content: result.response || 'Trip plan ready.',
                            timestamp: new Date(),
                            data: result,
                        }])
                        setStreamingText('')
                        setStreamingStatus('')
                        if (onItineraryGenerated && result) onItineraryGenerated(result)
                    } else if (event.type === 'error') {
                        setStreamingStatus('')
                        setStreamingText('')
                        setSources(IDLE_SOURCES)
                        setMessages(prev => [...prev, {
                            role: 'assistant',
                            content: `The search failed: ${String(event.message || '').replace(/\.$/, '')}. Try again, or rephrase the trip.`,
                            timestamp: new Date(),
                        }])
                    } else if (event.type === 'cancelled') {
                        if (stopMessageAddedRef.current) return
                        stoppedByUserRef.current = true
                        const partialText = streamingTextRef.current.trim()
                        setStreamingStatus('')
                        setStreamingText('')
                        stopMessageAddedRef.current = true
                        setMessages(prev => [...prev, {
                            role: 'assistant',
                            content: partialText ? `${partialText}\n\n*Stopped.*` : '*Stopped.*',
                            timestamp: new Date(),
                        }])
                    }
                },
                () => {
                    setIsLoading(false)
                    setStreamingStatus('')
                    setStreamingText('')
                    abortControllerRef.current = null
                },
                (error: string) => {
                    setIsLoading(false)
                    setStreamingStatus('')
                    setStreamingText('')
                    abortControllerRef.current = null
                    if (stoppedByUserRef.current) return
                    setSources(IDLE_SOURCES)
                    setMessages(prev => [...prev, {
                        role: 'assistant',
                        content: `Can't reach the desk: ${error}. Check that the backend is running.`,
                        timestamp: new Date(),
                    }])
                },
                abortControllerRef.current.signal
            )
        } catch {
            setIsLoading(false)
            setStreamingStatus('')
        }
    }

    const handleStop = async () => {
        if (!isLoading || !sessionId) return

        stoppedByUserRef.current = true
        setStreamingStatus('Stopping')

        try {
            await cancelStreaming(sessionId)
        } catch {
            // The local abort still ends the client stream.
        }

        abortControllerRef.current?.abort()
        abortControllerRef.current = null

        const partialText = streamingTextRef.current.trim()
        setStreamingText('')
        setStreamingStatus('')
        setIsLoading(false)
        stopMessageAddedRef.current = true
        setMessages(prev => [...prev, {
            role: 'assistant',
            content: partialText ? `${partialText}\n\n*Stopped.*` : '*Stopped.*',
            timestamp: new Date(),
        }])
    }

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }

    // Empty desk sizes to its content; once there is a transcript it becomes
    // a fixed, scrolling record.
    const isEmpty = messages.length === 0 && !isLoading

    return (
        <div className={`flex flex-col ${isEmpty ? '' : 'h-[600px]'}`}>
            <div className="flex items-baseline justify-between gap-4 pb-4 mb-5 border-b border-rule">
                <p className="field-label">Transcript</p>
                {mounted && sessionId && (
                    <p className="data text-[0.625rem] text-muted/70">
                        {sessionId.replace('session_', '').slice(0, 8)}
                    </p>
                )}
            </div>

            <div className="relative flex-1 min-h-0 flex flex-col">
                <div
                    ref={scrollRef}
                    onScroll={handleScroll}
                    className={`space-y-6 ${isEmpty ? '' : 'flex-1 overflow-y-auto pr-1'}`}
                >
                {isEmpty && (
                    <div>
                        <p className="text-sm text-ink mb-1">Nothing planned yet.</p>
                        <p className="text-sm text-muted mb-6">
                            Describe a trip to start. Dates and origin are optional.
                        </p>

                        <p className="field-label mb-3">Try</p>
                        <div className="space-y-px">
                            {EXAMPLES.map((prompt, index) => (
                                <button
                                    key={index}
                                    onClick={() => setInput(prompt)}
                                    className="group w-full flex items-center justify-between gap-3 text-left py-3 border-t border-rule/60 last:border-b transition-colors hover:text-ink"
                                >
                                    <span className="text-sm text-muted group-hover:text-ink transition-colors">
                                        {prompt}
                                    </span>
                                    <ArrowRight className="w-3.5 h-3.5 shrink-0 text-muted opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((message, index) => (
                    <MessageBubble key={index} message={message} />
                ))}

                <AgentTimeline trace={trace} />

                {isLoading && !streamingText && streamingStatus && (
                    <StreamingIndicator status={streamingStatus} />
                )}

                {isLoading && streamingText && (
                    <div className="pl-4 border-l-2 border-marigold">
                        <div className="flex items-baseline justify-between gap-3 mb-2">
                            <p className="field-label">Desk</p>
                            <span className="data text-[0.625rem] text-marigold">
                                writing<span className="animate-blink">_</span>
                            </span>
                        </div>
                        <Prose>{streamingText}</Prose>
                    </div>
                )}

                </div>

                {!isEmpty && !pinnedToBottom && (
                    <button
                        type="button"
                        onClick={jumpToLatest}
                        className="btn-quiet absolute bottom-2 left-1/2 -translate-x-1/2 bg-card shadow-sm animate-rise"
                    >
                        <ArrowDown className="w-3 h-3" />
                        Latest
                    </button>
                )}
            </div>

            <form onSubmit={handleSubmit} className="flex gap-2 pt-5 mt-5 border-t border-rule">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Three days in Goa from Mumbai…"
                    className="desk-input"
                    disabled={isLoading}
                    aria-label="Describe your trip"
                />
                <button
                    type={isLoading ? 'button' : 'submit'}
                    onClick={isLoading ? handleStop : undefined}
                    disabled={!isLoading && !input.trim()}
                    className="btn-ink shrink-0"
                >
                    {isLoading ? (
                        <>
                            <Square className="w-3 h-3 fill-current" />
                            Stop
                        </>
                    ) : (
                        'Plan trip'
                    )}
                </button>
            </form>
        </div>
    )
}
