'use client'

import { User, Bot } from 'lucide-react'
import { Message } from '@/lib/types'
import { formatTime } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'

interface MessageBubbleProps {
    message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user'

    return (
        <div className={`flex gap-3 message-enter ${isUser ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                      ${isUser
                    ? 'bg-primary-100 text-primary-600'
                    : 'bg-gradient-to-br from-primary-500 to-accent-500 text-white'}`}>
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Message Content */}
            <div className={`max-w-[80%] ${isUser ? 'text-right' : ''}`}>
                <div className={`rounded-2xl px-4 py-3 ${isUser
                        ? 'bg-primary-600 text-white rounded-tr-sm'
                        : 'bg-gray-100 text-gray-800 rounded-tl-sm'
                    }`}>
                    {isUser ? (
                        <p className="text-sm">{message.content}</p>
                    ) : (
                        <div className="text-sm prose prose-sm max-w-none">
                            <ReactMarkdown
                                components={{
                                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                                    ul: ({ children }) => <ul className="list-disc list-inside mb-2">{children}</ul>,
                                    ol: ({ children }) => <ol className="list-decimal list-inside mb-2">{children}</ol>,
                                    li: ({ children }) => <li className="mb-1">{children}</li>,
                                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                                    a: ({ href, children }) => (
                                        <a href={href} target="_blank" rel="noopener noreferrer"
                                            className="text-primary-600 hover:underline">
                                            {children}
                                        </a>
                                    ),
                                    h1: ({ children }) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
                                    h2: ({ children }) => <h2 className="text-base font-bold mb-2">{children}</h2>,
                                    h3: ({ children }) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
                                    code: ({ children }) => (
                                        <code className="bg-gray-200 px-1 rounded text-xs">{children}</code>
                                    ),
                                }}
                            >
                                {message.content}
                            </ReactMarkdown>
                        </div>
                    )}
                </div>

                {/* Timestamp */}
                <p className={`text-xs text-gray-400 mt-1 ${isUser ? 'text-right' : ''}`}>
                    {formatTime(message.timestamp)}
                </p>
            </div>
        </div>
    )
}
