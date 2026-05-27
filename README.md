# Stanford CBCL AR Models

This repository turns VTK geometry into AR-ready assets and publishes them as a GitHub Pages site with one page per model.

It supports two workflows:

- static models from `.vtp` or `.vtu` inputs
- animated models from time-series `.vtu` inputs with `--animated`

Website is live at [https://stanfordcbcl.github.io/ar-models/](https://stanfordcbcl.github.io/ar-models/)


## Adding a model

Firstly, you need the following installed locally

- `/Applications/ParaView-6.1.0.app`
- `/Applications/Blender.app`
- macOS shell with `/usr/bin/python3`

There are two good ways to add a model to the site.

### Option 1: Run the one-shot command yourself

Static model:

```bash
./bin/vtk-to-ar --name "<slug-for-your-model>" --title "<title-for-your-model>" "<path-to-your-vtk-files>"
```

Animated model:

```bash
./bin/vtk-to-ar --animated --name "<slug-for-your-model>" --title "<title-for-your-model>" "<path-to-your-time-series-vtu-files>"
```

The command will:

1. Discover `.vtp` and `.vtu` files from the provided paths.
2. Choose the static or animated pipeline based on `--animated`.
3. Ask for Blender-facing parameters unless you pass them explicitly.
4. Export intermediate `.ply` meshes with ParaView.
5. Build `.glb` and `.usdz` assets with Blender.
6. Publish assets, update the manifest, regenerate the index page, and create `docs/models/<slug>/index.html`.

Useful static-model flags:

```bash
./bin/vtk-to-ar \
  --name "<slug-for-your-model>" \
  --title "<title-for-your-model>" \
  --fit-meters <target-size-in-meters> \
  --decimate-ratio <value-between-0-and-1> \
  --rotation-deg <x,y,z-degrees> \
  --color-mode <auto-or-vertex> \
  --part-color <part-name>=#RRGGBB \
  --non-interactive \
  "<path-to-your-vtk-files>"
```

Useful animated-model flags:

```bash
./bin/vtk-to-ar \
  --animated \
  --name "<slug-for-your-model>" \
  --title "<title-for-your-model>" \
  --animation-frames <sampled-frame-count> \
  --animation-fps <viewer-fps> \
  --pressure-array <point-data-array-name> \
  --pressure-divisor <unit-conversion-divisor> \
  --representative-frame peak-max-pressure \
  --fit-meters <target-size-in-meters> \
  --decimate-ratio <value-between-0-and-1> \
  --rotation-deg <x,y,z-degrees> \
  --non-interactive \
  "<path-to-your-time-series-vtu-files>"
```

Animated export notes:

- Animated exports force `--color-mode vertex`.
- Animated exports do not support `--part-color`.
- The animated viewer GLB and the static download assets are generated through different branches of the pipeline.

### Option 2: Use the skill

The Codex skill for this workflow lives at `skills/vtk-to-ar/SKILL.md`.

Use it when you want an agent to help convert and publish a model set. The intended flow is:

1. Give the agent the `.vtp` or `.vtu` inputs.
2. Have the agent determine whether this should be a static model or an animated time-series model.
3. Have the agent ask what Blender modifications you want:
   scale, centering, rotation, decimation, colors, smoothing, and any part visibility changes.
4. For animated models, have the agent also confirm the point-data quantity to visualize, frame sampling, and representative-frame strategy.
5. Let the agent run `./bin/vtk-to-ar ...` and show you the result.
6. Iterate on those Blender parameters until the model looks right.
7. Publish the generated `docs/` updates in a pull request.

The skill is designed around iteration, so the agent should keep asking for adjustment requests until you approve the output.

### Publishing flow

- Generated assets land under `docs/assets/models/<slug>/`
- Model pages land under `docs/models/<slug>/`
- The site index is `docs/index.html`
- The manifest is `docs/assets/models/manifest.json`

For animated models:

- `docs/assets/models/<slug>/<slug>.glb` is the animated viewer asset.
- `docs/assets/models/<slug>/<slug>-static.glb` is the representative-frame static download.
- `docs/assets/models/<slug>/<slug>.usdz` is the iOS asset built from the representative frame.

### Troubleshooting

- Static models and animated-derived static assets do not follow exactly the same geometry path.
- Animated exports decimate and select a representative surface in ParaView before Blender export.
- Animated viewer colors are postprocessed into the GLB after Blender export.
- iOS `.usdz` output for animated models uses a baked-texture path, so Quick Look issues should be debugged separately from the web GLB.
