import type { Config } from 'tailwindcss';
import forms from '@tailwindcss/forms';
import typography from '@tailwindcss/typography';

export default {
  content: ['./src/**/*.{astro,html,ts,tsx,md,mdx}'],
  theme: {
    extend: {
      // `/ <alpha-value>` is REQUIRED on every token: without it Tailwind 3.4
      // cannot inject opacity modifiers, so classes like border-mint/20 or
      // bg-ink/95 are silently dropped from the build (borders then fall back
      // to preflight gray-200).
      colors: {
        navy: 'oklch(0.25 0.06 260 / <alpha-value>)',
        'navy-deep': 'oklch(0.18 0.05 260 / <alpha-value>)',
        mint: 'oklch(0.91 0.12 155 / <alpha-value>)',
        'mint-deep': 'oklch(0.55 0.13 155 / <alpha-value>)',
        coral: 'oklch(0.74 0.16 15 / <alpha-value>)',
        paper: 'oklch(0.985 0.003 90 / <alpha-value>)',
        'paper-card': 'oklch(0.97 0.004 90 / <alpha-value>)',
        ink: 'oklch(0.18 0.04 260 / <alpha-value>)',
        slate: 'oklch(0.50 0.02 260 / <alpha-value>)',
      },
      // PolySans swap point: sans/display intentionally identical until PolySans is licensed.
      fontFamily: {
        sans: ['InterVariable', 'system-ui', 'sans-serif'],
        display: ['InterVariable', 'system-ui', 'sans-serif'],
      },
      maxWidth: { prose: '62ch', 'prose-narrow': '56ch' },
    },
  },
  plugins: [forms, typography],
} satisfies Config;
