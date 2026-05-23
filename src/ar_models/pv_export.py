from __future__ import annotations

import json
import sys
from pathlib import Path

from paraview.simple import ExtractSurface, SaveData, XMLPolyDataReader, XMLUnstructuredGridReader


def export_to_ply(config_path: Path) -> None:
    config = json.loads(config_path.read_text())
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: pv_export.py <config.json>")
    export_to_ply(Path(sys.argv[1]).resolve())
