import { useState, useRef } from 'react'
import { ChevronDown, ExternalLink, Download, Loader2 } from 'lucide-react'
import { formatCurrency, formatDate } from '@/lib/utils'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import DayPlan from './DayPlan'
import BudgetBreakdown from './BudgetBreakdown'

interface ItineraryDisplayProps {
    data: any
}

/** The signature mark: where this section's numbers came from. */
function ProvenanceStamp({ source }: { source?: string }) {
    if (!source) return null

    const isLive = /Real Data|SerpAPI|RapidAPI|Foursquare/.test(source)

    return (
        <span
            className={`stamp-mark animate-stamp ${isLive ? 'stamp-live' : 'stamp-est'}`}
            title={source}
        >
            {isLive ? 'Live' : 'Est.'}
        </span>
    )
}

export default function ItineraryDisplay({ data }: ItineraryDisplayProps) {
    const [openSection, setOpenSection] = useState<string | null>('itinerary')
    const [isDownloading, setIsDownloading] = useState(false)
    const itineraryRef = useRef<HTMLDivElement>(null)

    const collected = data?.collected_data || {}

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
    const attractionsData = parseIfNeeded(collected?.attractions)
    const budget = parseIfNeeded(collected?.budget)
    const tripParams = parseIfNeeded(collected?.trip_params)

    const itinerary = itineraryData
    const flights = Array.isArray(flightsData) ? flightsData : (flightsData?.flights || [])
    const hotels = Array.isArray(hotelsData) ? hotelsData : (hotelsData?.hotels || [])
    const restaurants = Array.isArray(restaurantsData) ? restaurantsData : (restaurantsData?.restaurants || [])
    const attractions = Array.isArray(attractionsData) ? attractionsData : (attractionsData?.attractions || [])

    const destination =
        tripParams?.destination || itinerary?.destination || budget?.destination ||
        flightsData?.destination || data?.destination || 'Destination'
    const origin = tripParams?.origin || flightsData?.origin || ''

    const rawDuration =
        tripParams?.days || itinerary?.duration_days || itinerary?.duration ||
        budget?.duration_days || data?.duration_days || '?'
    const duration = typeof rawDuration === 'string' ? rawDuration.replace(/\s*days?\s*/i, '') : rawDuration

    const startDate = tripParams?.start_date || itinerary?.start_date || null
    const endDate = tripParams?.end_date || null

    const dailyPlan = itinerary?.daily_plan || itinerary?.days || []
    const bookingLinks = itinerary?.booking_links || {}

    const toggle = (section: string) => setOpenSection(openSection === section ? null : section)

    const handleDownloadPDF = async () => {
        if (!itineraryRef.current || isDownloading) return
        try {
            setIsDownloading(true)
            const canvas = await html2canvas(itineraryRef.current, {
                scale: 2,
                logging: false,
                useCORS: true,
                backgroundColor: '#F2F5EE',
            })
            const imgData = canvas.toDataURL('image/png')
            const pdf = new jsPDF('p', 'mm', 'a4')
            const pdfWidth = pdf.internal.pageSize.getWidth()
            const pdfHeight = pdf.internal.pageSize.getHeight()
            const imgHeight = (canvas.height * pdfWidth) / canvas.width

            let heightLeft = imgHeight
            let position = 0
            pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight)
            heightLeft -= pdfHeight
            while (heightLeft >= 0) {
                position = heightLeft - imgHeight
                pdf.addPage()
                pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight)
                heightLeft -= pdfHeight
            }
            pdf.save(`${String(destination).replace(/ /g, '_')}_itinerary.pdf`)
        } catch (error) {
            console.error('PDF generation failed:', error)
        } finally {
            setIsDownloading(false)
        }
    }

    return (
        <div ref={itineraryRef}>
            {/* ---- The stub: route, dates, party ------------------------- */}
            <div className="flex items-start justify-between gap-4 mb-1">
                <p className="field-label">Trip plan</p>
                <button
                    onClick={handleDownloadPDF}
                    disabled={isDownloading}
                    className="btn-quiet -mt-1.5"
                    title="Download as PDF"
                >
                    {isDownloading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                        <Download className="w-3.5 h-3.5" />
                    )}
                    PDF
                </button>
            </div>

            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-4">
                {origin && (
                    <>
                        <span className="data text-sm uppercase tracking-[0.12em] text-muted">{origin}</span>
                        <span aria-hidden className="text-muted">→</span>
                    </>
                )}
                <span className="display text-3xl sm:text-[2.5rem] text-ink">{destination}</span>
            </div>

            <dl className="grid grid-cols-3 gap-4 pb-5 mb-5 border-b border-dashed border-rule">
                <div>
                    <dt className="field-label">Nights</dt>
                    <dd className="data text-sm text-ink tabular-nums mt-1">{duration}</dd>
                </div>
                <div>
                    <dt className="field-label">Depart</dt>
                    <dd className="data text-sm text-ink mt-1">
                        {startDate ? formatDate(startDate) : 'Flexible'}
                    </dd>
                </div>
                <div>
                    <dt className="field-label">Return</dt>
                    <dd className="data text-sm text-ink mt-1">
                        {endDate ? formatDate(endDate) : 'Flexible'}
                    </dd>
                </div>
            </dl>

            <div className="space-y-px">
                {flights.length > 0 && (
                    <Section
                        title="Flights"
                        stamp={<ProvenanceStamp source={flightsData?.source} />}
                        count={flights.length}
                        isOpen={openSection === 'flights'}
                        onToggle={() => toggle('flights')}
                    >
                        <ul className="space-y-px">
                            {flights.slice(0, 3).map((flight: any, index: number) => (
                                <li key={index} className="flex items-baseline justify-between gap-4 py-3 border-t border-rule/50 first:border-t-0">
                                    <div className="min-w-0">
                                        <p className="text-sm text-ink">{flight.airline}</p>
                                        <p className="data text-[0.6875rem] text-muted mt-0.5">
                                            {flight.departure_time || flight.departure || ''}
                                            {(flight.arrival_time || flight.arrival) && ' → '}
                                            {flight.arrival_time || flight.arrival || ''}
                                            {flight.duration && ` · ${flight.duration}`}
                                        </p>
                                    </div>
                                    <div className="text-right shrink-0">
                                        <p className="data text-sm text-ink tabular-nums">{formatCurrency(flight.price)}</p>
                                        {flight.booking_link && (
                                            <a
                                                href={flight.booking_link}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="data inline-flex items-center gap-1 text-[0.625rem] uppercase tracking-[0.1em] text-stamp hover:underline mt-0.5"
                                            >
                                                Book <ExternalLink className="w-2.5 h-2.5" />
                                            </a>
                                        )}
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </Section>
                )}

                {hotels.length > 0 && (
                    <Section
                        title="Stays"
                        stamp={<ProvenanceStamp source={hotelsData?.source} />}
                        count={hotels.length}
                        isOpen={openSection === 'hotels'}
                        onToggle={() => toggle('hotels')}
                    >
                        <ul className="space-y-px">
                            {hotels.slice(0, 4).map((hotel: any, index: number) => (
                                <li key={index} className="flex items-baseline justify-between gap-4 py-3 border-t border-rule/50 first:border-t-0">
                                    <div className="min-w-0">
                                        <p className="text-sm text-ink truncate">{hotel.name}</p>
                                        {hotel.rating > 0 && (
                                            <p className="data text-[0.6875rem] text-muted mt-0.5">
                                                Rated {hotel.rating}
                                            </p>
                                        )}
                                    </div>
                                    <p className="data text-sm text-ink tabular-nums shrink-0">
                                        {formatCurrency(hotel.price_per_night)}
                                        <span className="text-muted text-[0.6875rem]"> /night</span>
                                    </p>
                                </li>
                            ))}
                        </ul>
                    </Section>
                )}

                {dailyPlan.length > 0 && (
                    <Section
                        title="Day by day"
                        count={dailyPlan.length}
                        isOpen={openSection === 'itinerary'}
                        onToggle={() => toggle('itinerary')}
                    >
                        <div className="space-y-6">
                            {dailyPlan.map((day: any, index: number) => (
                                <DayPlan key={index} day={day} />
                            ))}
                        </div>
                    </Section>
                )}

                {restaurants.length > 0 && (
                    <Section
                        title="Eateries"
                        stamp={<ProvenanceStamp source={restaurantsData?.source} />}
                        count={restaurants.length}
                        isOpen={openSection === 'restaurants'}
                        onToggle={() => toggle('restaurants')}
                    >
                        <ul className="space-y-px">
                            {restaurants.slice(0, 6).map((restaurant: any, index: number) => (
                                <li key={index} className="flex items-baseline justify-between gap-4 py-3 border-t border-rule/50 first:border-t-0">
                                    <div className="min-w-0">
                                        <p className="text-sm text-ink truncate">{restaurant.name}</p>
                                        {restaurant.cuisine && (
                                            <p className="data text-[0.6875rem] text-muted mt-0.5">{restaurant.cuisine}</p>
                                        )}
                                    </div>
                                    {restaurant.rating > 0 && (
                                        <p className="data text-[0.6875rem] text-muted tabular-nums shrink-0">
                                            {restaurant.rating}
                                        </p>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </Section>
                )}

                {attractions.length > 0 && (
                    <Section
                        title="Sights"
                        stamp={<ProvenanceStamp source={attractionsData?.source} />}
                        count={attractions.length}
                        isOpen={openSection === 'attractions'}
                        onToggle={() => toggle('attractions')}
                    >
                        <ul className="space-y-px">
                            {attractions.slice(0, 8).map((attraction: any, index: number) => (
                                <li key={index} className="flex items-baseline justify-between gap-4 py-3 border-t border-rule/50 first:border-t-0">
                                    <p className="text-sm text-ink truncate">{attraction.name}</p>
                                    {attraction.kind && (
                                        <p className="data text-[0.625rem] uppercase tracking-[0.1em] text-muted shrink-0">
                                            {attraction.kind}
                                        </p>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </Section>
                )}

                {budget && Object.keys(budget).length > 0 && (
                    <Section
                        title="Budget"
                        isOpen={openSection === 'budget'}
                        onToggle={() => toggle('budget')}
                    >
                        <BudgetBreakdown data={budget} />
                    </Section>
                )}
            </div>

            {bookingLinks && Object.keys(bookingLinks).length > 0 && (
                <div className="pt-5 mt-5 border-t border-rule">
                    <p className="field-label mb-3">Booking</p>
                    <div className="flex flex-wrap gap-2">
                        {Object.entries({ ...(bookingLinks.flights || {}), ...(bookingLinks.hotels || {}) }).map(
                            ([name, url]: [string, any]) => (
                                <a
                                    key={name}
                                    href={url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn-quiet"
                                >
                                    {name} <ExternalLink className="w-3 h-3" />
                                </a>
                            )
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}

function Section({
    title,
    stamp,
    count,
    isOpen,
    onToggle,
    children,
}: {
    title: string
    stamp?: React.ReactNode
    count?: number
    isOpen: boolean
    onToggle: () => void
    children: React.ReactNode
}) {
    return (
        <div className="border-t border-rule last:border-b">
            <button
                onClick={onToggle}
                aria-expanded={isOpen}
                className="w-full flex items-center justify-between gap-3 py-3.5 text-left group"
            >
                <span className="flex items-center gap-3 min-w-0">
                    <span className="text-sm text-ink">{title}</span>
                    {typeof count === 'number' && (
                        <span className="data text-[0.625rem] text-muted tabular-nums">{count}</span>
                    )}
                </span>
                <span className="flex items-center gap-3 shrink-0">
                    {stamp}
                    <ChevronDown
                        className={`w-4 h-4 text-muted transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    />
                </span>
            </button>
            {isOpen && <div className="pb-5 animate-rise">{children}</div>}
        </div>
    )
}
