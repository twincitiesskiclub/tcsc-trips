/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/**/*.js'
  ],
  theme: {
    extend: {
      colors: {
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
