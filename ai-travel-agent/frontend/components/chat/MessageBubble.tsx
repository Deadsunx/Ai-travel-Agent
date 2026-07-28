'use client'

import { Message } from '@/lib/types'
import { formatTime } from '@/lib/utils'
import Prose from './Prose'

interface MessageBubbleProps {
    message: Message
}

/**
 * Transcript entry. Not a chat bubble — a ruled record with the speaker in
 * the gutter, so the desk's long itineraries read as a document.
 */
export default function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user'

    return (
        <div className={`animate-rise pl-4 border-l-2 ${isUser ? 'border-rule' : 'border-stamp'}`}>
            <div className="flex items-baseline justify-between gap-3 mb-2">
                <p className="field-label">{isUser ? 'You' : 'Desk'}</p>
                <p className="data text-[0.625rem] text-muted/60">{formatTime(message.timestamp)}</p>
            </div>

            {isUser ? (
                <p className="text-sm leading-relaxed text-ink">{message.content}</p>
            ) : (
                <Prose>{message.content}</Prose>
            )}
        </div>
    )
}
