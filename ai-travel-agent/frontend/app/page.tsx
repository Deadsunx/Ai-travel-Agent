'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import ChatInterface from '@/components/chat/ChatInterface'
import ManualPlanningForm from '@/components/planning/ManualPlanningForm'
import ItineraryDisplay from '@/components/itinerary/ItineraryDisplay'
import { Plane, MapPin, Sparkles, Globe2, Calendar, Wallet, Star, TrendingUp, MessageSquare, ClipboardList, Sun, Moon } from 'lucide-react'
import { useTheme } from '@/components/ui/ThemeProvider'
import TravelBackground from '@/components/ui/BackgroundSlider'

export default function Home() {
    const [mode, setMode] = useState<'chat' | 'manual'>('chat')
    const [selectedModel, setSelectedModel] = useState<string>('qwen3:8b')
    const [itinerary, setItinerary] = useState<any>(null)
    const [showItinerary, setShowItinerary] = useState(false)
    const { theme, toggleTheme } = useTheme()

    const handleItineraryGenerated = (data: any) => {
        setItinerary(data)
        setShowItinerary(true)
    }

    return (
        <main className="min-h-screen relative overflow-hidden">
            {/* Travel-themed background */}
            <TravelBackground />

            {/* Header */}
            <header className="bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-100 dark:border-gray-700 sticky top-0 z-50 shadow-sm">
                <div className="container mx-auto px-4 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 via-primary-600 to-accent-500 flex items-center justify-center shadow-lg transform hover:scale-105 transition-transform duration-200">
                                <Plane className="w-6 h-6 text-white" />
                            </div>
                            <div>
                                <h1 className="text-xl font-bold gradient-text">AI Travel Agent</h1>
                                <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                                    <Sparkles className="w-3 h-3" />
                                    Powered by Ollama
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            {/* Model Selector */}
                            <select
                                value={selectedModel}
                                onChange={(e) => setSelectedModel(e.target.value)}
                                className="bg-gray-100 dark:bg-gray-800 border-none rounded-lg text-sm px-3 py-2 focus:ring-2 focus:ring-primary-500 outline-none"
                            >
                                <option value="qwen3:8b">Qwen3:8b</option>
                                <option value="gemma2:9b">Gemma2:9b</option>
                                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                            </select>

                            {/* Dark Mode Toggle */}
                            <button
                                onClick={toggleTheme}
                                className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                                aria-label="Toggle dark mode"
                            >
                                {theme === 'dark' ? (
                                    <Sun className="w-5 h-5 text-yellow-500" />
                                ) : (
                                    <Moon className="w-5 h-5 text-gray-600" />
                                )}
                            </button>
                            <span className="status-badge status-success">
                                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                                Online
                            </span>
                        </div>
                    </div>
                </div>
            </header>

            {/* Hero Section */}
            <section className="relative py-16 px-4 overflow-hidden">
                <div className="container mx-auto">
                    <motion.div
                        className="text-center mb-12"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                    >
                        <div className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-primary-100 to-accent-100 dark:from-primary-900/50 dark:to-accent-900/50 rounded-full text-primary-700 dark:text-primary-300 text-sm font-semibold mb-6 shadow-sm border border-primary-200/50 dark:border-primary-700/50 hover:shadow-md transition-shadow duration-200">
                            <Sparkles className="w-4 h-4 animate-pulse" />
                            AI-Powered Trip Planning
                        </div>
                        <h2 className="text-5xl md:text-6xl font-bold text-gray-900 dark:text-white mb-6 leading-tight">
                            Plan Your <span className="gradient-text relative">
                                Dream Trip
                                <svg className="absolute -bottom-2 left-0 w-full" height="8" viewBox="0 0 200 8" fill="none">
                                    <path d="M0 4 Q50 0, 100 4 T200 4" stroke="url(#gradient)" strokeWidth="3" fill="none" />
                                    <defs>
                                        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                            <stop offset="0%" stopColor="#6366f1" />
                                            <stop offset="100%" stopColor="#ec4899" />
                                        </linearGradient>
                                    </defs>
                                </svg>
                            </span>
                        </h2>
                        <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto leading-relaxed">
                            Tell me where you want to go, and I'll create a complete itinerary with
                            <span className="font-semibold text-primary-600 dark:text-primary-400"> real-time prices</span> for flights, hotels, and restaurants.
                        </p>
                    </motion.div>

                    {/* Feature Cards */}
                    <motion.div
                        className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12 max-w-5xl mx-auto"
                        initial="hidden"
                        animate="visible"
                        variants={{
                            hidden: { opacity: 0 },
                            visible: {
                                opacity: 1,
                                transition: { staggerChildren: 0.1, delayChildren: 0.3 }
                            }
                        }}
                    >
                        {[
                            { icon: Globe2, title: 'Smart Search', color: 'from-blue-400 to-blue-600' },
                            { icon: Calendar, title: 'Custom Plans', color: 'from-purple-400 to-purple-600' },
                            { icon: Wallet, title: 'Budget-Friendly', color: 'from-emerald-400 to-emerald-600' },
                            { icon: TrendingUp, title: 'Real-Time Data', color: 'from-pink-400 to-pink-600' }
                        ].map((feature, index) => (
                            <motion.div
                                key={index}
                                className="group p-4 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-2xl border border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
                                variants={{
                                    hidden: { opacity: 0, y: 20 },
                                    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } }
                                }}
                            >
                                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-3 shadow-lg group-hover:scale-110 transition-transform duration-200`}>
                                    <feature.icon className="w-6 h-6 text-white" />
                                </div>
                                <h3 className="font-semibold text-gray-800 dark:text-gray-200 text-sm">{feature.title}</h3>
                            </motion.div>
                        ))}
                    </motion.div>

                    {/* Sample Prompts */}
                    <div className="flex flex-wrap justify-center gap-3 mb-8">
                        {[
                            { text: '3-day trip to Goa under ₹10,000', icon: '🏖️' },
                            { text: 'Week in Kerala, food-focused', icon: '🍛' },
                            { text: 'Mumbai weekend getaway', icon: '🌆' },
                            { text: 'Honeymoon in Maldives', icon: '🏝️' }
                        ].map((prompt, index) => (
                            <button
                                key={index}
                                className="group px-5 py-3 bg-white/90 backdrop-blur-sm rounded-full text-sm text-gray-700 font-medium
                         border-2 border-gray-200 hover:border-primary-400 hover:bg-gradient-to-r hover:from-primary-50 hover:to-accent-50
                         transition-all duration-300 flex items-center gap-2 shadow-sm hover:shadow-md transform hover:scale-105"
                            >
                                <span className="text-lg group-hover:animate-bounce">{prompt.icon}</span>
                                <MapPin className="w-4 h-4 text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                                {prompt.text}
                            </button>
                        ))}
                    </div>
                </div>
            </section>

            {/* Mode Toggle */}
            <section className="container mx-auto px-4 mb-8">
                <div className="flex justify-center gap-3" >
                    <button
                        onClick={() => setMode('chat')}
                        className={`px-8 py-4 rounded-2xl font-semibold text-base transition-all duration-300 flex items-center gap-2 shadow-lg ${mode === 'chat'
                            ? 'bg-gradient-to-r from-primary-600 to-purple-600 text-white scale-105 shadow-xl'
                            : 'bg-white/80 backdrop-blur-sm text-gray-600 hover:bg-gray-50 border-2 border-gray-200 hover:border-gray-300'
                            }`}
                    >
                        <MessageSquare className="w-5 h-5" />
                        AI Chat Mode
                        {mode === 'chat' && <Sparkles className="w-4 h-4 animate-pulse" />}
                    </button>
                    <button
                        onClick={() => setMode('manual')}
                        className={`px-6 py-3 md:px-8 md:py-4 rounded-2xl font-semibold text-sm md:text-base transition-all duration-300 flex items-center gap-2 shadow-lg ${mode === 'manual'
                            ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white scale-105 shadow-xl'
                            : 'bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 border-2 border-gray-200 dark:border-gray-600 hover:border-gray-300'
                            }`}
                    >
                        <ClipboardList className="w-5 h-5" />
                        Manual Planning
                        {mode === 'manual' && <span className="text-xs bg-white/20 px-2 py-1 rounded-full">New!</span>}
                    </button>
                </div>
            </section>

            {/* Main Content */}
            <section className="container mx-auto px-4 pb-16">
                <div className={`grid gap-6 ${showItinerary ? 'lg:grid-cols-2' : 'max-w-4xl mx-auto'}`}>
                    {/* Dynamic Interface - Chat or Manual Form */}
                    <div className="card p-6 shadow-xl border-2 border-gray-100 hover:border-primary-200 transition-all duration-300">
                        {mode === 'chat' ? (
                            <ChatInterface onItineraryGenerated={handleItineraryGenerated} selectedModel={selectedModel} />
                        ) : (
                            <ManualPlanningForm onItineraryGenerated={handleItineraryGenerated} />
                        )}
                    </div>

                    {/* Itinerary Display */}
                    {showItinerary && itinerary && (
                        <div className="card p-6 card-hover shadow-xl border-2 border-gray-100 animate-fade-in">
                            <ItineraryDisplay data={itinerary} />
                        </div>
                    )}
                </div>
            </section>

            {/* Footer */}
            <footer className="bg-gradient-to-t from-gray-50 dark:from-gray-900 to-white/50 dark:to-gray-800/50 border-t border-gray-200 dark:border-gray-700 py-8 mt-12">
                <div className="container mx-auto px-4 text-center">
                    <div className="flex items-center justify-center gap-2 mb-3">
                        <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
                        <p className="text-gray-700 dark:text-gray-300 font-medium">Built with ❤️ using cutting-edge AI</p>
                        <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Next.js • FastAPI • Qwen3 + Ollama • TailwindCSS</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">Real-time data from SerpAPI, RapidAPI, and more</p>
                </div>
            </footer>
        </main>
    )
}
