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
FRAME_NUMBER_PATTERN = re.compile(r"(\d+)(?!.*\d)")


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


@dataclass(frozen=True)
class AnimationConfig:
    frame_count: int
    fps: int
    pressure_array: str
    pressure_divisor: float
    label_mode: str
    representative_frame: str

    def payload(self) -> dict[str, object]:
        return asdict(self)


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


def sort_time_series_files(files: Iterable[Path]) -> list[Path]:
    return sorted(files, key=_time_series_sort_key)


def sample_sequence_indices(
    total_count: int,
    sample_count: int,
    required_indices: Iterable[int] = (),
) -> list[int]:
    if total_count <= 0:
        raise ValueError("Cannot sample an empty sequence.")
    if sample_count <= 0:
        raise ValueError("Sample count must be positive.")

    target_count = min(total_count, sample_count)
    selected = {index for index in required_indices if 0 <= index < total_count}
    if len(selected) > target_count:
        raise ValueError("Required indices exceed the sample count.")

    if target_count == total_count:
        return list(range(total_count))

    denominator = max(target_count - 1, 1)
    ideal_positions = [index * (total_count - 1) / denominator for index in range(target_count)]
    for position in ideal_positions:
        if len(selected) >= target_count:
            break
        for candidate in sorted(range(total_count), key=lambda index: (abs(index - position), index)):
            if candidate not in selected:
                selected.add(candidate)
                break

    if len(selected) < target_count:
        for candidate in range(total_count):
            if candidate not in selected:
                selected.add(candidate)
            if len(selected) >= target_count:
                break
    return sorted(selected)


def lookup_surface_indices(surface_original_ids: Iterable[int], requested_original_ids: Iterable[int]) -> list[int]:
    lookup = {int(original_id): index for index, original_id in enumerate(surface_original_ids)}
    resolved: list[int] = []
    for original_id in requested_original_ids:
        key = int(original_id)
        if key not in lookup:
            raise KeyError(f"Original point id {key} was not found in the source surface.")
        resolved.append(lookup[key])
    return resolved


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


def pressure_to_mmhg(value: float, divisor: float) -> float:
    if divisor == 0:
        raise ValueError("Pressure divisor must be non-zero.")
    return value / divisor


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
    animation: dict[str, object] | None = None,
    pressure_presentation: dict[str, object] | None = None,
    glb_path: str | None = None,
    usdz_path: str | None = None,
    download_glb_path: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "slug": slug,
        "title": title,
        "page": f"models/{slug}/",
        "glb": glb_path or f"assets/models/{slug}/{slug}.glb",
        "usdz": usdz_path or f"assets/models/{slug}/{slug}.usdz",
        "parts": parts,
        "blenderParameters": config.blender_payload(),
    }
    if download_glb_path is not None:
        entry["downloadGlb"] = download_glb_path
    if animation is not None:
        entry["animation"] = animation
    if pressure_presentation is not None:
        entry["pressurePresentation"] = pressure_presentation
    return entry


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


def _time_series_sort_key(path: Path) -> tuple[str, int, str]:
    match = FRAME_NUMBER_PATTERN.search(path.stem)
    if match is None:
        return (path.stem, -1, path.name)
    prefix = path.stem[:match.start()]
    return (prefix, int(match.group(1)), path.name)
