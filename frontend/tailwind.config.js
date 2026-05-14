/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#FDF0F3",
          100: "#FAD5DF",
          200: "#F5C8D4",
          300: "#EDA8BC",
          400: "#E8849B",
          500: "#D95E7C",
          600: "#C9446A",
          700: "#A8324F",
          800: "#7D1A38",
          900: "#4F0C20",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
