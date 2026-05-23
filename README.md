# Stanford CBCL AR Models

This repository turns `.vtp` and `.vtu` files into AR-ready `.glb` and `.usdz` assets and publishes them as a GitHub Pages site with one page per model.

## Live site

- Website: `https://stanfordcbcl.github.io/ar-models/`
- Example model page: `https://stanfordcbcl.github.io/ar-models/models/chips10-series5/`

If someone lands on the GitHub repository first, these are the URLs they can use to open the published site directly.

## Local prerequisites

- `/Applications/ParaView-6.1.0.app`
- `/Applications/Blender.app`
- macOS shell with `/usr/bin/python3`

## One-shot command

```bash
./bin/vtk-to-ar --name chips10-series5 --title "CHiPS-10 CT Series 5" "/Users/aaronbrown/Downloads/CHiPS-10 CT series 5 segmentation vtp files"
```

The command will:

1. Discover `.vtp` and `.vtu` files from the provided paths.
2. Ask for Blender-facing parameters unless you pass them explicitly.
3. Export intermediate `.ply` meshes with ParaView.
4. Build `.glb` and `.usdz` assets with Blender.
5. Publish assets, update the manifest, regenerate the index page, and create `docs/models/<slug>/index.html`.

## Useful flags

```bash
./bin/vtk-to-ar \
  --name chips10-series5 \
  --title "CHiPS-10 CT Series 5" \
  --fit-meters 0.18 \
  --decimate-ratio 0.30 \
  --rotation-deg 0,0,0 \
  --color-mode auto \
  --part-color aorta=#C9362D \
  --part-color lv=#7F0D0D \
  --non-interactive \
  "/Users/aaronbrown/Downloads/CHiPS-10 CT series 5 segmentation vtp files"
```

## Publishing flow

- Generated assets land under `docs/assets/models/<slug>/`
- Model pages land under `docs/models/<slug>/`
- The site index is `docs/index.html`
- The manifest is `docs/assets/models/manifest.json`

For the Stanford CBCL org workflow, contributors should run the command locally, inspect the result, iterate on Blender parameters if needed, then open a pull request with the generated pages and assets.

## Using the skill

The Codex skill for this workflow lives at `skills/vtk-to-ar/SKILL.md`.

Use it when you want an agent to help convert and publish a model set. The intended flow is:

1. Give the agent the `.vtp` or `.vtu` inputs.
2. Have the agent ask what Blender modifications you want:
   scale, centering, rotation, decimation, colors, smoothing, and any part visibility changes.
3. Let the agent run `./bin/vtk-to-ar ...` and show you the result.
4. Iterate on those Blender parameters until the model looks right.
5. Publish the generated `docs/` updates in a pull request.

The skill is designed around iteration, so the agent should keep asking for adjustment requests until you approve the output.
