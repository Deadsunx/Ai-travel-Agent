'use client'

import { useState } from 'react'
import { Calendar, MapPin, Users, DollarSign, Utensils, Sparkles, Plane } from 'lucide-react'

interface ManualPlanningFormProps {
    onItineraryGenerated: (data: any) => void
}

export default function ManualPlanningForm({ onItineraryGenerated }: ManualPlanningFormProps) {
    const [formData, setFormData] = useState({
        origin: '',
        destination: '',
        departureDate: '',
        returnDate: '',
        passengers: 1,
        budget: 15000,
        preferences: 'any',
        tripStyle: 'relaxed'
    })
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState('')

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setIsLoading(true)

        try {
            const response = await fetch('http://localhost:8000/api/manual-plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    origin: formData.origin,
                    destination: formData.destination,
                    departure_date: formData.departureDate,
                    return_date: formData.returnDate,
                    passengers: formData.passengers,
                    budget: formData.budget,
                    preferences: formData.preferences,
                    trip_style: formData.tripStyle
                })
            })

            const data = await response.json()

            if (data.success) {
                // Pass the entire response, ItineraryDisplay will extract collected_data
                onItineraryGenerated(data)
            } else {
                setError(data.detail || 'Failed to generate itinerary')
            }
        } catch (error) {
            console.error('Error:', error)
            setError('Failed to connect to server. Please try again.')
        } finally {
            setIsLoading(false)
        }
    }

    // Get min date (today) and default dates
    const today = new Date().toISOString().split('T')[0]
    const defaultDeparture = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    const defaultReturn = new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

    return (
        <div className="max-w-4xl mx-auto">
            {/* Info Banner */}
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-xl">
                <p className="text-sm text-blue-800">
                    <strong>💡 Quick Planning:</strong> Fill in the form below to generate your itinerary instantly - no AI chat needed!
                </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* Flight Details Section */}
                <div className="card p-6 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl shadow-lg">
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 text-gray-800">
                        <Plane className="w-5 h-5 text-primary-600" />
                        Travel Details
                    </h3>

                    <div className="grid md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Origin City *
                            </label>
                            <input
                                type="text"
                                placeholder="e.g., Delhi, Mumbai, Bangalore"
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                value={formData.origin}
                                onChange={(e) => setFormData({ ...formData, origin: e.target.value })}
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Destination *
                            </label>
                            <input
                                type="text"
                                placeholder="e.g., Goa, Kerala, Manali"
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                value={formData.destination}
                                onChange={(e) => setFormData({ ...formData, destination: e.target.value })}
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                <Calendar className="w-4 h-4 inline mr-1" />
                                Departure Date *
                            </label>
                            <input
                                type="date"
                                min={today}
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                value={formData.departureDate}
                                onChange={(e) => setFormData({ ...formData, departureDate: e.target.value })}
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                <Calendar className="w-4 h-4 inline mr-1" />
                                Return Date *
                            </label>
                            <input
                                type="date"
                                min={formData.departureDate || today}
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                value={formData.returnDate}
                                onChange={(e) => setFormData({ ...formData, returnDate: e.target.value })}
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                <Users className="w-4 h-4 inline mr-1" />
                                Number of Travelers
                            </label>
                            <input
                                type="number"
                                min="1"
                                max="10"
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                value={formData.passengers}
                                onChange={(e) => setFormData({ ...formData, passengers: parseInt(e.target.value) })}
                            />
                        </div>
                    </div>
                </div>

                {/* Budget & Preferences */}
                <div className="card p-6 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl shadow-lg">
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 text-gray-800">
                        <Sparkles className="w-5 h-5 text-primary-600" />
                        Preferences & Budget
                    </h3>

                    <div className="grid md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                <DollarSign className="w-4 h-4 inline mr-1" />
                                Total Budget (₹) *
                            </label>
                            <input
                                type="number"
                                min="1000"
                                step="1000"
                                placeholder="15000"
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                value={formData.budget}
                                onChange={(e) => setFormData({ ...formData, budget: parseInt(e.target.value) })}
                                required
                            />
                            <p className="mt-1 text-xs text-gray-500">Per person budget for the entire trip</p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                <Utensils className="w-4 h-4 inline mr-1" />
                                Food Preferences
                            </label>
                            <select
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                value={formData.preferences}
                                onChange={(e) => setFormData({ ...formData, preferences: e.target.value })}
                            >
                                <option value="any">Any Cuisine</option>
                                <option value="local">Local Cuisine</option>
                                <option value="vegetarian">Vegetarian</option>
                                <option value="seafood">Seafood</option>
                                <option value="street food">Street Food</option>
                            </select>
                        </div>

                        <div className="md:col-span-2">
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Trip Style
                            </label>
                            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                                {[
                                    { value: 'relaxed', label: '🏖️ Relaxation', emoji: '🏖️' },
                                    { value: 'adventure', label: '🏔️ Adventure', emoji: '🏔️' },
                                    { value: 'cultural', label: '🏛️ Cultural', emoji: '🏛️' },
                                    { value: 'food', label: '🍜 Food Tour', emoji: '🍜' },
                                    { value: 'budget', label: '💰 Budget', emoji: '💰' }
                                ].map((style) => (
                                    <button
                                        key={style.value}
                                        type="button"
                                        onClick={() => setFormData({ ...formData, tripStyle: style.value })}
                                        className={`p-3 rounded-xl border-2 transition-all text-sm font-medium ${formData.tripStyle === style.value
                                            ? 'border-primary-500 bg-primary-50 text-primary-700'
                                            : 'border-gray-200 hover:border-gray-300 text-gray-600'
                                            }`}
                                    >
                                        <div className="text-2xl mb-1">{style.emoji}</div>
                                        <div className="text-xs">{style.label.replace(style.emoji + ' ', '')}</div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                        <strong>Error:</strong> {error}
                    </div>
                )}

                {/* Submit Button */}
                <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-4 px-6 bg-gradient-to-r from-primary-600 to-purple-600 text-white font-semibold text-lg rounded-2xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                >
                    {isLoading ? (
                        <span className="flex items-center justify-center gap-2">
                            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            Generating Your Perfect Itinerary...
                        </span>
                    ) : (
                        '🚀 Generate My Itinerary'
                    )}
                </button>

                <p className="text-center text-xs text-gray-500">
                    This feature works without using AI - perfect for quick planning!
                </p>
            </form>
        </div>
    )
}
