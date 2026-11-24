/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: { brand: { 50: '#effaf3', 100: '#d7f2e0', 500: '#2f9e5e', 600: '#238a4f', 700: '#1c6e40' } },
      fontFamily: { sans: ['"Noto Sans Bengali"', 'Inter', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
};
