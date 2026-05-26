from __future__ import annotations

import json
import re
import struct
from pathlib import Path


FRAME_NAME_PATTERN = re.compile(r"Frame_(\d+)$")


def embed_animated_pressure_colors(glb_path: Path, pv_summary: dict[str, object]) -> None:
    payload, binary = read_glb(glb_path)
    mesh = payload["meshes"][0]
    primitive = mesh["primitives"][0]
    targets = primitive.get("targets", [])
    if not targets:
        raise ValueError(f"{glb_path.name} does not contain morph targets.")

    sampled_frames = pv_summary["sampledFrames"]
    representative_frame = pv_summary["representativeFrame"]
    surface = pv_summary["surface"]
    color_data_path = Path(pv_summary["colorDataPath"])
    vertex_count = int(surface["vertexCount"])
    representative_index = int(representative_frame["sampledIndex"])

    color_bytes = color_data_path.read_bytes()
    expected_bytes = len(sampled_frames) * vertex_count * 3
    if len(color_bytes) != expected_bytes:
        raise ValueError(
            f"Pressure color payload for {glb_path.name} has {len(color_bytes)} bytes, expected {expected_bytes}."
        )

    frame_stride = vertex_count * 3
    base_offset = representative_index * frame_stride
    base_colors = memoryview(color_bytes)[base_offset : base_offset + frame_stride]

    target_names = list(mesh.get("extras", {}).get("targetNames", []))
    target_frame_indices = resolve_target_frame_indices(
        target_names=target_names,
        target_count=len(targets),
        sampled_frame_count=len(sampled_frames),
        representative_index=representative_index,
    )

    buffer = bytearray(binary)
    accessors = payload["accessors"]
    buffer_views = payload["bufferViews"]

    for target, frame_index in zip(targets, target_frame_indices):
        frame_offset = frame_index * frame_stride
        frame_colors = memoryview(color_bytes)[frame_offset : frame_offset + frame_stride]
        color_delta_bytes = build_color_delta_bytes(frame_colors, base_colors)
        byte_offset = align4(len(buffer))
        if byte_offset > len(buffer):
            buffer.extend(b"\x00" * (byte_offset - len(buffer)))
        buffer.extend(color_delta_bytes)

        buffer_view_index = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": byte_offset,
                "byteLength": len(color_delta_bytes),
                "target": 34962,
            }
        )
        accessor_index = len(accessors)
        accessors.append(
            {
                "bufferView": buffer_view_index,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC3",
            }
        )
        target["COLOR_0"] = accessor_index

    payload["buffers"][0]["byteLength"] = len(buffer)
    write_glb(glb_path, payload, bytes(buffer))


def build_color_delta_bytes(frame_colors: memoryview, base_colors: memoryview) -> bytes:
    if len(frame_colors) != len(base_colors):
        raise ValueError("Frame and base color buffers must have the same size.")
    if len(frame_colors) % 3 != 0:
        raise ValueError("Expected RGB color buffers.")

    delta = bytearray((len(frame_colors) // 3) * 12)
    write_offset = 0
    for byte_offset in range(0, len(frame_colors), 3):
        struct.pack_into(
            "<3f",
            delta,
            write_offset,
            frame_colors[byte_offset] / 255.0 - base_colors[byte_offset] / 255.0,
            frame_colors[byte_offset + 1] / 255.0 - base_colors[byte_offset + 1] / 255.0,
            frame_colors[byte_offset + 2] / 255.0 - base_colors[byte_offset + 2] / 255.0,
        )
        write_offset += 12
    return bytes(delta)


def resolve_target_frame_indices(
    *,
    target_names: list[str],
    target_count: int,
    sampled_frame_count: int,
    representative_index: int,
) -> list[int]:
    if target_names:
        if len(target_names) != target_count:
            raise ValueError("GLB targetNames count does not match morph target count.")
        resolved = []
        for name in target_names:
            match = FRAME_NAME_PATTERN.fullmatch(name)
            if match is None:
                raise ValueError(f"Unexpected morph target name: {name}")
            resolved.append(int(match.group(1)))
        return resolved

    return [index for index in range(sampled_frame_count) if index != representative_index]


def read_glb(path: Path) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    magic, version, _ = struct.unpack_from("<4sII", payload, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError(f"{path} is not a GLB 2.0 file.")

    json_length, json_type = struct.unpack_from("<I4s", payload, 12)
    if json_type != b"JSON":
        raise ValueError(f"{path} is missing a JSON chunk.")
    json_start = 20
    json_end = json_start + json_length
    document = json.loads(payload[json_start:json_end].decode("utf-8"))

    if json_end + 8 > len(payload):
        return document, b""
    bin_length, bin_type = struct.unpack_from("<I4s", payload, json_end)
    if bin_type != b"BIN\x00":
        raise ValueError(f"{path} has an unexpected binary chunk type: {bin_type!r}")
    bin_start = json_end + 8
    return document, payload[bin_start : bin_start + bin_length]


def write_glb(path: Path, document: dict[str, object], binary_chunk: bytes) -> None:
    json_bytes = json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    binary_chunk += b"\x00" * ((4 - len(binary_chunk) % 4) % 4)
    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary_chunk)

    with path.open("wb") as handle:
        handle.write(struct.pack("<4sII", b"glTF", 2, total_length))
        handle.write(struct.pack("<I4s", len(json_bytes), b"JSON"))
        handle.write(json_bytes)
        handle.write(struct.pack("<I4s", len(binary_chunk), b"BIN\x00"))
        handle.write(binary_chunk)


def align4(value: int) -> int:
    return (value + 3) & ~3
