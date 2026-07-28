'use client'

import { formatCurrency } from '@/lib/utils'

interface Activity {
    time: string
    activity: string
    location?: string
    duration?: string
    cost?: number
    link?: string
    notes?: string
}

interface DayPlanProps {
    day: {
        day: number
        date?: string
        day_name?: string
        theme?: string
        morning?: Activity[]
        afternoon?: Activity[]
        evening?: Activity[]
        estimated_cost?: number
    }
}

/**
 * A day is a timetable. The clock times carry the information, so they are
 * the structural markers — hung in a fixed gutter, set in the data face —
 * rather than decorative step numbers.
 */
export default function DayPlan({ day }: DayPlanProps) {
    const blocks = [
        { label: 'Morning', items: day.morning },
        { label: 'Afternoon', items: day.afternoon },
        { label: 'Evening', items: day.evening },
    ].filter((block) => block.items && block.items.length > 0)

    return (
        <section>
            <div className="flex items-baseline justify-between gap-4 pb-2 mb-3 border-b border-rule">
                <h4 className="flex items-baseline gap-2.5 min-w-0">
                    <span className="data text-[0.625rem] uppercase tracking-[0.16em] text-muted shrink-0">
                        Day {day.day}
                    </span>
                    {day.theme && <span className="text-sm text-ink truncate">{day.theme}</span>}
                </h4>
                {day.estimated_cost !== undefined && day.estimated_cost > 0 && (
                    <span className="data text-[0.6875rem] text-muted tabular-nums shrink-0">
                        {formatCurrency(day.estimated_cost)}
                    </span>
                )}
            </div>

            {blocks.map((block) => (
                <div key={block.label} className="mb-4 last:mb-0">
                    <p className="field-label mb-1.5">{block.label}</p>
                    <ul>
                        {block.items!.map((activity, index) => (
                            <li key={index} className="flex gap-4 py-1.5">
                                <span className="data text-[0.6875rem] text-muted tabular-nums w-11 shrink-0 pt-px">
                                    {activity.time}
                                </span>
                                <span className="min-w-0 flex-1">
                                    <span className="block text-sm text-ink">{activity.activity}</span>
                                    {activity.location && (
                                        <span className="data block text-[0.625rem] text-muted mt-0.5">
                                            {activity.location}
                                        </span>
                                    )}
                                    {activity.notes && (
                                        <span className="block text-xs text-muted mt-0.5">{activity.notes}</span>
                                    )}
                                </span>
                                {activity.cost !== undefined && activity.cost > 0 && (
                                    <span className="data text-[0.6875rem] text-muted tabular-nums shrink-0">
                                        {formatCurrency(activity.cost)}
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            ))}
        </section>
    )
}
