'use client'

import { useEffect, useState } from 'react'
import ChatInterface from '@/components/chat/ChatInterface'
import ManualPlanningForm from '@/components/planning/ManualPlanningForm'
import ItineraryDisplay from '@/components/itinerary/ItineraryDisplay'
import { Sun, Moon } from 'lucide-react'
import { useTheme } from '@/components/ui/ThemeProvider'
import SourceLedger, { IDLE_SOURCES, SourceMap } from '@/components/ui/SourceLedger'
import { fetchModels, ModelOption } from '@/lib/api-client'

/**
 * Shown until the server answers, and kept if it never does — the picker
 * should never be empty. Everything is marked unavailable, because until
 * the server says otherwise we genuinely do not know what it can run.
 */
const UNKNOWN_MODELS: ModelOption[] = [
    { value: 'gemini-flash-latest', label: 'Gemini Flash', kind: 'cloud', available: true, reason: null },
]

// Which planner runs the request: the deterministic pipeline, or the
// multi-agent graph whose desks and critic show up in the transcript.
const PLANNERS = [
    { value: 'graph', label: 'Multi-agent' },
    { value: 'pipeline', label: 'Pipeline' },
]

export default function Home() {
    const [mode, setMode] = useState<'chat' | 'manual'>('chat')
    const [models, setModels] = useState<ModelOption[]>(UNKNOWN_MODELS)
    const [selectedModel, setSelectedModel] = useState<string>('gemini-flash-latest')
    const [selectedPlanner, setSelectedPlanner] = useState<string>('graph')
    const [itinerary, setItinerary] = useState<any>(null)
    const [sources, setSources] = useState<SourceMap>(IDLE_SOURCES)
    const { theme, toggleTheme } = useTheme()

    // Which models this backend can run is the server's answer: local ones
    // need Ollama beside it, which a hosted deployment does not have.
    useEffect(() => {
        let cancelled = false
        fetchModels()
            .then(({ models: listed, default: fallback }) => {
                if (cancelled || !listed?.length) return
                setModels(listed)
                setSelectedModel(fallback)
            })
            .catch(() => {
                // Backend unreachable — keep the placeholder rather than
                // showing an empty picker.
            })
        return () => { cancelled = true }
    }, [])

    // The per-option `title` carries the server's own wording; the note
    // below only needs to appear when something is actually locked.
    const hasLockedModels = models.some(m => !m.available)
    const lockedNote = models.find(m => !m.available)?.reason

    return (
        <main className="min-h-screen">
            {/* ---- Desk bar ------------------------------------------------ */}
            <header className="border-b border-rule">
                <div className="mx-auto max-w-6xl px-5 sm:px-8 h-14 flex items-center justify-between gap-4">
                    <div className="flex items-baseline gap-2.5 min-w-0">
                        <span className="display text-lg text-ink">Travel Desk</span>
                        <span className="data hidden sm:inline text-[0.625rem] tracking-[0.16em] uppercase text-muted">
                            India
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        <label className="sr-only" htmlFor="model">Model</label>
                        <select
                            id="model"
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                            title={lockedNote || undefined}
                            className="data bg-transparent border border-rule rounded-stub text-[0.6875rem] uppercase tracking-[0.1em] text-muted px-2.5 py-2 hover:text-ink focus:outline-none focus-visible:outline-2"
                        >
                            {models.map((m) => (
                                <option
                                    key={m.value}
                                    value={m.value}
                                    disabled={!m.available}
                                    title={m.reason || undefined}
                                    className="bg-card text-ink"
                                >
                                    {/* Locked models stay listed: the point is to show
                                        what the project can do, and how to get it. */}
                                    {m.available ? m.label : `🔒 ${m.label}`}
                                </option>
                            ))}
                        </select>

                        <label className="sr-only" htmlFor="planner">Planner</label>
                        <select
                            id="planner"
                            value={selectedPlanner}
                            onChange={(e) => setSelectedPlanner(e.target.value)}
                            className="data bg-transparent border border-rule rounded-stub text-[0.6875rem] uppercase tracking-[0.1em] text-muted px-2.5 py-2 hover:text-ink focus:outline-none focus-visible:outline-2"
                        >
                            {PLANNERS.map((p) => (
                                <option key={p.value} value={p.value} className="bg-card text-ink">
                                    {p.label}
                                </option>
                            ))}
                        </select>

                        <button
                            onClick={toggleTheme}
                            className="btn-quiet"
                            aria-label={theme === 'dark' ? 'Switch to day stock' : 'Switch to night desk'}
                        >
                            {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
                        </button>
                    </div>
                </div>
            </header>

            {/* ---- Hero: the working instrument ----------------------------- */}
            <section className="mx-auto max-w-6xl px-5 sm:px-8 pt-14 pb-12 sm:pt-20 sm:pb-16">
                <div className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16 lg:items-start">
                    <div className="animate-rise">
                        <p className="field-label mb-5">Trip planning desk</p>
                        <h1 className="display text-[2.75rem] sm:text-6xl lg:text-[4.25rem] text-ink mb-6">
                            Where are
                            <br />
                            you going?
                        </h1>
                        <p className="text-base sm:text-lg leading-relaxed text-muted max-w-md">
                            Tell me in a sentence. I search flights, stays and places to eat,
                            price the whole trip in rupees, and mark every number with where
                            it came from.
                        </p>

                        {/* A disabled <option> cannot be relied on to show a
                            tooltip, so the reason is stated in the page. */}
                        {hasLockedModels && (
                            <p className="mt-5 pl-3 border-l border-rule text-xs leading-relaxed text-muted max-w-md">
                                🔒 The local models are locked here — this deployment has no
                                GPU of its own. Clone the repo and run it alongside Ollama
                                to use them. Gemini runs on Google&apos;s side, so it works
                                from anywhere.
                            </p>
                        )}

                        <div className="mt-8 flex flex-wrap gap-2">
                            <button
                                onClick={() => setMode('chat')}
                                data-active={mode === 'chat'}
                                className="btn-quiet"
                            >
                                Describe it
                            </button>
                            <button
                                onClick={() => setMode('manual')}
                                data-active={mode === 'manual'}
                                className="btn-quiet"
                            >
                                Fill a form
                            </button>
                        </div>
                    </div>

                    <div className="animate-rise lg:mt-2">
                        <SourceLedger sources={sources} />
                    </div>
                </div>
            </section>

            {/* ---- Working area --------------------------------------------- */}
            <section className="mx-auto max-w-6xl px-5 sm:px-8 pb-20">
                <div className={`grid gap-6 ${itinerary ? 'lg:grid-cols-2' : 'max-w-2xl'}`}>
                    <div className="stock p-5 sm:p-6">
                        {mode === 'chat' ? (
                            <ChatInterface
                                onItineraryGenerated={setItinerary}
                                onSourcesChange={setSources}
                                selectedModel={selectedModel}
                                selectedPlanner={selectedPlanner}
                            />
                        ) : (
                            <ManualPlanningForm
                                onItineraryGenerated={setItinerary}
                                onSourcesChange={setSources}
                            />
                        )}
                    </div>

                    {itinerary && (
                        <div className="stock p-5 sm:p-6 animate-rise">
                            <ItineraryDisplay data={itinerary} />
                        </div>
                    )}
                </div>
            </section>

            {/* ---- Colophon --------------------------------------------------- */}
            <footer className="border-t border-rule">
                <div className="mx-auto max-w-6xl px-5 sm:px-8 py-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <p className="data text-[0.625rem] tracking-[0.14em] uppercase text-muted">
                        Fares in INR · Prices change without notice
                    </p>
                    <p className="data text-[0.625rem] tracking-[0.14em] uppercase text-muted">
                        Next.js · FastAPI · Ollama
                    </p>
                </div>
            </footer>
        </main>
    )
}
