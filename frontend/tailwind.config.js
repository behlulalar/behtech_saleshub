/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#94a3b8',
          500: '#6b7280',
          800: '#1a1a1a',
          900: '#000000',
        },
        brand: {
          50: '#eeeeff',
          100: '#d8d8f5',
          200: '#b1b1eb',
          300: '#8a89e0',
          400: '#5e5dd4',
          500: '#3432c7',
          600: '#2b29a8',
          700: '#222089',
          800: '#14135c',
          900: '#000000',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(0deg, #000000 0%, #3432c7 100%)',
        'brand-gradient-h': 'linear-gradient(90deg, #000000 0%, #3432c7 100%)',
        'brand-subtle': 'linear-gradient(180deg, #f9fafb 0%, #eeeeff 100%)',
      },
    },
  },
  plugins: [],
}
