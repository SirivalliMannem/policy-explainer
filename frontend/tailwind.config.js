/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
          hover: "var(--primary-hover)",
        },
        navy: {
          DEFAULT: "#0F2A43",
          dark: "#0A1E30",
          light: "#16385A",
        },
        orange: {
          DEFAULT: "#F97316",
          btn: "#EA580C",
          gold: "#FDBA74",
        },
        gold: {
          DEFAULT: "#FDBA74",
        },
        espresso: {
          DEFAULT: "var(--dark-espresso)",
          foreground: "var(--dark-espresso-foreground)",
        },
        caramel: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        surface: {
          DEFAULT: "var(--surface)",
          subtle: "var(--surface-subtle)",
        },
        background: "var(--background)",
        foreground: "var(--foreground)",
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        border: "var(--border)",
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        success: {
          DEFAULT: "var(--success)",
          foreground: "var(--success-foreground)",
        },
        ring: "var(--ring)",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "'Segoe UI'", "Roboto", "sans-serif"],
        display: ["Georgia", "serif"],
        serif: ["Georgia", "serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(15, 42, 67, 0.05)",
        card: "0 1px 3px 0 rgba(15, 42, 67, 0.08), 0 1px 2px -1px rgba(15, 42, 67, 0.08)",
        dropdown: "0 4px 6px -1px rgba(15, 42, 67, 0.1), 0 2px 4px -2px rgba(15, 42, 67, 0.08)",
        modal: "0 12px 24px -4px rgba(15, 42, 67, 0.15), 0 4px 6px -2px rgba(15, 42, 67, 0.08)",
      },
    },
  },
  plugins: [],
};
