from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable


SUPPORTED_EXTENSIONS = {".vtp", ".vtu"}
DEFAULT_PALETTE = [
    "#C9362D",
    "#2D6DCC",
    "#E68D2C",
    "#6E4CD8",
    "#0D8A6E",
    "#D84CA4",
    "#2C9AB7",
    "#8C5C2A",
    "#A5A832",
    "#3C4A8F",
]


@dataclass
class SceneConfig:
    fit_meters: float
    decimate_ratio: float
    centered: bool
    shade_smooth: bool
    rotation_deg: tuple[float, float, float]
    color_mode: str
    overwrite: bool

    def blender_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["rotation_deg"] = list(self.rotation_deg)
        return payload


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = slug.strip("-")
    if not slug:
        raise ValueError("Cannot derive a slug from an empty value.")
    return slug


def discover_input_files(paths: Iterable[str]) -> list[Path]:
    discovered: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input path does not exist: {path}")
        if path.is_dir():
            for ext in sorted(SUPPORTED_EXTENSIONS):
                discovered.extend(sorted(path.rglob(f"*{ext}")))
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported input type: {path}")
        discovered.append(path)

    unique = sorted(dict.fromkeys(discovered))
    if not unique:
        raise ValueError("No .vtp or .vtu files were found in the provided inputs.")
    return unique


def infer_title(slug: str) -> str:
    return slug.replace("-", " ").title()


def infer_part_names(files: Iterable[Path]) -> list[str]:
    return [path.stem for path in files]


def default_part_colors(part_names: Iterable[str]) -> dict[str, str]:
    colors: dict[str, str] = {}
    for index, name in enumerate(part_names):
        colors[name] = DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]
    return colors


def parse_color_overrides(values: Iterable[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Color override must look like part=#RRGGBB: {value}")
        key, color = value.split("=", 1)
        key = key.strip()
        color = color.strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError(f"Color override must use #RRGGBB format: {value}")
        overrides[key] = color.upper()
    return overrides


def parse_rotation(text: str) -> tuple[float, float, float]:
    parts = [piece.strip() for piece in text.split(",")]
    if len(parts) != 3:
        raise ValueError("Rotation must have exactly three comma-separated values.")
    return tuple(float(part) for part in parts)  # type: ignore[return-value]


def prompt_scene_config(
    prompt: Callable[[str], str],
    *,
    fit_meters: float | None = None,
    decimate_ratio: float | None = None,
    centered: bool | None = None,
    shade_smooth: bool | None = None,
    rotation_deg: tuple[float, float, float] | None = None,
    color_mode: str | None = None,
    overwrite: bool | None = None,
) -> SceneConfig:
    fit = fit_meters if fit_meters is not None else _prompt_float(prompt, "Fit longest dimension in meters", 0.18)
    decimate = (
        decimate_ratio
        if decimate_ratio is not None
        else _prompt_float(prompt, "Decimate ratio (0.0-1.0)", 0.30)
    )
    center_flag = centered if centered is not None else _prompt_bool(prompt, "Center model around the origin", True)
    smooth_flag = (
        shade_smooth
        if shade_smooth is not None
        else _prompt_bool(prompt, "Shade smooth in Blender", True)
    )
    rotation = (
        rotation_deg
        if rotation_deg is not None
        else parse_rotation(prompt("Rotation in degrees as x,y,z [0,0,0]: ").strip() or "0,0,0")
    )
    palette_mode = color_mode if color_mode is not None else (prompt("Color mode [auto/vertex] (auto): ").strip() or "auto")
    overwrite_flag = overwrite if overwrite is not None else _prompt_bool(prompt, "Overwrite existing generated assets", True)
    return SceneConfig(
        fit_meters=fit,
        decimate_ratio=decimate,
        centered=center_flag,
        shade_smooth=smooth_flag,
        rotation_deg=rotation,
        color_mode=palette_mode,
        overwrite=overwrite_flag,
    )


def build_manifest_entry(
    *,
    slug: str,
    title: str,
    parts: list[str],
    config: SceneConfig,
) -> dict[str, object]:
    return {
        "slug": slug,
        "title": title,
        "page": f"models/{slug}/",
        "glb": f"assets/models/{slug}/{slug}.glb",
        "usdz": f"assets/models/{slug}/{slug}.usdz",
        "parts": parts,
        "blenderParameters": config.blender_payload(),
    }


def load_manifest(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_manifest(path: Path, entries: list[dict[str, object]]) -> None:
    ordered = sorted(entries, key=lambda entry: str(entry["title"]).lower())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ordered, indent=2) + "\n")


def upsert_manifest_entry(entries: list[dict[str, object]], new_entry: dict[str, object]) -> list[dict[str, object]]:
    filtered = [entry for entry in entries if entry.get("slug") != new_entry["slug"]]
    filtered.append(new_entry)
    return filtered


def _prompt_float(prompt: Callable[[str], str], label: str, default: float) -> float:
    raw = prompt(f"{label} [{default}]: ").strip()
    return float(raw) if raw else default


def _prompt_bool(prompt: Callable[[str], str], label: str, default: bool) -> bool:
    marker = "Y/n" if default else "y/N"
    raw = prompt(f"{label} [{marker}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}
