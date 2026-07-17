import { useState, useRef } from 'react'
import {
    MapPin, Calendar, DollarSign, Plane, Hotel, Utensils,
    ChevronDown, ChevronUp, ExternalLink, Clock, Star, CheckCircle, AlertCircle,
    Download, Loader2
} from 'lucide-react'
import { formatCurrency, formatDate } from '@/lib/utils'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import DayPlan from './DayPlan'
import BudgetBreakdown from './BudgetBreakdown'

interface ItineraryDisplayProps {
    data: any
}

// Data Source Badge Component
function DataSourceBadge({ source }: { source?: string }) {
    if (!source) return null

    const isReal = source.includes('Real Data') || source.includes('SerpAPI') || source.includes('RapidAPI') || source.includes('Foursquare')

    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${isReal
            ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
            : 'bg-gray-100 text-gray-600 border border-gray-200'
            }`}>
            {isReal ? (
                <>
                    <CheckCircle className="w-3 h-3" />
                    Live Data
                </>
            ) : (
                <>
                    <AlertCircle className="w-3 h-3" />
                    Demo Data
                </>
            )}
        </span>
    )
}

export default function ItineraryDisplay({ data }: ItineraryDisplayProps) {
    const [expandedSection, setExpandedSection] = useState<string | null>('itinerary')
    const [isDownloading, setIsDownloading] = useState(false)
    const itineraryRef = useRef<HTMLDivElement>(null)

    // Extract itinerary data from the response
    const collected = data?.collected_data || {}

    // Helper function to parse JSON strings or return the object
    const parseIfNeeded = (value: any) => {
        if (typeof value === 'string') {
            try {
                return JSON.parse(value)
            } catch {
                return {}
            }
        }
        return value || {}
    }

    const itineraryData = parseIfNeeded(collected?.itinerary || data?.itinerary)
    const flightsData = parseIfNeeded(collected?.flights)
    const hotelsData = parseIfNeeded(collected?.hotels)
    const restaurantsData = parseIfNeeded(collected?.restaurants)
    const budgetData = parseIfNeeded(collected?.budget)

    const itinerary = itineraryData
    const flights = Array.isArray(flightsData) ? flightsData : (flightsData?.flights || [])
    const hotels = Array.isArray(hotelsData) ? hotelsData : (hotelsData?.hotels || [])
    const restaurants = Array.isArray(restaurantsData) ? restaurantsData : (restaurantsData?.restaurants || [])
    const budget = budgetData

    // Extract destination from any available source (itinerary > budget > flights > fallback)
    const destination = itinerary?.destination || budget?.destination || flightsData?.destination || data?.destination || 'Your Destination'

    // Parse duration: check itinerary, budget, or fallback
    const rawDuration = itinerary?.duration_days || itinerary?.duration || budget?.duration_days || data?.duration_days || '?'
    const duration = typeof rawDuration === 'string' ? rawDuration.replace(/\s*days?\s*/i, '') : rawDuration

    // Extract start date from itinerary, budget, or first flight departure
    const startDate = itinerary?.start_date || (() => {
        if (flights.length > 0) {
            const dep = flights[0].departure_time || flights[0].departure || ''
            const datePart = dep.split(' ')[0] // "2026-03-05 20:25" -> "2026-03-05"
            return datePart && datePart.match(/^\d{4}-\d{2}-\d{2}$/) ? datePart : null
        }
        return null
    })()

    const dailyPlan = itinerary?.daily_plan || itinerary?.days || []
    const bookingLinks = itinerary?.booking_links || {}

    const toggleSection = (section: string) => {
        setExpandedSection(expandedSection === section ? null : section)
    }

    const handleDownloadPDF = async () => {
        if (!itineraryRef.current || isDownloading) return

        try {
            setIsDownloading(true)

            // Open all sections for the PDF
            const previousSection = expandedSection
            setExpandedSection('all') // Hack to ensure everything renders? No, simpler to just rely on expanded logic or force expansion
            // For now, let's just capture what's visible, or maybe force consistent state
            // Better UX: Capture the whole container. If sections are collapsed, they won't show.
            // Let's assume the user expands what they want, or we can't easily force it without re-rendering flicker.

            const canvas = await html2canvas(itineraryRef.current, {
                scale: 2,
                logging: false,
                useCORS: true,
                backgroundColor: '#ffffff'
            })

            const imgData = canvas.toDataURL('image/png')
            const pdf = new jsPDF('p', 'mm', 'a4')
            const pdfWidth = pdf.internal.pageSize.getWidth()
            const pdfHeight = pdf.internal.pageSize.getHeight()
            const imgWidth = pdfWidth
            const imgHeight = (canvas.height * imgWidth) / canvas.width

            let heightLeft = imgHeight
            let position = 0

            pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
            heightLeft -= pdfHeight

            while (heightLeft >= 0) {
                position = heightLeft - imgHeight
                pdf.addPage()
                pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
                heightLeft -= pdfHeight
            }

            pdf.save(`${destination.replace(/ /g, '_')}_Itinerary.pdf`)
        } catch (error) {
            console.error('PDF generation failed:', error)
        } finally {
            setIsDownloading(false)
        }
    }

    return (
        <div className="space-y-4" ref={itineraryRef}>
            {/* Header */}
            <div className="text-center pb-4 border-b border-gray-100 relative">
                <button
                    onClick={handleDownloadPDF}
                    disabled={isDownloading}
                    className="absolute right-0 top-0 p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-full transition-colors"
                    title="Download Itinerary PDF"
                >
                    {isDownloading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                        <Download className="w-5 h-5" />
                    )}
                </button>

                <h2 className="text-2xl font-bold text-gray-800 flex items-center justify-center gap-2">
                    <MapPin className="w-6 h-6 text-primary-500" />
                    {destination}
                </h2>
                <p className="text-gray-500 mt-1">
                    {duration} days • {startDate ? formatDate(startDate) : 'Flexible dates'}
                </p>
                {itinerary?.budget_status && (
                    <span className={`inline-flex items-center gap-1 mt-2 px-3 py-1 rounded-full text-sm font-medium
            ${itinerary.budget_status.includes('✅') ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                        {itinerary.budget_status}
                    </span>
                )}
            </div>

            {/* Flights Section */}
            {flights.length > 0 && (
                <Section
                    title={
                        <div className="flex items-center gap-2">
                            <span>Flights</span>
                            <DataSourceBadge source={flightsData?.source} />
                        </div>
                    }
                    icon={<Plane className="w-5 h-5" />}
                    isExpanded={expandedSection === 'flights'}
                    onToggle={() => toggleSection('flights')}
                >
                    <div className="space-y-3">
                        {flights.slice(0, 3).map((flight: any, index: number) => (
                            <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <div>
                                    <p className="font-medium text-gray-800">{flight.airline}</p>
                                    <p className="text-sm text-gray-500">
                                        {flight.departure_time || flight.departure || ''} → {flight.arrival_time || flight.arrival || ''}
                                        {flight.duration && <span className="ml-2 text-gray-400">({flight.duration})</span>}
                                    </p>
                                    {flight.flight_number && flight.flight_number !== 'N/A' && (
                                        <p className="text-xs text-gray-400">{flight.flight_number}</p>
                                    )}
                                </div>
                                <div className="text-right">
                                    <p className="font-bold text-primary-600">
                                        {formatCurrency(flight.price)}
                                    </p>
                                    {flight.booking_link && (
                                        <a href={flight.booking_link} target="_blank" rel="noopener noreferrer"
                                            className="text-xs text-primary-500 hover:underline flex items-center gap-1">
                                            Book <ExternalLink className="w-3 h-3" />
                                        </a>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {/* Hotels Section */}
            {hotels.length > 0 && (
                <Section
                    title={
                        <div className="flex items-center gap-2">
                            <span>Accommodations</span>
                            <DataSourceBadge source={hotelsData?.source} />
                        </div>
                    }
                    icon={<Hotel className="w-5 h-5" />}
                    isExpanded={expandedSection === 'hotels'}
                    onToggle={() => toggleSection('hotels')}
                >
                    <div className="space-y-3">
                        {hotels.slice(0, 3).map((hotel: any, index: number) => (
                            <div key={index} className="p-3 bg-gray-50 rounded-lg">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="font-medium text-gray-800">{hotel.name}</p>
                                        {hotel.rating && (
                                            <div className="flex items-center gap-1 mt-1">
                                                <Star className="w-4 h-4 text-amber-400 fill-current" />
                                                <span className="text-sm text-gray-600">{hotel.rating}</span>
                                            </div>
                                        )}
                                    </div>
                                    <div className="text-right">
                                        <p className="font-bold text-primary-600">
                                            {formatCurrency(hotel.price_per_night)}<span className="text-xs text-gray-500">/night</span>
                                        </p>
                                    </div>
                                </div>
                                {hotel.amenities && hotel.amenities.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-2">
                                        {hotel.amenities.slice(0, 4).map((amenity: string, i: number) => (
                                            <span key={i} className="px-2 py-0.5 bg-white text-xs text-gray-600 rounded">
                                                {amenity}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {/* Daily Itinerary Section */}
            {dailyPlan.length > 0 && (
                <Section
                    title="Day-by-Day Itinerary"
                    icon={<Calendar className="w-5 h-5" />}
                    isExpanded={expandedSection === 'itinerary'}
                    onToggle={() => toggleSection('itinerary')}
                >
                    <div className="space-y-4">
                        {dailyPlan.map((day: any, index: number) => (
                            <DayPlan key={index} day={day} />
                        ))}
                    </div>
                </Section>
            )}

            {/* Restaurants Section */}
            {restaurants.length > 0 && (
                <Section
                    title={
                        <div className="flex items-center gap-2">
                            <span>Restaurants</span>
                            <DataSourceBadge source={restaurantsData?.source} />
                        </div>
                    }
                    icon={<Utensils className="w-5 h-5" />}
                    isExpanded={expandedSection === 'restaurants'}
                    onToggle={() => toggleSection('restaurants')}
                >
                    <div className="grid gap-3">
                        {restaurants.slice(0, 6).map((restaurant: any, index: number) => (
                            <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <div>
                                    <p className="font-medium text-gray-800">{restaurant.name}</p>
                                    <div className="flex items-center gap-2 mt-1">
                                        {restaurant.rating && (
                                            <span className="flex items-center gap-1 text-sm text-gray-600">
                                                <Star className="w-3 h-3 text-amber-400 fill-current" />
                                                {restaurant.rating}
                                            </span>
                                        )}
                                        {restaurant.price_level && (
                                            <span className="text-sm text-gray-500">{restaurant.price_level}</span>
                                        )}
                                    </div>
                                </div>
                                {restaurant.link && (
                                    <a href={restaurant.link} target="_blank" rel="noopener noreferrer"
                                        className="text-primary-500 hover:text-primary-600">
                                        <ExternalLink className="w-4 h-4" />
                                    </a>
                                )}
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {/* Budget Section */}
            {budget && Object.keys(budget).length > 0 && (
                <Section
                    title="Budget Breakdown"
                    icon={<DollarSign className="w-5 h-5" />}
                    isExpanded={expandedSection === 'budget'}
                    onToggle={() => toggleSection('budget')}
                >
                    <BudgetBreakdown data={budget} />
                </Section>
            )}

            {/* Booking Links */}
            {bookingLinks && Object.keys(bookingLinks).length > 0 && (
                <div className="pt-4 border-t border-gray-100">
                    <h3 className="text-sm font-medium text-gray-700 mb-3">Quick Booking Links</h3>
                    <div className="flex flex-wrap gap-2">
                        {bookingLinks.flights && Object.entries(bookingLinks.flights).map(([name, url]: [string, any]) => (
                            <a key={name} href={url} target="_blank" rel="noopener noreferrer"
                                className="px-3 py-1.5 bg-primary-50 text-primary-700 rounded-full text-sm 
                          hover:bg-primary-100 transition-colors flex items-center gap-1">
                                {name} <ExternalLink className="w-3 h-3" />
                            </a>
                        ))}
                        {bookingLinks.hotels && Object.entries(bookingLinks.hotels).map(([name, url]: [string, any]) => (
                            <a key={name} href={url} target="_blank" rel="noopener noreferrer"
                                className="px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-full text-sm 
                          hover:bg-emerald-100 transition-colors flex items-center gap-1">
                                {name} <ExternalLink className="w-3 h-3" />
                            </a>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

// Collapsible Section Component
function Section({
    title,
    icon,
    isExpanded,
    onToggle,
    children
}: {
    title: React.ReactNode
    icon: React.ReactNode
    isExpanded: boolean
    onToggle: () => void
    children: React.ReactNode
}) {
    return (
        <div className="border border-gray-100 rounded-xl overflow-hidden">
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
            >
                <div className="flex items-center gap-2 text-gray-700">
                    {icon}
                    <span className="font-medium">{title}</span>
                </div>
                {isExpanded ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                )}
            </button>
            {isExpanded && (
                <div className="p-4">
                    {children}
                </div>
            )}
        </div>
    )
}
