# Stanford CBCL AR Models

This repository turns `.vtp` and `.vtu` files into AR-ready `.glb` and `.usdz` assets and publishes them as a GitHub Pages site with one page per model.

## Live site

- Website: [https://stanfordcbcl.github.io/ar-models/](https://stanfordcbcl.github.io/ar-models/)

If someone lands on the GitHub repository first, this is the direct link to the published site.

## Local prerequisites

- `/Applications/ParaView-6.1.0.app`
- `/Applications/Blender.app`
- macOS shell with `/usr/bin/python3`

## Adding a model

There are two good ways to add a model to the site.

### Option 1: Run the one-shot command yourself

```bash
./bin/vtk-to-ar --name "<slug-for-your-model>" --title "<title-for-your-model>" "<path-to-your-vtk-files>"
```

The command will:

1. Discover `.vtp` and `.vtu` files from the provided paths.
2. Ask for Blender-facing parameters unless you pass them explicitly.
3. Export intermediate `.ply` meshes with ParaView.
4. Build `.glb` and `.usdz` assets with Blender.
5. Publish assets, update the manifest, regenerate the index page, and create `docs/models/<slug>/index.html`.

Useful flags:

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

### Option 2: Use the skill

The Codex skill for this workflow lives at `skills/vtk-to-ar/SKILL.md`.

Use it when you want an agent to help convert and publish a model set. The intended flow is:

1. Give the agent the `.vtp` or `.vtu` inputs.
2. Have the agent ask what Blender modifications you want:
   scale, centering, rotation, decimation, colors, smoothing, and any part visibility changes.
3. Let the agent run `./bin/vtk-to-ar ...` and show you the result.
4. Iterate on those Blender parameters until the model looks right.
5. Publish the generated `docs/` updates in a pull request.

The skill is designed around iteration, so the agent should keep asking for adjustment requests until you approve the output.

## Publishing flow

- Generated assets land under `docs/assets/models/<slug>/`
- Model pages land under `docs/models/<slug>/`
- The site index is `docs/index.html`
- The manifest is `docs/assets/models/manifest.json`

For the Stanford CBCL org workflow, contributors should run the command locally, inspect the result, iterate on Blender parameters if needed, then open a pull request with the generated pages and assets.
