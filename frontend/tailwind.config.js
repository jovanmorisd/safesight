/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#f0fdfa", 100: "#ccfbf1", 200: "#99f6e4", 300: "#5eead4", 400: "#2dd4bf",
          500: "#14b8a6", 600: "#0d9488", 700: "#0f766e", 800: "#115e59", 900: "#134e4a",
        },
        canvas: { DEFAULT: "#f3f5f7", dark: "#0a111c" },
        panel: { DEFAULT: "#ffffff", dark: "#111a29" },
        sunken: { DEFAULT: "#f6f7f9", dark: "#0d1522" },
        line: { DEFAULT: "#e7eaee", dark: "#1e293b" },
        ok: "#10b981",
        bad: "#ef4444",
        warn: "#f59e0b",
      },
      borderRadius: { "4xl": "2rem" },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.04), 0 8px 24px -12px rgba(16,24,40,.10)",
        float: "0 12px 32px -12px rgba(15,23,42,.25)",
        glow: "0 8px 24px -8px rgba(13,148,136,.55)",
      },
    },
  },
  plugins: [],
};
