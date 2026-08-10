# SafeVision

**A modern solution for safe roads.**

SafeVision turns every car into a moving **24 GHz mmWave radar** sensor — detecting
road hazards up to **50 m** away and warning the driver **15 seconds** in advance,
with **92% accuracy** in prototype testing.

Built for the **President Tech Award 2026 · Incubation Program** (Transport &
Infrastructure track).

---

## The landing page

This repository contains a fast, dependency-free, **bilingual (English / Uzbek)**
landing page for the project. Everything is static — plain HTML, CSS and vanilla
JavaScript, no build step.

| File | Purpose |
|------|---------|
| `index.html` | The full one-page site (all sections, bilingual content inline) |
| `styles.css` | Design system, layout and animations |
| `script.js`  | Language toggle, scroll reveals, animated counters |
| `logo.svg`   | SafeVision radar logo (use for the application "Project logo" field) |
| `vercel.json`| Vercel static-hosting config (clean URLs + security headers) |

Sections: Hero · Problem · Solution · Technology · Market · Innovation · Goals ·
Roadmap · Budget · Team · The Ask · Contact.

### Language
Click **EN / UZ** in the top-right corner to switch languages. The choice is
remembered in the browser.

---

## Run it locally

No dependencies. Just open `index.html`, or serve the folder:

```bash
# Python
python3 -m http.server 3000

# or Node
npx serve .
```

Then visit <http://localhost:3000>.

---

## Deploy to Vercel

The site is at the repository root, so Vercel needs **no build configuration**.

### Option A — Dashboard (easiest)
1. Go to <https://vercel.com/new> and sign in with GitHub.
2. **Import** the `safevision` repository.
3. Framework Preset: **Other**. Leave *Build Command* and *Output Directory* empty.
4. Click **Deploy**. Your site goes live at `https://<project>.vercel.app`.

Every push to the connected branch redeploys automatically.

### Option B — Vercel CLI
```bash
npm i -g vercel
vercel          # preview deploy
vercel --prod   # production deploy
```

Use the resulting `https://…vercel.app` URL for the **MVP link** field of the
Incubation Program application.

---

## Application quick-reference

- **Startup name:** SafeVision
- **MVP link:** your Vercel URL (after deploying)
- **GitHub:** this repository
- **Project logo:** `logo.svg` (SVG, accepted by the form)
- **Presentation:** `SafeVision_PTA_2026.pdf` / `SafeVision_PTA_2026.pptx`

## License

[MIT](LICENSE)
