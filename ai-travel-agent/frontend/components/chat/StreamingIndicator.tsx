interface StreamingIndicatorProps {
    status: string
}

/**
 * Shown only before the first token arrives. The status text is the real
 * pipeline stage, so it needs no decoration beyond a working marker.
 */
export default function StreamingIndicator({ status }: StreamingIndicatorProps) {
    return (
        <div className="animate-rise pl-4 border-l-2 border-marigold">
            <p className="field-label mb-2">Desk</p>
            <p className="data text-xs text-marigold">
                {status || 'Working'}
                <span className="animate-blink">_</span>
            </p>
        </div>
    )
}
