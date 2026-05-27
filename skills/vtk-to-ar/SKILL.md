---
name: vtk-to-ar
description: Convert VTP or VTU meshes into AR assets, iterate on Blender parameters with the user, and publish a dedicated GitHub Pages model page.
---

# VTK To AR

Use this skill when a user wants to turn `.vtp` or `.vtu` geometry into a published AR model page, either as a static model or as an animated time-series model.

## What this skill requires

- Determine whether the request is for a static model or an animated time-series model before proposing commands.
- Ask the user what Blender-side modifications they want before the final export.
- Treat scale, centering, rotation, decimation, colors, smoothing, and visibility as user-owned parameters.
- Expect iteration. Show the result, ask what they want changed, rerun the conversion, and repeat until they approve.
- Publish one dedicated page per model and make sure the page includes a QR code download button.

## Default workflow

1. Inspect the provided input files and decide whether this is a static model set or an animated time-series export.
2. Ask the user what they want for:
   - physical size in AR
   - centering or preserved world origin
   - rotation
   - decimation amount
   - color handling
   - smooth shading
   - any part-specific color overrides or visibility choices
3. If the request is animated, also confirm:
   - point-data quantity name to visualize
   - number of sampled frames
   - playback fps
   - representative-frame strategy
4. Run the appropriate command:

```bash
./bin/vtk-to-ar --name <slug> --title "<Title>" <inputs...>
```

```bash
./bin/vtk-to-ar --animated --name <slug> --title "<Title>" <time-series-inputs...>
```

5. Review the generated page and asset sizes.
6. If the user wants changes, rerun `./bin/vtk-to-ar` with updated parameters.
7. When approved, commit the generated `docs/` assets and open a PR.

## Notes

- `./bin/vtk-to-ar` prompts for missing Blender settings by default.
- Use `--non-interactive` only when you already know the right values.
- Prefer `--part-color part=#RRGGBB` for anatomy-specific adjustments.
- Animated exports force vertex-color mode and do not support `--part-color`.
- For animated models, `<slug>.glb` is the animated viewer asset, `<slug>-static.glb` is the representative-frame download, and `<slug>.usdz` is the iOS representative-frame asset.
- The animated viewer GLB and animated-derived static assets do not pass through exactly the same export path as ordinary static models.
- Keep an eye on generated asset size. The pipeline warns above roughly `50 MiB` and stops above roughly `95 MiB`.
