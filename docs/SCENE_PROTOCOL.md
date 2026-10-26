# SHINO // TV — Scene protocol v0 (desktop simulator)

Status: **draft**, intended for local preview only; not a live device protocol or a claim that the factory firmware accepts these messages.

Input: one JSON object with `kind` in `metrics`, `music`, `agent`, or `release`. All text is drawn in a canvas; it is never interpreted as HTML. Fields are bounded by the renderer. UI fixture values are **demo data** until connected to an explicit PC source.

Examples:

```json
{"kind":"metrics","title":"PC HEALTH","cpu":27,"gpu":62,"ram":43,"gpuTemp":68}
{"kind":"music","title":"NOW PLAYING","artist":"SHINOBIWAN","track":"MACHINE FEVER","progress":38}
{"kind":"agent","title":"CODEX","status":"RUNNING","task":"Build simulator","progress":72}
{"kind":"release","title":"NEXT RELEASE","artist":"SHINOBIWAN","track":"DANCE AT MY FUNERAL","days":12}
```

Scope: front-end preview and schema/renderer tests on PC, no HTTP traffic to a device and no writes to its flash. Any future transport will have independent authentication, resource limits and rate limits.

## Run preview (Windows / macOS / Linux)

From the repository root:

```bash
python -m http.server 8080 --directory simulator
```

Then open `http://localhost:8080` in your browser. Requires no external packages. The preview uses fictional sample values; its Save PNG button exports the current canvas.

Run renderer tests with `node --test simulator/scene.test.mjs` (Node.js 20+).
