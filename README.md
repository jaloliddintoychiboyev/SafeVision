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

---

## The detection code

`safevision/` is the working core of the project: the signal chain that turns a
24 GHz FMCW radar's raw ADC samples into a driver warning. It has **no
dependencies** - pure Python standard library - so a reviewer can clone and run
it immediately.

| Module | Purpose |
|--------|---------|
| `safevision/radar.py` | Sensor model plus the signal chain: range FFT -> Doppler FFT -> CA-CFAR detection |
| `safevision/simulator.py` | Generates the raw beat signal for a scene, so the chain is testable without hardware |
| `safevision/hazard.py` | Time-to-contact, braking distance and warning levels |
| `safevision/v2v.py` | Shared hazard map - the fleet relay that produces the 15-second warning |
| `demo.py` | End-to-end runnable demo |
| `tests/test_pipeline.py` | 14 tests covering the whole pipeline |

### Run it

```bash
python3 demo.py                 # default scene: pothole at 28 m, stalled vehicle at 62 m
python3 -m unittest discover -s tests -v
```

Describe your own scene:

```bash
python3 demo.py --speed 100 --targets "pothole:35:0.6,debris:70:1.5"
```

### What the demo shows

```
Detections (2):
    28.2 m   -22.8 m/s   44.4 dB
    61.8 m   -22.8 m/s   42.1 dB

Driver warnings:
  [CRITICAL] Brake now - hazard 28 m ahead  (TTC 1.2 s, confidence 100%)
  [CRITICAL] Brake now - hazard 62 m ahead  (TTC 2.7 s, confidence 100%)

Shared hazard map: 2 hazard(s) broadcast, 2 on the map
Following vehicle, still 333 m short of the hazard (its own radar horizon is only 77 m):
  [CRITICAL] hazard in 333 m - 15 s of warning, confidence 100%
```

Both hazards are recovered to within one range gate (0.6 m) and their closing
speed to within two Doppler bins, with no false alarms.

### Where the two headline numbers come from

- **50 m detection range** - the single-sensor horizon. With the configuration in
  `RadarConfig` (250 MHz sweep, 4 MHz ADC) the unambiguous maximum is ~77 m, and
  50 m is the range at which a pothole-sized 0.5 m^2 target still clears the CFAR
  threshold reliably.
- **15 s of warning** - the fleet horizon, not the single-sensor one. One sensor
  at 80 km/h gives about 3 seconds. The 15 seconds comes from `v2v.py`: a hazard
  confirmed by one vehicle is broadcast, and every following vehicle is warned
  roughly 330 m ahead of it - far beyond what its own radar can see.

### Design notes

- **CA-CFAR, not a fixed threshold.** Road clutter changes constantly with
  surface, traffic and weather; cell-averaging CFAR holds the false-alarm rate
  constant instead of the threshold.
- **Time-to-contact, not distance.** A 60 m gap is comfortable at 40 km/h and an
  emergency at 120 km/h, so warnings are ranked by TTC and compared against the
  driver's actual braking distance, including a 2.5 s reaction time.
- **Confidence compounds across vehicles.** Repeated independent sightings of the
  same spot raise confidence but never reach certainty, so one stray reflection
  can be outvoted while a real pothole is confirmed.
