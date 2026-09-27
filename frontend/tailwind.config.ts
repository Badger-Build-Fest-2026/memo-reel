import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        midnight: "#0E1224",
        panel: "#161B34",
        starlight: "#E8B85C",
        nebula: "#7C6FF0",
        paper: "#F2EFE6",
        dust: "#8A90B3",
        // category accent colors, used for graph node coloring + chips
        cat: {
          food: "#E8845C",
          tech: "#E8B85C",
          shop: "#7C6FF0",
          fitness: "#5CC9A7",
          lifestyle: "#D97BA8",
          entertainment: "#5CA8E8",
          other: "#8A90B3",
        },
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "serif"],
        sans: ["var(--font-plex)", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
