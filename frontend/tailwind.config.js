/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17201f",
        paper: "#f4f1e9",
        accent: "#df5b37",
        moss: "#2f6657",
      },
      boxShadow: {
        panel: "0 16px 45px rgba(23, 32, 31, 0.09)",
      },
    },
  },
  plugins: [],
};
