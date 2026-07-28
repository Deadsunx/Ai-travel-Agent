'use client'

/**
 * SourceLedger — the hero instrument.
 *
 * The one thing this desk does that a search box doesn't: it tells you where
 * every number came from. So the three data sources sit on the page from the
 * start, and resolve in place as the agent works, each one stamped live or
 * estimated.
 */

export type SourceKey = 'flights' | 'stays' | 'eateries' | 'sights'
export type SourceState = 'waiting' | 'searching' | 'live' | 'est'

export interface SourceRow {
    state: SourceState
    count: number
}

export type SourceMap = Record<SourceKey, SourceRow>

export const IDLE_SOURCES: SourceMap = {
    flights: { state: 'waiting', count: 0 },
    stays: { state: 'waiting', count: 0 },
    eateries: { state: 'waiting', count: 0 },
    sights: { state: 'waiting', count: 0 },
}

const ROWS: { key: SourceKey; label: string; via: string }[] = [
    { key: 'flights', label: 'Flights', via: 'Google Flights' },
    { key: 'stays', label: 'Stays', via: 'Booking.com' },
    { key: 'eateries', label: 'Eateries', via: 'OpenStreetMap' },
    { key: 'sights', label: 'Sights', via: 'OpenStreetMap' },
]

function Readout({ row }: { row: SourceRow }) {
    if (row.state === 'waiting') {
        return <span className="data text-xs text-muted/70">waiting</span>
    }

    if (row.state === 'searching') {
        return (
            <span className="data text-xs text-marigold">
                searching<span className="animate-blink">_</span>
            </span>
        )
    }

    return (
        <span className="flex items-center gap-2.5">
            <span className="data text-xs text-ink tabular-nums">
                {row.count} found
            </span>
            <span
                key={row.state}
                className={`stamp-mark animate-stamp ${row.state === 'live' ? 'stamp-live' : 'stamp-est'}`}
            >
                {row.state === 'live' ? 'Live' : 'Est.'}
            </span>
        </span>
    )
}

export default function SourceLedger({ sources }: { sources: SourceMap }) {
    return (
        <div className="stock perforated-top p-5 sm:p-6">
            <div className="flex items-baseline justify-between mb-4">
                <p className="field-label">Sources</p>
                <p className="field-label">Status</p>
            </div>

            <ul className="divide-y divide-rule/60">
                {ROWS.map(({ key, label, via }) => (
                    <li key={key} className="flex items-center justify-between gap-4 py-3.5 first:pt-0 last:pb-0">
                        <span className="min-w-0">
                            <span className="block text-sm text-ink">{label}</span>
                            <span className="data block text-[0.625rem] text-muted/80 truncate">{via}</span>
                        </span>
                        <Readout row={sources[key]} />
                    </li>
                ))}
            </ul>

            <p className="mt-5 pt-4 border-t border-rule/60 text-xs leading-relaxed text-muted">
                Live means the price came back from the source just now. Estimated means
                the source was unavailable and the figure is a stand-in.
            </p>
        </div>
    )
}
