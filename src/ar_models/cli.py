from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .core import (
    build_manifest_entry,
    default_part_colors,
    discover_input_files,
    infer_part_names,
    infer_title,
    load_manifest,
    parse_color_overrides,
    parse_rotation,
    prompt_scene_config,
    save_manifest,
    slugify,
    upsert_manifest_entry,
)
from .site import write_index_page, write_model_page


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
MANIFEST_PATH = DOCS_DIR / "assets" / "models" / "manifest.json"
BUILD_DIR = ROOT / ".build"
PV_SCRIPT = ROOT / "src" / "ar_models" / "pv_export.py"
BLENDER_SCRIPT = ROOT / "src" / "ar_models" / "blender_export.py"
GLB_WARN_BYTES = 50 * 1024 * 1024
GLB_FAIL_BYTES = 95 * 1024 * 1024


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert VTP/VTU meshes into AR assets and publish them to GitHub Pages.")
    parser.add_argument("inputs", nargs="+", help="Input .vtp/.vtu files or directories containing them.")
    parser.add_argument("--name", required=True, help="Slug for the model and page.")
    parser.add_argument("--title", help="Display title for the model page.")
    parser.add_argument("--fit-meters", type=float, help="Target size for the longest scene dimension.")
    parser.add_argument("--decimate-ratio", type=float, help="Blender decimation ratio from 0.0 to 1.0.")
    parser.add_argument("--rotation-deg", help="Rotation as x,y,z in degrees.")
    parser.add_argument("--color-mode", choices=["auto", "vertex"], help="Use palette colors or imported vertex colors.")
    parser.add_argument("--centered", dest="centered", action="store_true", default=None, help="Center the model around the origin.")
    parser.add_argument("--no-centered", dest="centered", action="store_false", help="Preserve imported origin.")
    parser.add_argument("--shade-smooth", dest="shade_smooth", action="store_true", default=None, help="Enable smooth shading.")
    parser.add_argument("--no-shade-smooth", dest="shade_smooth", action="store_false", help="Disable smooth shading.")
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", default=None, help="Overwrite generated assets.")
    parser.add_argument("--no-overwrite", dest="overwrite", action="store_false", help="Stop if outputs already exist.")
    parser.add_argument("--non-interactive", action="store_true", help="Do not prompt for missing Blender settings.")
    parser.add_argument("--part-color", action="append", default=[], help="Override a part color with part=#RRGGBB.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    slug = slugify(args.name)
    title = args.title or infer_title(slug)
    files = discover_input_files(args.inputs)
    part_names = infer_part_names(files)
    color_overrides = parse_color_overrides(args.part_color)
    colors = default_part_colors(part_names)
    colors.update(color_overrides)

    config = collect_scene_config(args)
    check_tool("pvpython", Path("/Applications/ParaView-6.1.0.app/Contents/bin/pvpython"))
    check_tool("Blender", Path("/Applications/Blender.app/Contents/MacOS/Blender"))

    build_dir = BUILD_DIR / slug
    ply_dir = build_dir / "ply"
    docs_model_dir = DOCS_DIR / "assets" / "models" / slug
    page_dir = DOCS_DIR / "models" / slug
    output_glb = docs_model_dir / f"{slug}.glb"
    output_usdz = docs_model_dir / f"{slug}.usdz"
    if not config.overwrite and (output_glb.exists() or output_usdz.exists()):
        raise SystemExit(f"Refusing to overwrite existing assets for {slug}. Re-run with overwrite enabled.")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    ply_dir.mkdir(parents=True, exist_ok=True)
    docs_model_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)

    conversion_inputs = []
    for path, part_name in zip(files, part_names):
        conversion_inputs.append({"input": str(path), "part_name": part_name})

    pv_config_path = build_dir / "pv-config.json"
    pv_config_path.write_text(json.dumps({"output_dir": str(ply_dir), "inputs": conversion_inputs}, indent=2))
    run_command(
        ["/Applications/ParaView-6.1.0.app/Contents/bin/pvpython", str(PV_SCRIPT), str(pv_config_path)],
        env=None,
    )

    blender_inputs = []
    for part_name in part_names:
        blender_inputs.append(
            {
                "part_name": part_name,
                "ply": str((ply_dir / f"{part_name}.ply").resolve()),
                "color": colors[part_name],
            }
        )

    blender_config_path = build_dir / "blender-config.json"
    blender_config_path.write_text(
        json.dumps(
            {
                **config.blender_payload(),
                "inputs": blender_inputs,
                "output_glb": str(output_glb.resolve()),
                "output_usdz": str(output_usdz.resolve()),
            },
            indent=2,
        )
    )
    run_command(
        [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "--factory-startup",
            "--background",
            "--python",
            str(BLENDER_SCRIPT),
            "--",
            str(blender_config_path),
        ],
        env=None,
    )

    enforce_size_limit(output_glb)
    enforce_size_limit(output_usdz)

    entry = build_manifest_entry(slug=slug, title=title, parts=part_names, config=config)
    manifest = load_manifest(MANIFEST_PATH)
    manifest = upsert_manifest_entry(manifest, entry)
    save_manifest(MANIFEST_PATH, manifest)
    write_index_page(DOCS_DIR / "index.html", manifest)
    write_model_page(page_dir / "index.html", entry)

    summary_path = page_dir / "model.json"
    summary_path.write_text(json.dumps(entry, indent=2) + "\n")
    print(f"Published {title} at {page_dir / 'index.html'}")
    return 0


def collect_scene_config(args: argparse.Namespace):
    if args.non_interactive:
        return prompt_scene_config(
            lambda _: "",
            fit_meters=args.fit_meters,
            decimate_ratio=args.decimate_ratio,
            centered=args.centered,
            shade_smooth=args.shade_smooth,
            rotation_deg=parse_rotation(args.rotation_deg) if args.rotation_deg else None,
            color_mode=args.color_mode,
            overwrite=args.overwrite,
        )
    return prompt_scene_config(
        input,
        fit_meters=args.fit_meters,
        decimate_ratio=args.decimate_ratio,
        centered=args.centered,
        shade_smooth=args.shade_smooth,
        rotation_deg=parse_rotation(args.rotation_deg) if args.rotation_deg else None,
        color_mode=args.color_mode,
        overwrite=args.overwrite,
    )


def check_tool(label: str, path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"{label} was not found at {path}")


def run_command(command: list[str], env: dict[str, str] | None) -> None:
    completed = subprocess.run(command, check=False, env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def enforce_size_limit(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Expected generated asset at {path}")
    size = path.stat().st_size
    if size > GLB_FAIL_BYTES:
        raise SystemExit(f"{path.name} is {size / (1024 * 1024):.1f} MiB, above the 95 MiB publishing limit.")
    if size > GLB_WARN_BYTES:
        print(f"Warning: {path.name} is {size / (1024 * 1024):.1f} MiB. Consider stronger decimation.")


if __name__ == "__main__":
    raise SystemExit(main())
