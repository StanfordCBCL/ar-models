# AR Models Agent Guide

This repository publishes Stanford CBCL AR models as a static GitHub Pages site.

## What matters most

- The user-facing entrypoint is `./bin/vtk-to-ar`.
- The static site is served from `docs/`.
- The homepage and model pages are generated files. Prefer regenerating them through Python helpers instead of hand-editing the HTML.
- The manifest at `docs/assets/models/manifest.json` is the source of truth for which models appear on the homepage.

## Repo map

- `bin/vtk-to-ar`
  Wrapper that runs `python3 -m ar_models.cli`.
- `src/ar_models/cli.py`
  Main pipeline: discover inputs, choose static vs animated mode, ask for Blender parameters, run ParaView and Blender, update manifest, regenerate pages.
- `src/ar_models/pv_export.py`
  ParaView-side export from `.vtp` or `.vtu` to intermediate `.ply`, including animated frame sampling and representative-frame selection.
- `src/ar_models/blender_export.py`
  Blender-side import, transform, decimation, normal repair, materials, and `.glb` / `.usdz` export.
- `src/ar_models/site.py`
  HTML generators for the homepage and the dedicated model pages.
- `skills/vtk-to-ar/SKILL.md`
  Agent-facing workflow guidance for using this repo.
- `docs/assets/models/manifest.json`
  Published model registry.
- `docs/assets/models/<slug>/`
  Generated binary assets for one model.
- `docs/models/<slug>/index.html`
  Dedicated page for one model.

## Safe editing rules

- Do not hand-edit `docs/index.html` unless you are debugging generator output. Prefer changing `src/ar_models/site.py` and regenerating the page.
- Do not hand-edit `docs/models/<slug>/index.html` unless you are diagnosing a generation issue. Prefer changing `write_model_page()` in `src/ar_models/site.py`.
- Do not edit generated `.glb` or `.usdz` files directly.
- If you add new homepage or page-level features, implement them in `src/ar_models/site.py`, then regenerate.

## Common workflows

### Add a new static model

```bash
./bin/vtk-to-ar --name <slug> --title "<Title>" /path/to/input
```

The command will prompt for Blender-facing parameters unless `--non-interactive` is passed.

### Add a new animated model

```bash
./bin/vtk-to-ar --animated --name <slug> --title "<Title>" /path/to/time-series-vtu-dir
```

Animated exports currently assume a time-series `.vtu` input set and produce:

- an animated viewer GLB at `docs/assets/models/<slug>/<slug>.glb`
- a representative-frame static GLB at `docs/assets/models/<slug>/<slug>-static.glb`
- an iOS USDZ at `docs/assets/models/<slug>/<slug>.usdz`

### Regenerate homepage from the current manifest

```bash
cd <repo-root>
PYTHONPATH=src /usr/bin/python3 -c "from pathlib import Path; from ar_models.core import load_manifest; from ar_models.site import write_index_page; manifest = load_manifest(Path('docs/assets/models/manifest.json')); write_index_page(Path('docs/index.html'), manifest)"
```

### Run tests

```bash
cd <repo-root>
PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
```

### Local preview

```bash
cd <repo-root>/docs
/usr/bin/python3 -m http.server 8008
```

Then open `http://127.0.0.1:8008/`.

## User interaction expectations

- First determine whether the user wants a static model or an animated time-series model.
- Ask the user what Blender modifications they want before the final export.
- Treat scale, centering, rotation, decimation, color handling, smoothing, and part visibility as user-owned choices.
- For animated exports, also treat frame sampling, representative-frame selection, and point-data array naming as user-visible choices when they are not already fixed.
- Expect iteration. The intended workflow is generate, review, revise, and regenerate.

## Known quirks

- Blender may warn that some imported meshes are “not valid.” The current CHiPS sample still exports successfully despite those warnings.
- Static exports and animated-derived static assets do not use identical geometry paths.
- Animated exports decimate and select the representative surface in ParaView, then export the viewer GLB and static download assets through the animated Blender path.
- Animated scalar-field colors for the web viewer are postprocessed into the GLB after Blender export.
- Animated USDZ output uses a baked-texture iOS path, so Quick Look rendering issues may diverge from the web GLB.
- If an animated surface looks view-dependent or partially transparent on iOS, check normals and representative-frame surface orientation in the animated pipeline, not only the regular static pipeline.
- The QR preview and QR download button are client-side and depend on the current page URL.
- GitHub Pages deployment expects `main` branch with the `/docs` folder selected in repo settings.

## When updating documentation

- Keep `README.md` focused on humans landing on the repo page.
- Keep this file focused on future agents and maintenance workflows.
