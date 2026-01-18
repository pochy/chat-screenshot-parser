/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                dark: {
                    bg: '#0b0f14',
                    node: '#111827',
                    border: '#1f2a3a',
                    accent: '#23f5a4',
                    hover: '#1b2432',
                    panel: '#0f172a',
                    canvas: '#0b111a',
                    glow: '#0ea5e9',
                }
            },
        },
    },
    plugins: [],
}
