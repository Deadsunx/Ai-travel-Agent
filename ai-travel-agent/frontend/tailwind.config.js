/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: 'class',
    content: [
        './pages/**/*.{js,ts,jsx,tsx,mdx}',
        './components/**/*.{js,ts,jsx,tsx,mdx}',
        './app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
        extend: {
            colors: {
                // Ticket-stock palette. Values resolve from CSS vars so the
                // light ("day stock") and dark ("night desk") themes share
                // one set of class names.
                paper: 'rgb(var(--paper) / <alpha-value>)',
                card: 'rgb(var(--card) / <alpha-value>)',
                ink: 'rgb(var(--ink) / <alpha-value>)',
                muted: 'rgb(var(--muted) / <alpha-value>)',
                rule: 'rgb(var(--rule) / <alpha-value>)',
                stamp: 'rgb(var(--stamp) / <alpha-value>)',
                est: 'rgb(var(--est) / <alpha-value>)',
                marigold: 'rgb(var(--marigold) / <alpha-value>)',
            },
            fontFamily: {
                display: ['var(--font-display)', 'system-ui', 'sans-serif'],
                body: ['var(--font-body)', 'system-ui', 'sans-serif'],
                mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
            },
            borderRadius: {
                // Ticket stock is cut, not rounded. Just enough to avoid harshness.
                stub: '3px',
            },
            keyframes: {
                stampIn: {
                    '0%': { opacity: '0', transform: 'scale(1.8) rotate(-14deg)' },
                    '60%': { opacity: '1', transform: 'scale(0.94) rotate(-3deg)' },
                    '100%': { opacity: '1', transform: 'scale(1) rotate(-4.5deg)' },
                },
                riseIn: {
                    '0%': { opacity: '0', transform: 'translateY(6px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                blink: {
                    '0%, 45%': { opacity: '1' },
                    '50%, 95%': { opacity: '0.15' },
                },
            },
            animation: {
                stamp: 'stampIn 340ms cubic-bezier(0.2, 1.4, 0.4, 1) both',
                rise: 'riseIn 260ms ease-out both',
                blink: 'blink 1.4s steps(1, end) infinite',
            },
        },
    },
    plugins: [],
}
