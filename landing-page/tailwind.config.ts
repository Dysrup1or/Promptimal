import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'electric-cyan': '#00F0FF',
        'neon-magenta': '#FF00FF',
        'dark-cyan': '#00B8CC',
        'dark-magenta': '#CC00CC',
        'charcoal': '#1A1A1A',
        'ghost-white': '#F8F8F8',
        'slate-gray': '#718096',
      },
      fontFamily: {
        clash: ['var(--font-clash)', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains)', 'Courier New', 'monospace'],
      },
      boxShadow: {
        'cyan-glow': '0 0 40px rgba(0, 240, 255, 0.6), 0 0 80px rgba(0, 240, 255, 0.3)',
        'magenta-glow': '0 0 40px rgba(255, 0, 255, 0.6), 0 0 80px rgba(255, 0, 255, 0.3)',
        'dual-glow': '0 0 40px rgba(0, 240, 255, 0.4), 0 0 80px rgba(255, 0, 255, 0.4)',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(0, 240, 255, 0.6)' },
          '50%': { boxShadow: '0 0 40px rgba(0, 240, 255, 0.9)' },
        },
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
export default config
