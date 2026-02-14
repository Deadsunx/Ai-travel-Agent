import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/ui/ThemeProvider'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
    title: 'AI Travel Agent - Smart Trip Planning',
    description: 'Plan your perfect trip with AI-powered recommendations. Get real-time prices for flights, hotels, and restaurants.',
    keywords: ['travel', 'AI', 'trip planning', 'flights', 'hotels', 'itinerary'],
    authors: [{ name: 'AI Travel Agent' }],
    openGraph: {
        title: 'AI Travel Agent',
        description: 'Plan your perfect trip with AI-powered recommendations',
        type: 'website',
    },
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body className={`${inter.className} antialiased`}>
                <ThemeProvider>
                    <div className="min-h-screen">
                        {children}
                    </div>
                </ThemeProvider>
            </body>
        </html>
    )
}

