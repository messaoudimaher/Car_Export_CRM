/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        crm: {
          bg: "#0f172a",
          card: "#1e293b",
          border: "#334155",
          hover: "#334155",
          text: "#f8fafc",
          muted: "#94a3b8",
          primary: "#3b82f6",
          primaryHover: "#2563eb",
          success: "#10b981",
          warning: "#f59e0b",
          danger: "#ef4444",
          ai: "#8b5cf6",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
