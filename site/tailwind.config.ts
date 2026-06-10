import type { Config } from 'tailwindcss';
import forms from '@tailwindcss/forms';
import typography from '@tailwindcss/typography';

export default {
  content: ['./src/**/*.{astro,html,ts,tsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        navy: 'oklch(0.25 0.06 260)',
        'navy-deep': 'oklch(0.18 0.05 260)',
        mint: 'oklch(0.91 0.12 155)',
        'mint-deep': 'oklch(0.55 0.13 155)',
        coral: 'oklch(0.74 0.16 15)',
        paper: 'oklch(0.985 0.003 90)',
        'paper-card': 'oklch(0.97 0.004 90)',
        ink: 'oklch(0.18 0.04 260)',
        slate: 'oklch(0.50 0.02 260)',
      },
      fontFamily: {
        sans: ['PolySans', 'system-ui', 'sans-serif'],
        display: ['PolySans Wide', 'PolySans', 'system-ui', 'sans-serif'],
      },
      maxWidth: { prose: '62ch', 'prose-narrow': '56ch' },
    },
  },
  plugins: [forms, typography],
} satisfies Config;
