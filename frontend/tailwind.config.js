/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* Backgrounds */
        'bg-void': 'var(--color-bg-void)',
        'bg-base': 'var(--color-bg-base)',
        'bg-surface': 'var(--color-bg-surface)',
        'bg-elevated': 'var(--color-bg-elevated)',
        'bg-hover': 'var(--color-bg-hover)',
        /* Borders */
        'border-subtle': 'var(--color-border-subtle)',
        'border-default': 'var(--color-border-default)',
        'border-bright': 'var(--color-border-bright)',
        /* Text */
        'text-primary': 'var(--color-text-primary)',
        'text-body': 'var(--color-text-body)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',
        /* Accents */
        'accent-cyan': 'var(--color-accent-cyan)',
        'accent-magenta': 'var(--color-accent-magenta)',
        'accent-amber': 'var(--color-accent-amber)',
        /* Status — all use CSS vars */
        'status-success': 'var(--color-success)',
        'status-error': 'var(--color-error)',
        'status-warning': 'var(--color-warning)',
        'status-info': 'var(--color-info)',
        'status-secondary': 'var(--color-secondary)',
      },
      fontFamily: {
        body: ['var(--font-body)'],
        mono: ['var(--font-mono)'],
        display: ['var(--font-display)'],
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        pill: 'var(--radius-pill)',
      },
      boxShadow: {
        glow: 'var(--shadow-glow)',
        'glow-blue': 'var(--shadow-glow-blue)',
        'sm': 'var(--shadow-sm)',
        'md': 'var(--shadow-md)',
        'lg': 'var(--shadow-lg)',
        'xl': 'var(--shadow-xl)',
      },
      animation: {
        'fade-in': 'fade-in 200ms ease-out',
        'slide-up': 'slide-up 250ms ease-out',
        'slide-in-right': 'slide-in-right 250ms ease-out',
        'scale-in': 'scale-in 200ms ease-out',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
      },
      transitionDuration: {
        fast: '150ms',
        normal: '200ms',
        slow: '300ms',
      },
    },
  },
  plugins: [],
}
