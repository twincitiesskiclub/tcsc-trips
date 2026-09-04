/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/**/*.js'
  ],
  theme: {
    extend: {
      colors: {
        // Marketing site palette. Keep the existing admin tokens independent.
        'brand-navy': 'oklch(0.25 0.06 260 / <alpha-value>)',
        'brand-navy-deep': 'oklch(0.18 0.05 260 / <alpha-value>)',
        'brand-mint': 'oklch(0.91 0.12 155 / <alpha-value>)',
        'brand-mint-deep': 'oklch(0.52 0.13 155 / <alpha-value>)',
        'brand-coral': 'oklch(0.74 0.16 15 / <alpha-value>)',
        'brand-paper': 'oklch(0.985 0.003 90 / <alpha-value>)',
        'brand-paper-card': 'oklch(0.97 0.004 90 / <alpha-value>)',
        'brand-ink': 'oklch(0.18 0.04 260 / <alpha-value>)',
        'brand-slate': 'oklch(0.50 0.02 260 / <alpha-value>)',
        // Brand colors (from _tokens.css)
        'tcsc-navy': '#1c2c44',      // --p (primary)
        'tcsc-mint': '#acf3c4',      // --s (secondary)
        'tcsc-white': '#fcfefd',     // --w (white)

        // Gray scale based on navy with opacity
        'tcsc-gray': {
          50: 'rgba(28,44,68,0.03)',   // --g-o (overlay)
          100: 'rgba(28,44,68,0.15)',  // --g-b (border)
          400: 'rgba(28,44,68,0.4)',   // --g-l (light text)
          600: 'rgba(28,44,68,0.7)',   // --g-m (medium text)
          800: 'rgba(28,44,68,0.9)',   // --g-d (dark text)
        },

        // Status colors (background + text pairs)
        'status': {
          'success-bg': '#c6f6d5',
          'success-text': '#166534',
          'warning-bg': '#fff3dc',
          'warning-text': '#b07b2c',
          'error-bg': '#fee2e2',
          'error-text': '#991b1b',
          'info-bg': '#e8f0fe',
          'info-text': '#174ea6',
          'neutral-bg': '#e2e8f0',
          'neutral-text': '#4a5568',
          'purple-bg': '#faf5ff',
          'purple-text': '#5521b5',
        }
      },

      fontFamily: {
        'sans': ['-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        'brand': ['ArchivoVariable', 'system-ui', 'sans-serif'],
        'display': ['PolySansBulkyWide', 'ArchivoVariable', 'system-ui', 'sans-serif'],
      },

      borderRadius: {
        'tcsc': '6px',  // --r (standard radius)
      },

      maxWidth: {
        'form': '343px',  // --fw (form width)
        'form-lg': '700px', // Registration form width
      },

      animation: {
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
      },

      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },

  // Disable Tailwind reset during migration to avoid conflicts
  corePlugins: {
    preflight: false,
  },

  plugins: [
    require('@tailwindcss/forms'),
  ],
}
