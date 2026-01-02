# Reveal.js Best Practices

Reference guide for creating gorgeous, corporate-ready presentations with Reveal.js.

---

## Quick Start

### CDN Links (v5.1.0)
```html
<!-- CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/theme/black.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/plugin/highlight/monokai.css">

<!-- JS -->
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/plugin/highlight/highlight.js"></script>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/plugin/notes/notes.js"></script>
```

### Basic Config
```javascript
Reveal.initialize({
    hash: true,
    slideNumber: 'c/t',
    transition: 'slide',
    backgroundTransition: 'fade',
    center: true,
    controls: true,
    progress: true,
    plugins: [RevealHighlight, RevealNotes]
});
```

---

## Themes & Styling

### Built-in Themes
- **Dark**: `black` (default), `night`, `league`
- **Light**: `white`, `beige`, `sky`, `serif`
- **Colorful**: `blood`, `moon`, `solarized`

Use via: `theme: 'league'` in config or swap CSS file.

### Custom Brand Colors
```css
:root {
    --r-main-color: #f0f0f0;           /* Primary text */
    --r-heading-color: #4da6ff;         /* Headings */
    --r-link-color: #0066cc;            /* Links */
    --r-background-color: #0a0a0a;      /* Slide background */
    --r-selection-background-color: #0066cc;
}
```

### Gradient Backgrounds
```html
<!-- Title slide gradient -->
<section data-background-gradient="linear-gradient(135deg, #0a0a0a 0%, #0d1a2d 50%, #0a0a0a 100%)">

<!-- Radial spotlight -->
<section data-background-gradient="radial-gradient(circle, #1a3a5c 0%, #0a0a0a 70%)">
```

### Background Images
```html
<!-- Full bleed image -->
<section data-background-image="hero.jpg" data-background-size="cover">

<!-- Logo (contained) -->
<section data-background-image="logo.png" data-background-size="contain" data-background-opacity="0.2">
```

---

## Layout Patterns

### Helper Classes
| Class | Effect |
|-------|--------|
| `r-stretch` | Stretch element to fill slide |
| `r-fit-text` | Auto-scale text to fit |
| `r-stack` | Stack elements (for layered reveals) |
| `r-frame` | Add border frame |

### Two-Column Layout
```html
<div style="display: flex; gap: 2rem;">
    <div style="flex: 1;">Left column</div>
    <div style="flex: 1;">Right column</div>
</div>
```

### Centered Content
```html
<section class="center">
    <h2>Centered Title</h2>
</section>
```

### Title Slide Structure
```html
<section class="title-slide" data-background-gradient="...">
    <h1>Presentation Title</h1>
    <p class="tagline">Subtitle or tagline here</p>
    <p class="author">Author Name</p>
</section>
```

---

## Animations & Fragments

### Fragment Types
```html
<p class="fragment fade-in">Fade in</p>
<p class="fragment fade-up">Fade up</p>
<p class="fragment fade-out">Fade out</p>
<p class="fragment highlight-red">Highlight red</p>
<p class="fragment grow">Grow</p>
<p class="fragment shrink">Shrink</p>
<p class="fragment strike">Strike through</p>
```

### Ordered Fragments
```html
<p class="fragment" data-fragment-index="1">First</p>
<p class="fragment" data-fragment-index="2">Second</p>
<p class="fragment" data-fragment-index="3">Third</p>
```

### Transition Types
```javascript
transition: 'none'    // Instant
transition: 'fade'    // Fade
transition: 'slide'   // Slide (default)
transition: 'convex'  // 3D convex
transition: 'concave' // 3D concave
transition: 'zoom'    // Zoom
```

---

## Typography

### Font Loading
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">

<style>
.reveal {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 1.2em;
}
</style>
```

### Heading Hierarchy
```css
.reveal h1 { font-size: 3.5em; font-weight: 700; }
.reveal h2 { font-size: 2.5em; font-weight: 600; }
.reveal h3 { font-size: 1.5em; font-weight: 600; }
```

### Responsive Text
```css
@media (max-width: 768px) {
    .reveal h1 { font-size: 2.5em; }
    .reveal h2 { font-size: 1.8em; }
}
```

---

## Markdown Integration

### Inline Markdown
```html
<section data-markdown>
    <textarea data-template>
## Slide Title

- Bullet point 1
- Bullet point 2

```python
def hello():
    print("Hello")
```
    </textarea>
</section>
```

### External Markdown File
```html
<section data-markdown="slides.md" data-separator="^\n---\n" data-separator-vertical="^\n--\n">
</section>
```

### Markdown Comments (Hidden Notes)
```markdown
## Slide Title

Content here.

<!-- Claude feedback: Add chart here -->
<!-- Corporate note: Use brand blue #005EA2 -->

- Bullet 1
```

### Element Attributes via Comments
```markdown
## Title

<!-- .element: class="r-stretch" -->
![Image](photo.jpg)

<!-- .slide: data-background="#ff0000" -->
```

---

## Code Highlighting

### Basic Code Block
```html
<pre><code class="language-python" data-trim data-noescape>
def analyze_data(df):
    return df.groupby('category').mean()
</code></pre>
```

### Line Highlighting
```html
<pre><code data-line-numbers="1|3-4|6">
line 1
line 2
line 3
line 4
line 5
line 6
</code></pre>
```

### Attributes
| Attribute | Effect |
|-----------|--------|
| `data-trim` | Remove leading/trailing whitespace |
| `data-noescape` | Prevent HTML escaping |
| `data-line-numbers` | Show line numbers (or highlight specific lines) |

---

## Branding & Polish

### Slide Numbers
```javascript
slideNumber: true         // Simple: 1, 2, 3...
slideNumber: 'c/t'        // Current/Total: 3/12
slideNumber: 'h.v'        // Horizontal.Vertical: 2.3
slideNumber: 'h/v'        // Alternative format
```

### Custom Footer
```html
<style>
.reveal .slide-footer {
    position: absolute;
    bottom: 1em;
    left: 1em;
    font-size: 0.5em;
    color: #888;
}
</style>

<div class="slide-footer">Company Name | Confidential</div>
```

### Progress Bar Styling
```css
.reveal .progress {
    background: rgba(255,255,255,0.1);
    height: 4px;
}
.reveal .progress span {
    background: #0066cc;
}
```

---

## PDF Export

### Enable Print Mode
Append `?print-pdf` to URL:
```
https://yoursite.com/slides/?print-pdf
```

### Print CSS Tips
```css
@media print {
    .reveal .slides section {
        page-break-after: always;
    }
    .no-print { display: none; }
}
```

### Chrome Print Settings
- Destination: Save as PDF
- Layout: Landscape
- Margins: None
- Background graphics: Enabled

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `→` `↓` `Space` | Next slide |
| `←` `↑` | Previous slide |
| `F` | Fullscreen |
| `S` | Speaker view |
| `O` | Overview mode |
| `B` `.` | Pause (black screen) |
| `Esc` | Exit overview/fullscreen |
| `?` | Show help |
| `Home` | First slide |
| `End` | Last slide |

---

## Plugins

### Essential Plugins
```javascript
plugins: [
    RevealHighlight,  // Code syntax highlighting
    RevealNotes,      // Speaker notes (press S)
    RevealMath,       // LaTeX math rendering
    RevealSearch,     // Ctrl+Shift+F search
    RevealZoom        // Alt+click to zoom
]
```

### Math Plugin (KaTeX)
```html
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/plugin/math/math.js"></script>
<script>
    Reveal.initialize({
        math: { mathjax: 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js' },
        plugins: [RevealMath]
    });
</script>
```

Usage: `$E = mc^2$` for inline, `$$\int_0^\infty$$` for block.

---

## Vertical Slides

### Creating a Vertical Stack
```html
<section>
    <section>Horizontal slide 1 (top)</section>
    <section>Vertical slide 1.1</section>
    <section>Vertical slide 1.2</section>
</section>
<section>Horizontal slide 2</section>
```

Users press ↓ to navigate vertical stack, → to move to next horizontal slide.

---

## Performance Tips

1. **Lazy load images**: Use `data-src` instead of `src`
2. **Preload adjacent slides**: `preloadIframes: true`
3. **Minimize DOM**: Keep slide content lean
4. **Use CDN**: Faster than self-hosting for most cases
5. **Compress images**: WebP format, appropriate dimensions

---

## Useful Resources

- [Reveal.js Docs](https://revealjs.com)
- [Reveal.js GitHub](https://github.com/hakimel/reveal.js)
- [reveal-md](https://github.com/webpro/reveal-md) - Markdown CLI tool
- [Quarto Revealjs](https://quarto.org/docs/presentations/revealjs/) - YAML-driven presentations
- [GDS Template](https://github.com/alphagov/gds-reveal.js-presentation-template) - Government template
- [Adobe Theme](https://github.com/stlab/adobe-reveal-theme) - Corporate theme example

---

## tech-econ Brand Reference

For tech-econ.com presentations:
```css
:root {
    --te-accent: #0066cc;
    --te-accent-light: #4da6ff;
    --te-bg-dark: #0a0a0a;
    --te-bg-card: #161616;
    --te-text-primary: #f0f0f0;
    --te-text-muted: #888;
}
```

Font: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
