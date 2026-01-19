# Component Mapping Reference

CSS class to Tailwind equivalents for TCSC.

## Layout

| Current | Tailwind |
|---------|----------|
| `.admin-container` | `max-w-6xl mx-auto p-5` |
| `.admin-content` | `bg-gray-50 p-5 rounded-md` |
| `.admin-menu` | `grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-6` |

## Cards

```html
<!-- Admin menu item -->
<div class="bg-white p-6 rounded-md border border-zinc-200 hover:shadow-lg hover:-translate-y-0.5 transition-all">

<!-- Trip/event card -->
<div class="bg-white rounded-2xl shadow-sm p-6 md:p-8 flex flex-col gap-4 hover:shadow-md transition-shadow">
```

## Buttons

```html
<!-- Primary -->
<button class="bg-tcsc-navy text-white px-4 py-3 rounded-xl font-medium hover:bg-tcsc-navy/90 active:scale-[0.98] transition-all">

<!-- Secondary -->
<button class="bg-white text-tcsc-navy px-4 py-3 rounded-xl font-medium border-2 border-tcsc-navy hover:bg-tcsc-navy/5 transition-all">

<!-- Danger -->
<button class="bg-red-500/15 text-red-700 px-4 py-3 rounded-xl font-medium hover:bg-red-500/25 transition-all">
```

## Badges (from Catalyst)

```html
<!-- Base: inline-flex items-center gap-x-1.5 rounded-md px-1.5 py-0.5 text-sm font-medium -->

<!-- Colors -->
<span class="... bg-green-500/15 text-green-700">Active</span>
<span class="... bg-amber-400/20 text-amber-700">Pending</span>
<span class="... bg-red-500/15 text-red-700">Error</span>
<span class="... bg-blue-500/15 text-blue-700">Info</span>
<span class="... bg-zinc-600/10 text-zinc-700">Neutral</span>
```

## Form Inputs

```html
<!-- Text input (mobile-friendly 48px height) -->
<input class="w-full h-12 px-4 rounded-xl border border-zinc-200 focus:outline-none focus:ring-2 focus:ring-tcsc-mint/50 focus:border-tcsc-navy transition-colors">

<!-- Select -->
<select class="w-full h-12 px-4 rounded-xl border border-zinc-200 focus:outline-none focus:ring-2 focus:ring-tcsc-mint/50 appearance-none">
```

## Modals

```html
<!-- Overlay -->
<div class="fixed inset-0 bg-black/50 z-50">
  <!-- Modal -->
  <div class="fixed inset-0 flex items-center justify-center p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
      <!-- Content -->
    </div>
  </div>
</div>
```

## Sidebar Layout (Admin)

From Catalyst `sidebar-layout.jsx`:

```html
<!-- Main container -->
<div class="relative isolate flex min-h-svh w-full bg-white max-lg:flex-col lg:bg-zinc-100">

  <!-- Desktop sidebar (fixed) -->
  <div class="fixed inset-y-0 left-0 w-64 max-lg:hidden">
    <!-- Sidebar content -->
  </div>

  <!-- Content area -->
  <div class="flex flex-1 flex-col pb-2 lg:min-w-0 lg:pt-2 lg:pr-2 lg:pl-64">
    <div class="grow p-6 lg:rounded-lg lg:bg-white lg:p-10 lg:shadow-sm lg:ring-1 lg:ring-zinc-950/5">
      <div class="mx-auto max-w-6xl">
        <!-- Page content -->
      </div>
    </div>
  </div>
</div>
```

## Sidebar Navigation

```html
<!-- Nav item -->
<a href="#" class="flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-base font-medium text-zinc-950 hover:bg-zinc-950/5 {% if current %}bg-zinc-950/5{% endif %}">
  <svg class="size-5">...</svg>
  <span>Label</span>
</a>

<!-- Section heading -->
<h3 class="mb-1 px-2 text-xs font-medium text-zinc-500">Section</h3>
```

## Tables (non-Tabulator)

```html
<table class="min-w-full text-left text-sm">
  <thead>
    <tr class="border-b border-zinc-200">
      <th class="px-4 py-2 font-medium text-zinc-500">Header</th>
    </tr>
  </thead>
  <tbody>
    <tr class="border-b border-zinc-100 hover:bg-zinc-50">
      <td class="px-4 py-4">Content</td>
    </tr>
  </tbody>
</table>
```

## Tabulator Theme

Keep custom Tabulator styling - just ensure header matches navy:

```css
.tabulator .tabulator-header { background: #1c2c44; color: white; }
```
