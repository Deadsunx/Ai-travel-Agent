'use client'

import { Plane, Hotel, Utensils, Ticket, Package, Shield, CheckCircle, AlertTriangle } from 'lucide-react'
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

export default function BudgetBreakdown({ data }: BudgetBreakdownProps) {
    // Support both the structured "breakdown" format and the flat "daily_breakdown" format from budget_calculator
    const breakdown = data.breakdown || {}
    const dailyBreakdown = (data as any).daily_breakdown || {}
    const hasDailyBreakdown = Object.keys(dailyBreakdown).length > 0

    const withinBudget = data.within_budget !== false
    const percentageUsed = data.percentage_used || 0

    // Build items from whichever format is available
    const items = hasDailyBreakdown ? [
        { label: 'Accommodation', value: dailyBreakdown.accommodation || 0, icon: Hotel, color: 'text-emerald-500' },
        { label: 'Food', value: dailyBreakdown.food || 0, icon: Utensils, color: 'text-orange-500' },
        { label: 'Transport', value: dailyBreakdown.transport || 0, icon: Plane, color: 'text-blue-500' },
        { label: 'Activities', value: dailyBreakdown.activities || 0, icon: Ticket, color: 'text-purple-500' },
        { label: 'Miscellaneous', value: dailyBreakdown.miscellaneous || 0, icon: Package, color: 'text-gray-500' },
    ] : [
        { label: 'Flights', value: breakdown.flights || 0, icon: Plane, color: 'text-blue-500' },
        { label: 'Accommodation', value: breakdown.accommodation || 0, icon: Hotel, color: 'text-emerald-500' },
        { label: 'Food', value: breakdown.food || 0, icon: Utensils, color: 'text-orange-500' },
        { label: 'Transport', value: breakdown.transport || 0, icon: Plane, color: 'text-sky-500' },
        { label: 'Activities', value: breakdown.activities || 0, icon: Ticket, color: 'text-purple-500' },
        { label: 'Miscellaneous', value: breakdown.miscellaneous || 0, icon: Package, color: 'text-gray-500' },
        { label: 'Buffer (10%)', value: breakdown.buffer_10_percent || 0, icon: Shield, color: 'text-amber-500' },
    ]

    return (
        <div className="space-y-4">
            {/* Budget Items */}
            <div className="space-y-2">
                {items.filter(item => item.value > 0).map((item, index) => (
                    <div key={index} className="flex items-center justify-between py-2">
                        <div className="flex items-center gap-2">
                            <item.icon className={`w-4 h-4 ${item.color}`} />
                            <span className="text-sm text-gray-600">{item.label}</span>
                        </div>
                        <span className="text-sm font-medium text-gray-800">
                            {formatCurrency(item.value)}
                        </span>
                    </div>
                ))}
            </div>

            {/* Divider */}
            <hr className="border-gray-200" />

            {/* Totals */}
            <div className="space-y-2">
                {/* Support both formats */}
                {hasDailyBreakdown ? (
                    <>
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-600">Daily Total (per person)</span>
                            <span className="text-sm font-medium text-gray-700">
                                {formatCurrency((data as any).daily_total_per_person || 0)}
                            </span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-700">Total (per person)</span>
                            <span className="text-lg font-bold text-gray-900">
                                {formatCurrency((data as any).total_per_person || 0)}
                            </span>
                        </div>
                        {(data as any).travelers > 1 && (
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-600">Total for {(data as any).travelers} travelers</span>
                                <span className="text-sm font-medium text-gray-700">
                                    {formatCurrency((data as any).total_for_group || 0)}
                                </span>
                            </div>
                        )}
                    </>
                ) : (
                    <>
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-700">Total (with buffer)</span>
                            <span className="text-lg font-bold text-gray-900">
                                {formatCurrency(data.total_with_buffer || 0)}
                            </span>
                        </div>

                        {data.budget_limit !== undefined && data.budget_limit > 0 && (
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-600">Budget Limit</span>
                                <span className="text-sm font-medium text-gray-700">
                                    {formatCurrency(data.budget_limit)}
                                </span>
                            </div>
                        )}

                        {data.remaining_budget !== undefined && (
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-600">Remaining</span>
                                <span className={`text-sm font-medium ${data.remaining_budget >= 0 ? 'text-emerald-600' : 'text-red-600'
                                    }`}>
                                    {formatCurrency(Math.abs(data.remaining_budget))}
                                    {data.remaining_budget < 0 && ' over'}
                                </span>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Progress Bar */}
            {percentageUsed > 0 && (
                <div className="space-y-1">
                    <div className="flex justify-between text-xs text-gray-500">
                        <span>Budget usage</span>
                        <span>{Math.round(percentageUsed)}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all duration-500 ${percentageUsed > 100
                                ? 'bg-red-500'
                                : percentageUsed > 90
                                    ? 'bg-amber-500'
                                    : 'bg-emerald-500'
                                }`}
                            style={{ width: `${Math.min(percentageUsed, 100)}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Status Badge */}
            <div className={`flex items-center gap-2 p-3 rounded-lg ${withinBudget ? 'bg-emerald-50' : 'bg-amber-50'
                }`}>
                {withinBudget ? (
                    <CheckCircle className="w-5 h-5 text-emerald-500" />
                ) : (
                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                )}
                <span className={`text-sm font-medium ${withinBudget ? 'text-emerald-700' : 'text-amber-700'
                    }`}>
                    {withinBudget ? 'Within budget ✓' : 'Budget exceeded - see recommendations'}
                </span>
            </div>

            {/* Recommendations / Tips */}
            {(data.recommendations || (data as any).tips) && (data.recommendations || (data as any).tips).length > 0 && (
                <div className="space-y-1">
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tips</p>
                    {(data.recommendations || (data as any).tips).map((rec: string, index: number) => (
                        <p key={index} className="text-sm text-gray-600">• {rec}</p>
                    ))}
                </div>
            )}
        </div>
    )
}
