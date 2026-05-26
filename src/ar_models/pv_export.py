from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy

try:
    from .core import lookup_surface_indices
except ImportError:
    from ar_models.core import lookup_surface_indices


FRAME_NUMBER_PATTERN = re.compile(r"(\d+)(?!.*\d)")
LOW_COLOR = np.array([0.231373, 0.298039, 0.752941], dtype=np.float64)
MID_COLOR = np.array([0.865003, 0.865003, 0.865003], dtype=np.float64)
HIGH_COLOR = np.array([0.705882, 0.0156863, 0.14902], dtype=np.float64)


def export_to_ply(config_path: Path) -> None:
    config = json.loads(config_path.read_text())
    mode = config.get("mode", "static")
    if mode == "animated":
        export_animated(config)
        return
    export_static(config)


def export_static(config: dict[str, object]) -> None:
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    from paraview.simple import ExtractSurface, SaveData, XMLPolyDataReader, XMLUnstructuredGridReader

    for item in config["inputs"]:
        input_path = Path(item["input"])
        output_path = output_dir / item["part_name"]
        output_path = output_path.with_suffix(".ply")
        suffix = input_path.suffix.lower()

        if suffix == ".vtp":
            reader = XMLPolyDataReader(FileName=[str(input_path)])
            proxy = reader
        elif suffix == ".vtu":
            reader = XMLUnstructuredGridReader(FileName=[str(input_path)])
            proxy = ExtractSurface(Input=reader)
        else:
            raise ValueError(f"Unsupported VTK input type: {input_path}")

        SaveData(str(output_path), proxy=proxy)
        print(f"wrote {output_path}")


def export_animated(config: dict[str, object]) -> None:
    input_paths = [Path(raw_path) for raw_path in config["inputs"]]
    if not input_paths:
        raise ValueError("Animated export requires at least one input file.")
    if any(path.suffix.lower() != ".vtu" for path in input_paths):
        raise ValueError("Animated export currently requires .vtu inputs.")

    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    pressure_array = str(config["pressure_array"])
    pressure_divisor = float(config["pressure_divisor"])
    frame_count = int(config["frame_count"])
    representative_strategy = str(config["representative_frame"])
    decimate_ratio = float(config["decimate_ratio"])
    metadata_path = Path(config["metadata_path"])
    color_data_path = Path(config["color_data_path"])

    ordered_inputs = sorted(input_paths, key=time_series_sort_key)
    frame_scan = [scan_frame(path, pressure_array, pressure_divisor) for path in ordered_inputs]
    peak_index = max(range(len(frame_scan)), key=lambda index: frame_scan[index]["maxPressureRaw"])
    global_min_raw = min(frame["minPressureRaw"] for frame in frame_scan)
    global_max_raw = max(frame["maxPressureRaw"] for frame in frame_scan)
    actual_range_mmhg = [global_min_raw / pressure_divisor, global_max_raw / pressure_divisor]
    global_range_mmhg = [0.0, max(actual_range_mmhg[1], 0.0)]

    if representative_strategy != "peak-max-pressure":
        raise ValueError(f"Unsupported representative frame strategy: {representative_strategy}")
    representative_source_index = peak_index

    sampled_indices = sample_sequence_indices(
        len(ordered_inputs),
        frame_count,
        required_indices=[0, representative_source_index, len(ordered_inputs) - 1],
    )
    representative_surface = load_surface_polydata(ordered_inputs[representative_source_index])
    base_surface = decimate_surface(representative_surface, decimate_ratio)
    original_point_ids = extract_original_point_ids(base_surface)

    sampled_frames = []
    color_frames: list[np.ndarray] = []
    representative_sampled_index = None
    for sampled_index, source_index in enumerate(sampled_indices):
        source_path = ordered_inputs[source_index]
        source_surface = load_surface_polydata(source_path)
        source_surface_indices = source_indices_for_ids(source_surface, original_point_ids)
        frame_colors = pressure_colors_for_ids(
            source_surface,
            source_surface_indices,
            pressure_array,
            global_range_mmhg,
            pressure_divisor,
        )
        frame_poly = build_frame_polydata(
            base_surface,
            coordinates_for_indices(source_surface, source_surface_indices),
            colors=frame_colors if source_index == representative_source_index else None,
        )
        frame_path = (output_dir / f"frame-{sampled_index:03d}.ply").resolve()
        write_polydata_ply(frame_poly, frame_path)
        color_frames.append(frame_colors)
        cycle_percent = 0.0
        if len(sampled_indices) > 1:
            cycle_percent = 100.0 * sampled_index / (len(sampled_indices) - 1)
        sampled_frames.append(
            {
                "sampledIndex": sampled_index,
                "sourceIndex": source_index,
                "sourceName": source_path.name,
                "sourceStep": frame_scan[source_index]["sourceStep"],
                "cyclePercent": round(cycle_percent, 2),
                "label": f"{round(cycle_percent):.0f}% of cycle",
                "minPressureRaw": frame_scan[source_index]["minPressureRaw"],
                "maxPressureRaw": frame_scan[source_index]["maxPressureRaw"],
                "minPressureMmHg": round(frame_scan[source_index]["minPressureMmHg"], 4),
                "maxPressureMmHg": round(frame_scan[source_index]["maxPressureMmHg"], 4),
                "ply": str(frame_path),
            }
        )
        if source_index == representative_source_index:
            representative_sampled_index = sampled_index
        print(f"wrote {frame_path}")

    if representative_sampled_index is None:
        raise RuntimeError("Representative frame was not included in the sampled animation set.")

    color_data_path.parent.mkdir(parents=True, exist_ok=True)
    color_buffer = np.stack(color_frames, axis=0).astype(np.uint8, copy=False)
    color_data_path.write_bytes(color_buffer.tobytes())

    summary = {
        "mode": "animated",
        "partName": "pressure-surface",
        "frameSourceCount": len(ordered_inputs),
        "sampledFrames": sampled_frames,
        "representativeFrame": {
            "sampledIndex": representative_sampled_index,
            "sourceIndex": representative_source_index,
            "sourceName": ordered_inputs[representative_source_index].name,
            "sourceStep": frame_scan[representative_source_index]["sourceStep"],
            "ply": sampled_frames[representative_sampled_index]["ply"],
        },
        "pressureArray": pressure_array,
        "pressureDivisor": pressure_divisor,
        "globalPressureRangeRaw": [global_min_raw, global_max_raw],
        "globalPressureRangeMmHg": [round(global_range_mmhg[0], 4), round(global_range_mmhg[1], 4)],
        "colorRangeMmHg": [round(global_range_mmhg[0], 4), round(global_range_mmhg[1], 4)],
        "actualPressureRangeMmHg": [round(actual_range_mmhg[0], 4), round(actual_range_mmhg[1], 4)],
        "colorDataPath": str(color_data_path.resolve()),
        "surface": {
            "vertexCount": int(base_surface.GetNumberOfPoints()),
            "faceCount": int(base_surface.GetNumberOfPolys()),
        },
    }
    metadata_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {metadata_path}")


def scan_frame(path: Path, pressure_array: str, pressure_divisor: float) -> dict[str, float | int | str]:
    surface = load_surface_polydata(path)
    pressure_values = point_array(surface, pressure_array)
    return {
        "sourceName": path.name,
        "sourceStep": source_step_from_path(path),
        "minPressureRaw": float(pressure_values.min()),
        "maxPressureRaw": float(pressure_values.max()),
        "minPressureMmHg": float(pressure_values.min() / pressure_divisor),
        "maxPressureMmHg": float(pressure_values.max() / pressure_divisor),
    }


def load_surface_polydata(path: Path) -> vtk.vtkPolyData:
    reader = vtk.vtkXMLUnstructuredGridReader()
    reader.SetFileName(str(path))
    reader.Update()

    surface = vtk.vtkDataSetSurfaceFilter()
    surface.SetInputConnection(reader.GetOutputPort())
    surface.PassThroughPointIdsOn()
    surface.PassThroughCellIdsOn()
    surface.Update()

    triangles = vtk.vtkTriangleFilter()
    triangles.SetInputConnection(surface.GetOutputPort())
    triangles.Update()

    polydata = vtk.vtkPolyData()
    polydata.DeepCopy(triangles.GetOutput())
    return polydata


def decimate_surface(polydata: vtk.vtkPolyData, keep_ratio: float) -> vtk.vtkPolyData:
    if keep_ratio >= 0.999:
        result = vtk.vtkPolyData()
        result.DeepCopy(polydata)
        return result

    decimator = vtk.vtkDecimatePro()
    decimator.SetInputData(polydata)
    decimator.SetTargetReduction(1.0 - keep_ratio)
    decimator.PreserveTopologyOn()
    decimator.Update()

    result = vtk.vtkPolyData()
    result.DeepCopy(decimator.GetOutput())
    return result


def extract_original_point_ids(polydata: vtk.vtkPolyData) -> np.ndarray:
    array = polydata.GetPointData().GetArray("vtkOriginalPointIds")
    if array is None:
        raise RuntimeError("Expected vtkOriginalPointIds on the representative surface.")
    return vtk_to_numpy(array).astype(np.int64, copy=False)


def source_indices_for_ids(polydata: vtk.vtkPolyData, point_ids: np.ndarray) -> np.ndarray:
    surface_point_ids = extract_original_point_ids(polydata)
    return np.asarray(lookup_surface_indices(surface_point_ids, point_ids), dtype=np.int64)


def coordinates_for_indices(polydata: vtk.vtkPolyData, point_indices: np.ndarray) -> np.ndarray:
    points = vtk_to_numpy(polydata.GetPoints().GetData())
    displaced = points[point_indices].copy()
    displacement_array = polydata.GetPointData().GetArray("Displacement")
    if displacement_array is not None:
        displaced += vtk_to_numpy(displacement_array)[point_indices]
    return displaced


def pressure_colors_for_ids(
    polydata: vtk.vtkPolyData,
    point_indices: np.ndarray,
    pressure_array: str,
    pressure_range_mmhg: list[float],
    pressure_divisor: float,
) -> np.ndarray:
    pressure_values = point_array(polydata, pressure_array)[point_indices] / pressure_divisor
    return pressure_to_rgb(pressure_values, pressure_range_mmhg)


def point_array(polydata: vtk.vtkPolyData, name: str) -> np.ndarray:
    array = polydata.GetPointData().GetArray(name)
    if array is None:
        raise RuntimeError(f"Expected point-data array '{name}' on the surface.")
    return vtk_to_numpy(array)


def pressure_to_rgb(values_mmhg: np.ndarray, pressure_range_mmhg: list[float]) -> np.ndarray:
    minimum, maximum = pressure_range_mmhg
    if maximum <= minimum:
        normalized = np.zeros_like(values_mmhg, dtype=np.float64)
    else:
        normalized = np.clip((values_mmhg - minimum) / (maximum - minimum), 0.0, 1.0)
    rgb = np.empty((len(values_mmhg), 3), dtype=np.float64)
    low_mask = normalized <= 0.5
    high_mask = ~low_mask
    if np.any(low_mask):
        t = (normalized[low_mask] / 0.5).reshape(-1, 1)
        rgb[low_mask] = LOW_COLOR + (MID_COLOR - LOW_COLOR) * t
    if np.any(high_mask):
        t = ((normalized[high_mask] - 0.5) / 0.5).reshape(-1, 1)
        rgb[high_mask] = MID_COLOR + (HIGH_COLOR - MID_COLOR) * t
    return np.clip(np.round(rgb * 255.0), 0, 255).astype(np.uint8)


def build_frame_polydata(
    base_surface: vtk.vtkPolyData,
    coordinates: np.ndarray,
    colors: np.ndarray | None,
) -> vtk.vtkPolyData:
    polydata = vtk.vtkPolyData()
    polydata.SetPolys(base_surface.GetPolys())

    points = vtk.vtkPoints()
    vtk_points = numpy_to_vtk(coordinates.astype(np.float32), deep=True)
    vtk_points.SetNumberOfComponents(3)
    points.SetData(vtk_points)
    polydata.SetPoints(points)

    if colors is not None:
        color_array = numpy_to_vtk(colors, deep=True, array_type=vtk.VTK_UNSIGNED_CHAR)
        color_array.SetName("RGB")
        color_array.SetNumberOfComponents(3)
        polydata.GetPointData().SetScalars(color_array)
    return polydata


def write_polydata_ply(polydata: vtk.vtkPolyData, output_path: Path) -> None:
    writer = vtk.vtkPLYWriter()
    writer.SetFileName(str(output_path))
    writer.SetInputData(polydata)
    writer.SetFileTypeToBinary()
    if polydata.GetPointData().GetScalars() is not None:
        writer.SetArrayName(polydata.GetPointData().GetScalars().GetName())
    writer.Write()


def sample_sequence_indices(total_count: int, sample_count: int, required_indices: list[int]) -> list[int]:
    if total_count <= 0:
        raise ValueError("Cannot sample an empty sequence.")
    target_count = min(total_count, sample_count)
    selected = {index for index in required_indices if 0 <= index < total_count}
    if len(selected) > target_count:
        raise ValueError("Required indices exceed the sample count.")

    if target_count == total_count:
        return list(range(total_count))

    denominator = max(target_count - 1, 1)
    for step in range(target_count):
        position = step * (total_count - 1) / denominator
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


def source_step_from_path(path: Path) -> int:
    match = FRAME_NUMBER_PATTERN.search(path.stem)
    if match is None:
        return -1
    return int(match.group(1))


def time_series_sort_key(path: Path) -> tuple[str, int, str]:
    match = FRAME_NUMBER_PATTERN.search(path.stem)
    if match is None:
        return (path.stem, -1, path.name)
    return (path.stem[:match.start()], int(match.group(1)), path.name)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: pv_export.py <config.json>")
    export_to_ply(Path(sys.argv[1]).resolve())
