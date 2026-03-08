---
trigger: always_on
---
# Web UI Responsive Design Standards

To ensure the DriveWire management interface remains usable across both desktop and mobile devices while preserving the retro "Radio Shack" CRT aesthetic, follow these standards.

## 📱 Mobile-First Principles

1. **Viewport Setup**: Every page MUST include the standard viewport meta tag:
   ```html
   <meta name="viewport" content="width=device-width, initial-scale=1.0">
   ```
2. **Touch Targets**: All interactive elements (buttons, links, form inputs) should have a minimum touch target size of **44x44px** on mobile.
3. **No Hover Reliance**: Do not hide critical information or actions behind hover states, as these are inaccessible on mobile devices.

## 📐 Layout & CSS

1. **Fluid Grids**: Use `display: grid` with `grid-template-columns: 1fr 1fr` for desktop, and override to `1fr` for mobile.
2. **Media Queries**: Use the project-standard **600px** breakpoint for mobile overrides:
   ```css
   @media (max-width: 600px) {
       /* mobile-specific styles here */
   }
   ```
3. **Typography**: Use relative units (`em`, `rem`) for font sizes where possible, though the pixel-art `VT323` font may require fixed pixel sizes at small scales for readability.
4. **Scrolling**: Ensure that large tables or log boxes have `overflow-x: auto` or `overflow-y: auto` to prevent breaking the layout on narrow screens.

## 🎨 Aesthetic Consistency

1. **Retro Constraints**: Even on mobile, maintain the green-on-black CRT terminal aesthetic.
2. **Contrast**: Ensure that the low-contrast "phosphor" colors remain readable under direct sunlight (common for mobile usage).
