---
name: vtk-to-ar
description: Convert VTP or VTU meshes into AR assets, iterate on Blender parameters with the user, and publish a dedicated GitHub Pages model page.
---

# VTK To AR

Use this skill when a user wants to turn `.vtp` or `.vtu` geometry into a published AR model page.

## What this skill requires

- Ask the user what Blender-side modifications they want before the final export.
- Treat scale, centering, rotation, decimation, colors, smoothing, and visibility as user-owned parameters.
- Expect iteration. Show the result, ask what they want changed, rerun the conversion, and repeat until they approve.
- Publish one dedicated page per model and make sure the page includes a QR code download button.

## Default workflow

1. Inspect the provided input files and decide whether they should become one combined scene or one model per file.
2. Ask the user what they want for:
   - physical size in AR
   - centering or preserved world origin
   - rotation
   - decimation amount
   - color handling
   - smooth shading
   - any part-specific color overrides or visibility choices
3. Run:

```bash
./bin/vtk-to-ar --name <slug> --title "<Title>" <inputs...>
```

4. Review the generated page and asset sizes.
5. If the user wants changes, rerun `./bin/vtk-to-ar` with updated parameters.
6. When approved, commit the generated `docs/` assets and open a PR.

## Notes

- `./bin/vtk-to-ar` prompts for missing Blender settings by default.
- Use `--non-interactive` only when you already know the right values.
- Prefer `--part-color part=#RRGGBB` for anatomy-specific adjustments.
- Keep an eye on generated asset size. The pipeline warns above roughly `50 MiB` and stops above roughly `95 MiB`.
