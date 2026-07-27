'use client'

/**
 * AgentTimeline — what the desk actually did.
 *
 * The multi-agent planner dispatches three specialists at once, then a critic
 * decides whether the plan may be sent. None of that is visible in the prose
 * answer, so the lanes fill in here as the work happens: who was sent out,
 * under what constraint, what came back, and whether the critic sent it back
 * for another round.
 *
 * The pipeline planner emits none of these events, so the panel stays hidden
 * for it — the reducer is a no-op on events it does not recognise.
 */

import { StreamEvent } from '@/lib/api-client'
import { AgentName, AgentTrace, IDLE_TRACE } from '@/lib/types'

const LANES: { agent: AgentName; label: string; remit: string }[] = [
    { agent: 'flight', label: 'Flight desk', remit: 'fares and routing' },
    { agent: 'hotel', label: 'Hotel desk', remit: 'stays within the nightly cap' },
    { agent: 'local', label: 'Local desk', remit: 'eateries and sights' },
]

/**
 * Fold one stream event into the trace. Pure, so the panel has no logic of
 * its own and the mapping can be tested without rendering.
 */
export function reduceTrace(trace: AgentTrace, event: StreamEvent): AgentTrace {
    switch (event.type) {
        case 'agent_start': {
            const agent = event.agent as AgentName
            if (!trace.lanes[agent]) return trace
            return {
                ...trace,
                constraints: event.constraints || trace.constraints,
                lanes: {
                    ...trace.lanes,
                    [agent]: { ...trace.lanes[agent], state: 'dispatched' },
                },
            }
        }

        case 'agent_result': {
            const agent = event.agent as AgentName
            const lane = trace.lanes[agent]
            if (!lane) return trace
            const estimated = String(event.source || '').startsWith('Mock')
            const choice = (event as any).choice
            return {
                ...trace,
                lanes: {
                    ...trace.lanes,
                    // The local desk reports twice (eateries, then sights).
                    [agent]: {
                        state: 'reported',
                        count: lane.count + (event.count || 0),
                        estimated: lane.estimated || estimated,
                        choice: choice || lane.choice,
                    },
                },
            }
        }

        case 'critique':
            return {
                ...trace,
                verdict: (event.verdict as AgentTrace['verdict']) || null,
                issues: event.issues || [],
            }

        case 'revision':
            return {
                ...trace,
                rounds: [...trace.rounds, {
                    round: event.round || trace.rounds.length + 1,
                    actions: event.actions || [],
                }],
                // A new round re-dispatches everyone; clear the counts.
                lanes: IDLE_TRACE.lanes,
                verdict: null,
            }

        default:
            return trace
    }
}

export function hasTrace(trace: AgentTrace): boolean {
    return LANES.some(({ agent }) => trace.lanes[agent].state !== 'idle')
}

function money(value: number): string {
    return `₹${Math.round(value).toLocaleString('en-IN')}`
}

/** The constraint the supervisor handed this desk, in one short phrase. */
function remitFor(agent: AgentName, constraints: Record<string, any> | null): string | null {
    if (!constraints) return null

    if (agent === 'hotel') {
        const cap = constraints.hotel_nightly_cap
        return cap ? `under ${money(cap)} a night` : 'no cap set'
    }
    if (agent === 'flight') {
        return constraints.flight_tier ? `${constraints.flight_tier} fare` : null
    }
    const activity = constraints.activity_budget
    return activity ? `activities under ${money(activity)}` : null
}

function Readout({ lane }: { lane: AgentTrace['lanes'][AgentName] }) {
    if (lane.state === 'idle') {
        return <span className="data text-xs text-muted/70">waiting</span>
    }

    if (lane.state === 'dispatched') {
        return (
            <span className="data text-xs text-marigold">
                searching<span className="animate-blink">_</span>
            </span>
        )
    }

    return (
        <span className="flex items-center gap-2.5">
            <span className="data text-xs text-ink tabular-nums">{lane.count} found</span>
            <span className={`stamp-mark animate-stamp ${lane.estimated ? 'stamp-est' : 'stamp-live'}`}>
                {lane.estimated ? 'Est.' : 'Live'}
            </span>
        </span>
    )
}

function Verdict({ trace }: { trace: AgentTrace }) {
    if (!trace.verdict) {
        return <span className="data text-xs text-muted/70">not checked yet</span>
    }

    if (trace.verdict === 'pass') {
        return <span className="stamp-mark stamp-live animate-stamp">Cleared</span>
    }

    return (
        <span className="stamp-mark stamp-est animate-stamp">
            {trace.verdict === 'revise' ? 'Sent back' : 'Best effort'}
        </span>
    )
}

export default function AgentTimeline({ trace }: { trace: AgentTrace }) {
    if (!hasTrace(trace)) return null

    const round = trace.rounds.length

    return (
        <div className="stock p-5 animate-rise">
            <div className="flex items-baseline justify-between mb-4">
                <p className="field-label">Desks</p>
                <p className="field-label">
                    {round > 0 ? `Round ${round + 1}` : 'Round 1'}
                </p>
            </div>

            <ul className="divide-y divide-rule/60">
                {LANES.map(({ agent, label, remit }) => {
                    const lane = trace.lanes[agent]
                    const brief = remitFor(agent, trace.constraints) || remit
                    return (
                        <li key={agent} className="py-3.5 first:pt-0 last:pb-0">
                            <div className="flex items-center justify-between gap-4">
                                <span className="min-w-0">
                                    <span className="block text-sm text-ink">{label}</span>
                                    <span className="data block text-[0.625rem] text-muted/80 truncate">
                                        {brief}
                                    </span>
                                </span>
                                <Readout lane={lane} />
                            </div>

                            {/* Why this desk picked what it picked. */}
                            {lane.choice && (
                                <p className="mt-2 pl-3 border-l border-rule text-xs leading-relaxed text-muted">
                                    {lane.choice.rationale}
                                </p>
                            )}
                        </li>
                    )
                })}
            </ul>

            <div className="mt-4 pt-4 border-t border-rule/60">
                <div className="flex items-center justify-between gap-4">
                    <span className="min-w-0">
                        <span className="block text-sm text-ink">Critic</span>
                        <span className="data block text-[0.625rem] text-muted/80 truncate">
                            budget, coverage, feasibility
                        </span>
                    </span>
                    <Verdict trace={trace} />
                </div>

                {trace.issues.length > 0 && (
                    <ul className="mt-3 space-y-1.5">
                        {trace.issues.map((issue, index) => (
                            <li key={index} className="flex gap-2 text-xs leading-relaxed">
                                <span
                                    className={`data text-[0.625rem] shrink-0 pt-0.5 ${
                                        issue.severity === 'blocker' ? 'text-est' : 'text-muted'
                                    }`}
                                >
                                    {issue.severity === 'blocker' ? '✗' : '·'}
                                </span>
                                <span className="text-muted">{issue.message}</span>
                            </li>
                        ))}
                    </ul>
                )}

                {trace.rounds.map(({ round: number_, actions }) => (
                    <p key={number_} className="data mt-3 text-[0.625rem] text-muted">
                        Round {number_}: {actions.length ? actions.join(', ') : 'replanned'}
                    </p>
                ))}
            </div>
        </div>
    )
}
