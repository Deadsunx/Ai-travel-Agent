'use client'

import { formatCurrency } from '@/lib/utils'

interface BudgetBreakdownProps {
    data: {
        breakdown?: {
            flights?: number
            accommodation?: number
            food?: number
            transport?: number
            activities?: number
            miscellaneous?: number
            buffer_10_percent?: number
        }
        subtotal?: number
        total_with_buffer?: number
        budget_limit?: number
        remaining_budget?: number
        within_budget?: boolean
        percentage_used?: number
        recommendations?: string[]
    }
}

/** A fare table. Costs align on the decimal; the verdict is stated in words. */
export default function BudgetBreakdown({ data }: BudgetBreakdownProps) {
    const breakdown = data.breakdown || {}
    const dailyBreakdown = (data as any).daily_breakdown || {}
    const hasDailyBreakdown = Object.keys(dailyBreakdown).length > 0

    const withinBudget = data.within_budget !== false
    const percentageUsed = data.percentage_used || 0
    const hasLimit = (data.budget_limit ?? 0) > 0

    const items = hasDailyBreakdown
        ? [
            { label: 'Accommodation', value: dailyBreakdown.accommodation || 0 },
            { label: 'Food', value: dailyBreakdown.food || 0 },
            { label: 'Transport', value: dailyBreakdown.transport || 0 },
            { label: 'Activities', value: dailyBreakdown.activities || 0 },
            { label: 'Miscellaneous', value: dailyBreakdown.miscellaneous || 0 },
        ]
        : [
            { label: 'Flights', value: breakdown.flights || 0 },
            { label: 'Accommodation', value: breakdown.accommodation || 0 },
            { label: 'Food', value: breakdown.food || 0 },
            { label: 'Transport', value: breakdown.transport || 0 },
            { label: 'Activities', value: breakdown.activities || 0 },
            { label: 'Miscellaneous', value: breakdown.miscellaneous || 0 },
            { label: 'Buffer (10%)', value: breakdown.buffer_10_percent || 0 },
        ]

    // The calculator prefixes its list with a header line ("Budget exceeded!
    // Consider these options:"). The verdict above already says that, so drop
    // any tip that is just a lead-in rather than an action.
    const tips: string[] = (data.recommendations || (data as any).tips || [])
        .map((tip: string) => tip.replace(/^[^\w₹]+/, '').trim())
        .filter((tip: string) => tip && !tip.endsWith(':'))

    return (
        <div>
            <table className="w-full">
                <tbody>
                    {items.filter((item) => item.value > 0).map((item) => (
                        <tr key={item.label}>
                            <td className="py-1.5 text-sm text-muted">{item.label}</td>
                            <td className="py-1.5 text-right data text-sm text-ink tabular-nums">
                                {formatCurrency(item.value)}
                            </td>
                        </tr>
                    ))}
                    <tr>
                        <td className="pt-3 border-t border-rule text-sm text-ink">Total</td>
                        <td className="pt-3 border-t border-rule text-right data text-base text-ink tabular-nums">
                            {formatCurrency(
                                hasDailyBreakdown
                                    ? (data as any).total_per_person || 0
                                    : data.total_with_buffer || 0
                            )}
                        </td>
                    </tr>
                    {hasLimit && (
                        <tr>
                            <td className="py-1.5 text-sm text-muted">Your limit</td>
                            <td className="py-1.5 text-right data text-sm text-muted tabular-nums">
                                {formatCurrency(data.budget_limit!)}
                            </td>
                        </tr>
                    )}
                    {hasLimit && data.remaining_budget !== undefined && (
                        <tr>
                            <td className="py-1.5 text-sm text-muted">
                                {data.remaining_budget >= 0 ? 'Left over' : 'Over by'}
                            </td>
                            <td
                                className={`py-1.5 text-right data text-sm tabular-nums ${data.remaining_budget >= 0 ? 'text-stamp' : 'text-est'
                                    }`}
                            >
                                {formatCurrency(Math.abs(data.remaining_budget))}
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>

            {hasLimit && percentageUsed > 0 && (
                <div className="mt-4">
                    <div className="flex items-baseline justify-between mb-1.5">
                        <span className="field-label">Budget used</span>
                        <span className="data text-[0.6875rem] text-muted tabular-nums">
                            {Math.round(percentageUsed)}%
                        </span>
                    </div>
                    <div className="h-1 bg-rule/50">
                        <div
                            className={`h-full transition-[width] duration-700 ease-out ${percentageUsed > 100 ? 'bg-est' : percentageUsed > 90 ? 'bg-marigold' : 'bg-stamp'
                                }`}
                            style={{ width: `${Math.min(percentageUsed, 100)}%` }}
                        />
                    </div>
                </div>
            )}

            {hasLimit && (
                <p className={`mt-4 text-sm ${withinBudget ? 'text-ink' : 'text-est'}`}>
                    {withinBudget
                        ? 'This trip fits your budget.'
                        : 'This trip is over your budget. Trim it with the notes below.'}
                </p>
            )}

            {tips.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                    {tips.map((tip: string, index: number) => (
                        <li key={index} className="text-xs leading-relaxed text-muted pl-3 relative before:absolute before:left-0 before:top-[0.55em] before:w-1.5 before:h-px before:bg-rule">
                            {tip}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}
