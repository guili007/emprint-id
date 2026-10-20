/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // EmPrint-iD brand (#00dfc8 teal)
        teal: {
          400: '#00dfc8',
          500: '#00c4b0',
          600: '#00a896',
        },
        // Nuit opérationnelle
        navy: {
          900: '#0a0f1e',
          800: '#111827',
          700: '#1a2236',
          600: '#243047',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
