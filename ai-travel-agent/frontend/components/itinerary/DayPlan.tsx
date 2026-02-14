'use client'

import { Clock, MapPin, DollarSign, Sun, Sunset, Moon } from 'lucide-react'
import { formatCurrency, formatDate } from '@/lib/utils'

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

export default function DayPlan({ day }: DayPlanProps) {
    return (
        <div className="border border-gray-100 rounded-xl p-4">
            {/* Day Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h4 className="font-bold text-gray-800">
                        Day {day.day}
                        {day.day_name && <span className="font-normal text-gray-500"> • {day.day_name}</span>}
                    </h4>
                    {day.theme && (
                        <p className="text-sm text-primary-600">{day.theme}</p>
                    )}
                </div>
                {day.estimated_cost !== undefined && day.estimated_cost > 0 && (
                    <div className="flex items-center gap-1 text-sm font-medium text-gray-600">
                        <DollarSign className="w-4 h-4" />
                        {formatCurrency(day.estimated_cost)}
                    </div>
                )}
            </div>

            {/* Activities by time of day */}
            <div className="space-y-4">
                {/* Morning */}
                {day.morning && day.morning.length > 0 && (
                    <TimeBlock
                        icon={<Sun className="w-4 h-4 text-amber-500" />}
                        label="Morning"
                        activities={day.morning}
                    />
                )}

                {/* Afternoon */}
                {day.afternoon && day.afternoon.length > 0 && (
                    <TimeBlock
                        icon={<Sunset className="w-4 h-4 text-orange-500" />}
                        label="Afternoon"
                        activities={day.afternoon}
                    />
                )}

                {/* Evening */}
                {day.evening && day.evening.length > 0 && (
                    <TimeBlock
                        icon={<Moon className="w-4 h-4 text-indigo-500" />}
                        label="Evening"
                        activities={day.evening}
                    />
                )}
            </div>
        </div>
    )
}

function TimeBlock({
    icon,
    label,
    activities
}: {
    icon: React.ReactNode
    label: string
    activities: Activity[]
}) {
    return (
        <div>
            <div className="flex items-center gap-2 mb-2">
                {icon}
                <span className="text-sm font-medium text-gray-600">{label}</span>
            </div>
            <div className="space-y-2 ml-6">
                {activities.map((activity, index) => (
                    <div key={index} className="flex items-start gap-3 p-2 bg-gray-50 rounded-lg">
                        <div className="flex-shrink-0 mt-0.5">
                            <Clock className="w-4 h-4 text-gray-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-500">{activity.time}</span>
                                {activity.duration && (
                                    <span className="text-xs text-gray-400">({activity.duration})</span>
                                )}
                            </div>
                            <p className="text-sm font-medium text-gray-800">{activity.activity}</p>
                            {activity.location && (
                                <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                                    <MapPin className="w-3 h-3" />
                                    {activity.location}
                                </p>
                            )}
                            {activity.notes && (
                                <p className="text-xs text-primary-600 mt-1">{activity.notes}</p>
                            )}
                        </div>
                        {activity.cost !== undefined && activity.cost > 0 && (
                            <div className="text-xs text-gray-500">
                                {formatCurrency(activity.cost)}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}
