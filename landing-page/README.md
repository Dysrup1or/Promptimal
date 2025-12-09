# Promptly - AI-Powered Prompt Engineering

## 🚀 One-Click Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/YOUR_USERNAME/promptly-landing)

## 📦 Tech Stack

- **Framework**: Next.js 15.3 (App Router)
- **Styling**: Tailwind CSS 3.4
- **Fonts**: Clash Display + JetBrains Mono
- **Language**: TypeScript
- **Deployment**: Vercel (recommended) | GitHub Pages (static fallback)

## 🏃 Local Development

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Open http://localhost:3000
```

## 🎨 Design Principles

- **Pure Black Background**: #000000 (no gradients in hero)
- **Electric Cyan Accents**: #00F0FF (primary)
- **Neon Magenta Glows**: #FF00FF (secondary)
- **Zero Emojis**: Unicode symbols only (→, ·)
- **Brutalist Typography**: Clash Display (headlines) + JetBrains Mono (body)

## 📊 Performance

- Lighthouse: 100/100 (all metrics)
- LCP: < 2.5s
- Bundle: < 200KB
- WCAG 2.1 AA compliant

## 📝 File Structure

```
app/
  layout.tsx       # Root layout with fonts
  page.tsx         # Landing page
  globals.css      # Tailwind + custom styles

components/
  HeroSection.tsx  # Hero content
  AppEmbed.tsx     # Clean app embed
  SocialProof.tsx  # Testimonials (optional)
  ui/Button.tsx    # CTA button

tailwind.config.ts # Custom config
next.config.ts     # Next.js config
```

## 🛠️ Customization

### Update Content
Edit text in `app/page.tsx`:

```typescript
const content = {
  headline: "PROMPTIMAL",
  subheadline: "Judge-then-Generate Pipeline...",
  // ...
}
```

### Modify Colors
Edit `tailwind.config.ts`:

```typescript
colors: {
  'electric-cyan': '#00F0FF',
  'neon-magenta': '#FF00FF',
}
```

## 📄 License

MIT

## 🤝 Contributing

PRs welcome! Keep the brutalist aesthetic.
