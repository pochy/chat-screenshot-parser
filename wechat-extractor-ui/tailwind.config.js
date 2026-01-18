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
                    bg: '#1e1e1e',
                    node: '#2d2d2d',
                    border: '#404040',
                    accent: '#00ffaa',
                    hover: '#3a3a3a',
                }
            },
        },
    },
    plugins: [],
}
