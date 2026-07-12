/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eef7f7',
          100: '#d5ecec',
          200: '#aed9d9',
          300: '#7dc0c0',
          400: '#4fa3a3',
          500: '#2e8585',
          600: '#1f5c5c',   // primary — matches the payslip table header
          700: '#174545',
          800: '#102e2e',
          900: '#081818',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
