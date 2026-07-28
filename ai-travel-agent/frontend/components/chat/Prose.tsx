'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * The desk's house style for rendered Markdown. Shared by the streaming
 * preview and the finished transcript entry so text doesn't reflow into a
 * different look the moment generation ends.
 */
export default function Prose({ children }: { children: string }) {
    return (
        <div className="text-sm leading-relaxed text-ink">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: ({ children }) => (
                        <h3 className="display text-base text-ink mt-5 mb-2 first:mt-0">{children}</h3>
                    ),
                    h2: ({ children }) => (
                        <h3 className="display text-base text-ink mt-5 mb-2 first:mt-0">{children}</h3>
                    ),
                    h3: ({ children }) => (
                        <h3 className="field-label block mt-5 mb-2 first:mt-0">{children}</h3>
                    ),
                    p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="mb-3 space-y-1.5 last:mb-0">{children}</ul>,
                    ol: ({ children }) => (
                        <ol className="mb-3 space-y-1.5 list-decimal list-inside last:mb-0">{children}</ol>
                    ),
                    li: ({ children }) => (
                        <li className="pl-4 relative before:absolute before:left-0 before:top-[0.6em] before:w-1.5 before:h-px before:bg-rule">
                            {children}
                        </li>
                    ),
                    strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
                    em: ({ children }) => <em className="data text-xs not-italic text-muted">{children}</em>,
                    a: ({ href, children }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-stamp underline underline-offset-2 decoration-stamp/40 hover:decoration-stamp"
                        >
                            {children}
                        </a>
                    ),
                    code: ({ children }) => (
                        <code className="data text-xs bg-paper px-1 py-0.5 border border-rule/60 rounded-sm">
                            {children}
                        </code>
                    ),
                    hr: () => <hr className="my-4 border-rule/60" />,
                    table: ({ children }) => (
                        <div className="my-3 overflow-x-auto">
                            <table className="w-full data text-xs border-collapse">{children}</table>
                        </div>
                    ),
                    th: ({ children }) => (
                        <th className="text-left font-semibold py-1.5 pr-4 border-b border-rule whitespace-nowrap">
                            {children}
                        </th>
                    ),
                    td: ({ children }) => (
                        <td className="py-1.5 pr-4 border-b border-rule/40 tabular-nums">{children}</td>
                    ),
                    blockquote: ({ children }) => (
                        <blockquote className="my-3 pl-3 border-l-2 border-marigold text-muted">
                            {children}
                        </blockquote>
                    ),
                }}
            >
                {children}
            </ReactMarkdown>
        </div>
    )
}
