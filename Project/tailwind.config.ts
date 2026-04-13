import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      screens: {
        xs: "375px",
      },
      colors: {
        background: "#f8f6f1",
        foreground: "#2e2f2c",
        primary: "#a03929",
        "primary-dim": "#902d1f",
        "primary-container": "#fd7d68",
        "primary-fixed": "#fd7d68",
        "primary-fixed-dim": "#ec715d",
        "on-primary": "#ffefed",
        "on-primary-container": "#520300",
        "on-primary-fixed": "#020000",
        "on-primary-fixed-variant": "#610903",
        
        secondary: "#705900",
        "secondary-dim": "#624d00",
        "secondary-container": "#fdd34d",
        "secondary-fixed": "#fdd34d",
        "secondary-fixed-dim": "#eec540",
        "on-secondary": "#fff2d4",
        "on-secondary-container": "#5c4900",
        "on-secondary-fixed": "#463600",
        "on-secondary-fixed-variant": "#675200",
        
        tertiary: "#00684f",
        "tertiary-dim": "#005b45",
        "tertiary-container": "#98ffd9",
        "tertiary-fixed": "#98ffd9",
        "tertiary-fixed-dim": "#89f0cb",
        "on-tertiary": "#c6ffe7",
        "on-tertiary-container": "#00634b",
        "on-tertiary-fixed": "#004f3b",
        "on-tertiary-fixed-variant": "#006e54",
        
        surface: "#f8f6f1",
        "surface-dim": "#d5d5ce",
        "surface-bright": "#f8f6f1",
        "surface-variant": "#deddd7",
        "surface-tint": "#a03929",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f2f1eb",
        "surface-container": "#eae8e3",
        "surface-container-high": "#e4e2dd",
        "surface-container-highest": "#deddd7",
        "on-surface": "#2e2f2c",
        "on-surface-variant": "#5c5c58",
        "on-background": "#2e2f2c",
        "inverse-surface": "#0e0e0c",
        "inverse-primary": "#fd7d68",
        "inverse-on-surface": "#9e9d99",
        
        outline: "#777773",
        "outline-variant": "#aeada9",
        
        error: "#b41340",
        "error-dim": "#a70138",
        "error-container": "#f74b6d",
        "on-error": "#ffefef",
        "on-error-container": "#510017",

        // Keep aura/brand groups for backward compatibility if needed
        aura: {
          primary: "#a03929",
          "on-primary": "#ffefed",
        }
      },
      fontFamily: {
        sans: ['Lexend', 'system-ui', 'sans-serif'],
        headline: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
        body: ['Lexend', 'system-ui', 'sans-serif'],
        label: ['Lexend', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: "1rem",
        lg: "2rem",
        xl: "3rem",
        card: "var(--radius-card)",
        panel: "var(--radius-panel)",
        full: "9999px"
      },
      animation: {
        "fade-in": "fadeIn 300ms ease-out",
        "slide-up": "slideUp 300ms cubic-bezier(0.4, 0.0, 0.2, 1)",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
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
        apple: "cubic-bezier(0.4, 0.0, 0.2, 1)",
      },
      backdropBlur: {
        xs: "2px",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
        brand: "0 20px 40px rgba(0,0,0,0.1)",
        "brand-md": "0 8px 24px rgba(0,0,0,0.12)",
        "brand-sm": "0 2px 8px rgba(0,0,0,0.08)",
        aura: "0 4px 12px rgba(0,0,0,0.08)",
        "aura-md": "0 8px 24px rgba(0,0,0,0.12)",
        "aura-sm": "0 2px 8px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
