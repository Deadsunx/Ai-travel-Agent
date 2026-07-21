import type { Metadata } from 'next'
import { Archivo, Instrument_Sans, Azeret_Mono } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/ui/ThemeProvider'

// Display: wide grotesque, set like destination-board signage.
const archivo = Archivo({
    subsets: ['latin'],
    axes: ['wdth'],
    variable: '--font-display',
    display: 'swap',
})

// Body: humanist sans, warmer and less ubiquitous than Inter.
const instrument = Instrument_Sans({
    subsets: ['latin'],
    variable: '--font-body',
    display: 'swap',
})

// Data: every fare, time, count and code is set in this.
const azeret = Azeret_Mono({
    subsets: ['latin'],
    variable: '--font-mono',
    display: 'swap',
})

export const metadata: Metadata = {
    title: 'Travel Desk — trips planned from one sentence',
    description:
        'Describe a trip in a sentence. The desk searches flights, stays and places to eat, prices the whole thing, and marks every number live or estimated.',
    keywords: ['travel', 'trip planning', 'flights', 'hotels', 'itinerary', 'India'],
    openGraph: {
        title: 'Travel Desk',
        description: 'Trips planned from one sentence, with every number marked live or estimated.',
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
            <body className={`${archivo.variable} ${instrument.variable} ${azeret.variable} antialiased`}>
                <ThemeProvider>{children}</ThemeProvider>
            </body>
        </html>
    )
}
