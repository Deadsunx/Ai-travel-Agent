'use client'

import { useState } from 'react'
import { createManualPlan } from '@/lib/api-client'
import { IDLE_SOURCES, SourceKey, SourceMap } from '@/components/ui/SourceLedger'

interface ManualPlanningFormProps {
    onItineraryGenerated: (data: any) => void
    onSourcesChange?: (sources: SourceMap) => void
}

const CUISINES = [
    { value: 'any', label: 'No preference' },
    { value: 'local', label: 'Local cooking' },
    { value: 'vegetarian', label: 'Vegetarian' },
    { value: 'seafood', label: 'Seafood' },
    { value: 'street food', label: 'Street food' },
]

const TRIP_STYLES = [
    { value: 'relaxed', label: 'Relaxed' },
    { value: 'adventure', label: 'Adventure' },
    { value: 'cultural', label: 'Cultural' },
    { value: 'food', label: 'Food' },
    { value: 'budget', label: 'Budget' },
]

/** Mirror the ledger rows off a completed plan, as the chat path does live. */
function sourcesFromPlan(collected: any): SourceMap {
    const read = (section: any, listKey: string) => {
        const list = section?.[listKey] || []
        const isLive = /Real Data/.test(section?.source || '')
        return { state: (list.length ? (isLive ? 'live' : 'est') : 'waiting') as any, count: list.length }
    }
    return {
        flights: read(collected?.flights, 'flights'),
        stays: read(collected?.hotels, 'hotels'),
        eateries: read(collected?.restaurants, 'restaurants'),
        sights: read(collected?.attractions, 'attractions'),
    }
}

export default function ManualPlanningForm({
    onItineraryGenerated,
    onSourcesChange,
}: ManualPlanningFormProps) {
    const today = new Date().toISOString().split('T')[0]
    const inTwoWeeks = new Date(Date.now() + 14 * 864e5).toISOString().split('T')[0]
    const threeDaysLater = new Date(Date.now() + 17 * 864e5).toISOString().split('T')[0]

    const [formData, setFormData] = useState({
        origin: '',
        destination: '',
        departureDate: inTwoWeeks,
        returnDate: threeDaysLater,
        passengers: 1,
        budget: 30000,
        preferences: 'any',
        tripStyle: 'relaxed',
    })
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState('')

    const nights = (() => {
        const from = new Date(formData.departureDate).getTime()
        const to = new Date(formData.returnDate).getTime()
        const days = Math.round((to - from) / 864e5)
        return Number.isFinite(days) ? days : 0
    })()

    const set = (patch: Partial<typeof formData>) => setFormData({ ...formData, ...patch })

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')

        if (nights < 1) {
            setError('The return date must be after the departure date.')
            return
        }

        setIsLoading(true)
        onSourcesChange?.({
            flights: { state: 'searching', count: 0 },
            stays: { state: 'searching', count: 0 },
            eateries: { state: 'searching', count: 0 },
            sights: { state: 'searching', count: 0 },
        })

        try {
            const data = await createManualPlan({
                origin: formData.origin,
                destination: formData.destination,
                departure_date: formData.departureDate,
                return_date: formData.returnDate,
                passengers: formData.passengers,
                budget: formData.budget,
                preferences: formData.preferences,
                trip_style: formData.tripStyle,
            })

            onSourcesChange?.(sourcesFromPlan(data?.collected_data))
            onItineraryGenerated(data)
        } catch (err) {
            onSourcesChange?.(IDLE_SOURCES)
            setError(err instanceof Error ? err.message : 'Could not reach the desk.')
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <form onSubmit={handleSubmit}>
            <div className="flex items-baseline justify-between gap-4 pb-4 mb-5 border-b border-rule">
                <p className="field-label">Booking slip</p>
                <p className="data text-[0.625rem] text-muted/70">No AI</p>
            </div>

            <fieldset disabled={isLoading} className="space-y-5 disabled:opacity-60">
                <div className="grid sm:grid-cols-2 gap-4">
                    <Field label="From" htmlFor="origin">
                        <input
                            id="origin"
                            type="text"
                            required
                            placeholder="Delhi"
                            className="desk-input"
                            value={formData.origin}
                            onChange={(e) => set({ origin: e.target.value })}
                        />
                    </Field>

                    <Field label="To" htmlFor="destination">
                        <input
                            id="destination"
                            type="text"
                            required
                            placeholder="Udaipur"
                            className="desk-input"
                            value={formData.destination}
                            onChange={(e) => set({ destination: e.target.value })}
                        />
                    </Field>

                    <Field label="Depart" htmlFor="departure">
                        <input
                            id="departure"
                            type="date"
                            required
                            min={today}
                            className="desk-input data"
                            value={formData.departureDate}
                            onChange={(e) => set({ departureDate: e.target.value })}
                        />
                    </Field>

                    <Field
                        label="Return"
                        htmlFor="return"
                        hint={nights > 0 ? `${nights} night${nights === 1 ? '' : 's'}` : undefined}
                    >
                        <input
                            id="return"
                            type="date"
                            required
                            min={formData.departureDate || today}
                            className="desk-input data"
                            value={formData.returnDate}
                            onChange={(e) => set({ returnDate: e.target.value })}
                        />
                    </Field>

                    <Field label="Travellers" htmlFor="passengers">
                        <input
                            id="passengers"
                            type="number"
                            min={1}
                            max={10}
                            className="desk-input data"
                            value={formData.passengers}
                            onChange={(e) => set({ passengers: Math.max(1, parseInt(e.target.value) || 1) })}
                        />
                    </Field>

                    <Field label="Budget, total ₹" htmlFor="budget">
                        <input
                            id="budget"
                            type="number"
                            required
                            min={1000}
                            step={1000}
                            className="desk-input data"
                            value={formData.budget}
                            onChange={(e) => set({ budget: Math.max(0, parseInt(e.target.value) || 0) })}
                        />
                    </Field>
                </div>

                <Field label="Food" htmlFor="preferences">
                    <select
                        id="preferences"
                        className="desk-input"
                        value={formData.preferences}
                        onChange={(e) => set({ preferences: e.target.value })}
                    >
                        {CUISINES.map((c) => (
                            <option key={c.value} value={c.value} className="bg-card text-ink">
                                {c.label}
                            </option>
                        ))}
                    </select>
                </Field>

                <div>
                    <p className="field-label mb-2">Pace</p>
                    <div className="flex flex-wrap gap-2">
                        {TRIP_STYLES.map((style) => (
                            <button
                                key={style.value}
                                type="button"
                                onClick={() => set({ tripStyle: style.value })}
                                data-active={formData.tripStyle === style.value}
                                className="btn-quiet"
                            >
                                {style.label}
                            </button>
                        ))}
                    </div>
                </div>
            </fieldset>

            {error && (
                <p className="mt-5 pl-3 border-l-2 border-est text-sm text-est animate-rise">{error}</p>
            )}

            <div className="flex items-center justify-between gap-4 pt-5 mt-5 border-t border-rule">
                <p className="data text-[0.625rem] text-muted">
                    {isLoading ? 'Searching…' : 'Prices checked live at the source'}
                </p>
                <button type="submit" disabled={isLoading} className="btn-ink shrink-0">
                    {isLoading ? 'Working' : 'Build plan'}
                </button>
            </div>
        </form>
    )
}

function Field({
    label,
    htmlFor,
    hint,
    children,
}: {
    label: string
    htmlFor: string
    hint?: string
    children: React.ReactNode
}) {
    return (
        <div>
            <div className="flex items-baseline justify-between gap-2 mb-1.5">
                <label htmlFor={htmlFor} className="field-label">
                    {label}
                </label>
                {hint && <span className="data text-[0.625rem] text-muted/80">{hint}</span>}
            </div>
            {children}
        </div>
    )
}
