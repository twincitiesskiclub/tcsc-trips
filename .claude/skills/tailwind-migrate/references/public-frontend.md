# Public Frontend Design Guide

TCSC is a 501(c)(3) nonprofit for young adults (21-35) in Minneapolis-St. Paul promoting healthy lifestyle through cross-country ski training.

## Design Principles

1. **Timeless & Elegant** - Clean design that won't feel dated
2. **Inclusive & Welcoming** - Subtle warmth for diverse members
3. **Mobile-First** - Most members register on phones
4. **Professional but Personal** - Nonprofit credibility with community warmth

## Visual Direction

| Aspect | Approach |
|--------|----------|
| Color | Navy/mint with ample white space. Mint as subtle accent. |
| Typography | Clean sans-serif, generous line-height |
| Spacing | Ample breathing room, don't crowd |
| Cards | Soft shadows, 16px radius, inviting |
| Interactions | Smooth, subtle transitions |

## Pages to Migrate

| Priority | Page | Purpose |
|----------|------|---------|
| 1 | `season_register.html` | Primary conversion - member signup |
| 2 | `index.html` | Homepage - trip/event discovery |
| 3 | `trips/*.html` | Trip registration |
| 4 | `socials/registration.html` | Social event signup |
| 5 | Supporting pages | Detail/success pages |

## Component Patterns

### Cards (Public)

```html
<div class="bg-white rounded-2xl shadow-sm hover:shadow-md transition-shadow p-6 md:p-8 flex flex-col gap-4">
  <h2 class="text-xl md:text-2xl font-semibold text-tcsc-navy">Title</h2>
  <div class="flex flex-wrap gap-3 text-sm text-zinc-500">
    <span>Meta info</span>
  </div>
  <p class="text-zinc-600 leading-relaxed">Description</p>
  <div class="mt-auto pt-4 flex items-center justify-between">
    <span class="text-lg font-medium text-tcsc-navy">$185</span>
    <a href="#" class="btn-primary">Register</a>
  </div>
</div>
```

### Form Sections (Registration)

```html
<section class="bg-white rounded-2xl shadow-sm p-6 md:p-8">
  <div class="flex items-center gap-3 mb-6">
    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-tcsc-navy text-white text-sm font-medium">1</span>
    <h2 class="text-lg font-semibold text-tcsc-navy">Your Information</h2>
  </div>
  <div class="space-y-4">
    <!-- Form fields -->
  </div>
</section>
```

### Form Inputs (Mobile-Optimized)

```html
<!-- 48px height for touch-friendly targets -->
<div>
  <label class="block text-sm font-medium text-zinc-600 mb-1.5">First Name</label>
  <input type="text" class="w-full h-12 px-4 rounded-xl border border-zinc-200 focus:outline-none focus:ring-2 focus:ring-tcsc-mint/50 focus:border-tcsc-navy transition-colors">
</div>
```

### Radio/Checkbox Cards

```html
<label class="flex items-center gap-3 p-4 rounded-xl border border-zinc-200 hover:border-zinc-400 cursor-pointer transition-colors has-[:checked]:border-tcsc-navy has-[:checked]:bg-tcsc-mint/10">
  <input type="radio" name="option" class="w-5 h-5 text-tcsc-navy">
  <span class="font-medium">Option Label</span>
</label>
```

### Price Selection (Trips)

```html
<label class="block p-4 rounded-xl border-2 border-zinc-200 cursor-pointer hover:border-zinc-400 transition-colors has-[:checked]:border-tcsc-navy has-[:checked]:bg-tcsc-mint/5">
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
      <input type="radio" name="price" class="w-5 h-5 text-tcsc-navy">
      <div>
        <div class="font-semibold text-tcsc-navy">Standard</div>
        <div class="text-sm text-zinc-500">Shared room</div>
      </div>
    </div>
    <div class="text-xl font-bold text-tcsc-navy">$185</div>
  </div>
</label>
```

### Submit Button

```html
<button type="submit" class="w-full h-14 bg-tcsc-navy text-white text-lg font-semibold rounded-xl hover:bg-tcsc-navy/90 active:scale-[0.98] transition-all disabled:opacity-50">
  Complete Registration — $205
</button>
```

### Success State

```html
<div class="text-center py-12">
  <div class="w-16 h-16 mx-auto mb-6 rounded-full bg-tcsc-mint/20 flex items-center justify-center">
    <svg class="w-8 h-8 text-green-600"><!-- checkmark --></svg>
  </div>
  <h1 class="text-2xl font-bold text-tcsc-navy mb-2">You're registered!</h1>
  <p class="text-zinc-600 mb-8">Check your email for confirmation.</p>
  <a href="/" class="btn-primary">Back to Home</a>
</div>
```

### Error States

```html
<!-- Input error -->
<input class="... border-2 border-red-500 focus:ring-red-200">
<p class="mt-1.5 text-sm text-red-600">Please enter a valid email</p>

<!-- Error alert -->
<div class="p-4 rounded-xl bg-red-50 border border-red-200">
  <div class="flex gap-3">
    <svg class="w-5 h-5 text-red-600 shrink-0">...</svg>
    <div>
      <p class="font-medium text-red-800">Payment failed</p>
      <p class="text-sm text-red-600">Your card was declined.</p>
    </div>
  </div>
</div>
```

## Stripe Integration

Style Card Element container to match:

```html
<div class="h-12 px-4 rounded-xl border border-zinc-200 focus-within:ring-2 focus-within:ring-tcsc-mint/50 focus-within:border-tcsc-navy transition-colors flex items-center">
  <div id="card-element" class="w-full"></div>
</div>
```

## Mobile Testing

Test each page on:
- iPhone SE (small)
- iPhone 14/15 (standard)
- Android Chrome
- iPad (tablet)

## Accessibility

- All inputs have labels
- Focus states visible (mint ring)
- Color contrast WCAG AA
- Touch targets min 44x44px
- Error messages linked with `aria-describedby`
