/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brutal: {
          yellow: "#FFDB2C",
          blue: "#4D8DFF",
          pink: "#FF6FB5",
          green: "#5CE1A6",
          purple: "#B084FF",
          red: "#FF5C5C",
          ink: "#0A0A0A",
          paper: "#FFFDF5",
          dark: "#121212",
          darker: "#0A0A0A",
          darkcard: "#1C1C1C",
        },
      },
      fontFamily: {
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        brutal: "4px 4px 0 0 #0A0A0A",
        "brutal-sm": "2px 2px 0 0 #0A0A0A",
        "brutal-lg": "8px 8px 0 0 #0A0A0A",
        "brutal-xl": "12px 12px 0 0 #0A0A0A",
        "brutal-white": "4px 4px 0 0 #FFFDF5",
        "brutal-white-lg": "8px 8px 0 0 #FFFDF5",
      },
      borderRadius: {
        brutal: "14px",
      },
      keyframes: {
        "pop-in": {
          "0%": { transform: "scale(0.96)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        "slide-up": {
          "0%": { transform: "translateY(12px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      animation: {
        "pop-in": "pop-in 0.18s ease-out",
        "slide-up": "slide-up 0.25s ease-out",
      },
    },
  },
  plugins: [],
};
