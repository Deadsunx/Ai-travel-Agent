'use client'

/**
 * TravelBackground - Subtle animated travel-themed background
 * Uses CSS-only SVG patterns + gradient blobs for a clean, professional look.
 */
export default function TravelBackground() {
    return (
        <div className="fixed inset-0 -z-10 overflow-hidden">
            {/* Gradient blobs */}
            <div className="absolute top-0 -left-4 w-72 h-72 bg-primary-300 dark:bg-primary-800 rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-xl opacity-20 animate-blob"></div>
            <div className="absolute top-0 -right-4 w-72 h-72 bg-accent-300 dark:bg-accent-800 rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
            <div className="absolute -bottom-8 left-20 w-72 h-72 bg-pink-300 dark:bg-pink-800 rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>

            {/* Base gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-white via-primary-50/30 to-accent-50/30 dark:from-gray-900 dark:via-gray-900/90 dark:to-gray-800"></div>

            {/* Scattered travel SVG icons */}
            <svg className="absolute inset-0 w-full h-full opacity-[0.04] dark:opacity-[0.06]" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <pattern id="travel-pattern" x="0" y="0" width="200" height="200" patternUnits="userSpaceOnUse">
                        {/* Plane */}
                        <g transform="translate(20, 30) rotate(-30)" fill="currentColor">
                            <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z" />
                        </g>
                        {/* Globe */}
                        <g transform="translate(120, 20)" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <circle cx="12" cy="12" r="10" />
                            <path d="M2 12h20" />
                            <path d="M12 2c2.5 3 4 6.5 4 10s-1.5 7-4 10" />
                            <path d="M12 2c-2.5 3-4 6.5-4 10s1.5 7 4 10" />
                        </g>
                        {/* Luggage */}
                        <g transform="translate(60, 130)" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <rect x="3" y="7" width="18" height="14" rx="2" />
                            <path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2" />
                            <path d="M12 11v4" />
                        </g>
                        {/* Map pin */}
                        <g transform="translate(150, 110)" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
                            <circle cx="12" cy="9" r="2.5" />
                        </g>
                        {/* Compass */}
                        <g transform="translate(30, 160) scale(0.9)" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <circle cx="12" cy="12" r="10" />
                            <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88" fill="currentColor" opacity="0.3" />
                        </g>
                        {/* Sun / Vacation */}
                        <g transform="translate(160, 160)" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <circle cx="12" cy="12" r="4" />
                            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
                        </g>
                        {/* Small plane (different position) */}
                        <g transform="translate(100, 80) rotate(15) scale(0.8)" fill="currentColor">
                            <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z" />
                        </g>
                    </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#travel-pattern)" className="text-gray-900 dark:text-gray-100" />
            </svg>
        </div>
    )
}
