from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .core import (
    AnimationConfig,
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
    sort_time_series_files,
    upsert_manifest_entry,
)
from .glb_postprocess import embed_animated_pressure_colors
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
    parser.add_argument("--animated", action="store_true", help="Treat the inputs as a time-series and build an animated GLB.")
    parser.add_argument("--animation-frames", type=int, default=28, help="Number of sampled frames to keep for animated exports.")
    parser.add_argument("--animation-fps", type=int, default=12, help="Playback fps for animated GLB exports.")
    parser.add_argument("--pressure-array", default="Pressure", help="Point-data array to present for animated exports.")
    parser.add_argument("--pressure-divisor", type=float, default=1333.2, help="Divide the pressure array by this value to convert to display units.")
    parser.add_argument(
        "--pressure-label-mode",
        choices=["normalized-cycle"],
        default="normalized-cycle",
        help="Frame label mode for animated exports.",
    )
    parser.add_argument(
        "--representative-frame",
        choices=["peak-max-pressure"],
        default="peak-max-pressure",
        help="How to choose the static download frame for animated exports.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    slug = slugify(args.name)
    title = args.title or infer_title(slug)
    files = discover_input_files(args.inputs)
    config = collect_scene_config(args)
    animation = collect_animation_config(args)
    check_tool("pvpython", Path("/Applications/ParaView-6.1.0.app/Contents/bin/pvpython"))
    check_tool("Blender", Path("/Applications/Blender.app/Contents/MacOS/Blender"))

    build_dir = BUILD_DIR / slug
    ply_dir = build_dir / "ply"
    docs_model_dir = DOCS_DIR / "assets" / "models" / slug
    page_dir = DOCS_DIR / "models" / slug
    output_glb = docs_model_dir / f"{slug}.glb"
    download_glb = docs_model_dir / f"{slug}-static.glb"
    output_usdz = docs_model_dir / f"{slug}.usdz"
    if not config.overwrite and (output_glb.exists() or output_usdz.exists() or download_glb.exists()):
        raise SystemExit(f"Refusing to overwrite existing assets for {slug}. Re-run with overwrite enabled.")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    ply_dir.mkdir(parents=True, exist_ok=True)
    docs_model_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)

    pv_config_path = build_dir / "pv-config.json"
    blender_config_path = build_dir / "blender-config.json"
    if animation is None:
        part_names = infer_part_names(files)
        color_overrides = parse_color_overrides(args.part_color)
        colors = default_part_colors(part_names)
        colors.update(color_overrides)

        conversion_inputs = []
        for path, part_name in zip(files, part_names):
            conversion_inputs.append({"input": str(path), "part_name": part_name})
        pv_config_path.write_text(json.dumps({"mode": "static", "output_dir": str(ply_dir), "inputs": conversion_inputs}, indent=2))
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

        blender_config_path.write_text(
            json.dumps(
                {
                    "mode": "static",
                    **config.blender_payload(),
                    "inputs": blender_inputs,
                    "output_glb": str(output_glb.resolve()),
                    "output_usdz": str(output_usdz.resolve()),
                },
                indent=2,
            )
        )
        run_blender_export(blender_config_path)
        enforce_size_limit(output_glb)
        enforce_size_limit(output_usdz)
        entry = build_manifest_entry(slug=slug, title=title, parts=part_names, config=config)
    else:
        animation_files = sort_time_series_files(files)
        pv_summary_path = build_dir / "pv-summary.json"
        pv_config_path.write_text(
            json.dumps(
                {
                    "mode": "animated",
                    "output_dir": str(ply_dir),
                    "inputs": [str(path) for path in animation_files],
                    "frame_count": animation.frame_count,
                    "pressure_array": animation.pressure_array,
                    "pressure_divisor": animation.pressure_divisor,
                    "representative_frame": animation.representative_frame,
                    "decimate_ratio": config.decimate_ratio,
                    "metadata_path": str(pv_summary_path),
                    "color_data_path": str((build_dir / "pressure-colors.bin").resolve()),
                },
                indent=2,
            )
        )
        run_command(
            ["/Applications/ParaView-6.1.0.app/Contents/bin/pvpython", str(PV_SCRIPT), str(pv_config_path)],
            env=None,
        )
        pv_summary = json.loads(pv_summary_path.read_text())
        blender_config_path.write_text(
            json.dumps(
                {
                    "mode": "animated",
                    **config.blender_payload(),
                    "fps": animation.fps,
                    "representative_ply": pv_summary["representativeFrame"]["ply"],
                    "frame_plys": [frame["ply"] for frame in pv_summary["sampledFrames"]],
                    "representative_frame_index": pv_summary["representativeFrame"]["sampledIndex"],
                    "output_glb": str(output_glb.resolve()),
                    "output_download_glb": str(download_glb.resolve()),
                    "output_usdz": str(output_usdz.resolve()),
                },
                indent=2,
            )
        )
        run_blender_export(blender_config_path)
        embed_animated_pressure_colors(output_glb, pv_summary)
        verify_glb_has_animations(output_glb)
        verify_glb_has_pressure_color_morphs(output_glb)
        enforce_size_limit(output_glb)
        enforce_size_limit(download_glb)
        enforce_size_limit(output_usdz)
        entry = build_manifest_entry(
            slug=slug,
            title=title,
            parts=[str(pv_summary["partName"])],
            config=config,
            animation=build_animation_metadata(animation, pv_summary, output_glb),
            pressure_presentation=build_pressure_metadata(animation, pv_summary, slug),
            glb_path=f"assets/models/{slug}/{slug}.glb",
            usdz_path=f"assets/models/{slug}/{slug}.usdz",
            download_glb_path=f"assets/models/{slug}/{slug}-static.glb",
        )

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
    color_mode = args.color_mode
    if args.animated:
        if color_mode not in {None, "vertex"}:
            raise SystemExit("Animated exports require vertex colors for pressure presentation.")
        color_mode = "vertex"
    if args.non_interactive:
        return prompt_scene_config(
            lambda _: "",
            fit_meters=args.fit_meters,
            decimate_ratio=args.decimate_ratio,
            centered=args.centered,
            shade_smooth=args.shade_smooth,
            rotation_deg=parse_rotation(args.rotation_deg) if args.rotation_deg else None,
            color_mode=color_mode,
            overwrite=args.overwrite,
        )
    return prompt_scene_config(
        input,
        fit_meters=args.fit_meters,
        decimate_ratio=args.decimate_ratio,
        centered=args.centered,
        shade_smooth=args.shade_smooth,
        rotation_deg=parse_rotation(args.rotation_deg) if args.rotation_deg else None,
        color_mode=color_mode,
        overwrite=args.overwrite,
    )


def collect_animation_config(args: argparse.Namespace) -> AnimationConfig | None:
    if not args.animated:
        return None
    if args.part_color:
        raise SystemExit("Animated exports do not support --part-color overrides.")
    return AnimationConfig(
        frame_count=args.animation_frames,
        fps=args.animation_fps,
        pressure_array=args.pressure_array,
        pressure_divisor=args.pressure_divisor,
        label_mode=args.pressure_label_mode,
        representative_frame=args.representative_frame,
    )


def check_tool(label: str, path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"{label} was not found at {path}")


def run_command(command: list[str], env: dict[str, str] | None) -> None:
    completed = subprocess.run(command, check=False, env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def run_blender_export(blender_config_path: Path) -> None:
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


def enforce_size_limit(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Expected generated asset at {path}")
    size = path.stat().st_size
    if size > GLB_FAIL_BYTES:
        raise SystemExit(f"{path.name} is {size / (1024 * 1024):.1f} MiB, above the 95 MiB publishing limit.")
    if size > GLB_WARN_BYTES:
        print(f"Warning: {path.name} is {size / (1024 * 1024):.1f} MiB. Consider stronger decimation.")


def build_animation_metadata(
    animation: AnimationConfig,
    pv_summary: dict[str, object],
    output_glb: Path,
) -> dict[str, object]:
    sampled_frames = pv_summary["sampledFrames"]
    duration_seconds = 0.0
    if animation.fps > 0:
        duration_seconds = max(len(sampled_frames) - 1, 1) / animation.fps
    return {
        "enabled": True,
        "frameCount": len(sampled_frames),
        "fps": animation.fps,
        "durationSeconds": duration_seconds,
        "labelMode": animation.label_mode,
        "representativeFrame": pv_summary["representativeFrame"],
        "viewerAsset": output_glb.name,
        "viewerVerified": True,
    }


def build_pressure_metadata(animation: AnimationConfig, pv_summary: dict[str, object], slug: str) -> dict[str, object]:
    return {
        "arrayName": animation.pressure_array,
        "unit": "mmHg",
        "divisor": animation.pressure_divisor,
        "rangeMmHg": pv_summary["globalPressureRangeMmHg"],
        "colorRangeMmHg": pv_summary["colorRangeMmHg"],
        "vertexCount": pv_summary["surface"]["vertexCount"],
        "sampledFrames": pv_summary["sampledFrames"],
        "colorStrategy": "glb-morph-target-colors",
        "delivery": "model-viewer",
        "downloadAssets": {
            "glbFrame": pv_summary["representativeFrame"]["sourceName"],
            "usdzFrame": pv_summary["representativeFrame"]["sourceName"],
        },
    }


def verify_glb_has_animations(path: Path) -> None:
    payload = load_glb_json(path)
    animations = payload.get("animations", [])
    if not animations:
        raise SystemExit(f"Expected {path.name} to contain at least one animation.")


def verify_glb_has_pressure_color_morphs(path: Path) -> None:
    payload = load_glb_json(path)
    targets = payload["meshes"][0]["primitives"][0].get("targets", [])
    if not targets:
        raise SystemExit(f"Expected {path.name} to contain morph targets.")
    if any("COLOR_0" not in target for target in targets):
        raise SystemExit(f"Expected every morph target in {path.name} to contain COLOR_0 pressure deltas.")


def load_glb_json(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        header = handle.read(12)
        if len(header) != 12 or header[:4] != b"glTF":
            raise SystemExit(f"{path} is not a valid GLB file.")
        chunk_header = handle.read(8)
        if len(chunk_header) != 8:
            raise SystemExit(f"{path} is missing a JSON chunk.")
        chunk_length = int.from_bytes(chunk_header[:4], "little")
        chunk_type = chunk_header[4:]
        if chunk_type != b"JSON":
            raise SystemExit(f"{path} has an unexpected first chunk type: {chunk_type!r}")
        return json.loads(handle.read(chunk_length).decode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
