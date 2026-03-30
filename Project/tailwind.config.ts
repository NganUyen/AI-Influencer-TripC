import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          50: "#f0f9ff",
          100: "#e0f2fe",
          200: "#bae6fd",
          300: "#7dd3fc",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          800: "#075985",
          900: "#0c4a6e",
        },
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Inter', 'Segoe UI', 'sans-serif'],
      },
      animation: {
        "fade-in": "fadeIn 300ms ease-out",
        "slide-up": "slideUp 300ms cubic-bezier(0.4, 0.0, 0.2, 1)",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      transitionTimingFunction: {
        'apple': 'cubic-bezier(0.4, 0.0, 0.2, 1)',
      },
      backdropBlur: {
        'xs': '2px',
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
