/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        panel: "#ffffff",
        line: "#d8e0e8",
      },
    },
  },
  plugins: [],
};
