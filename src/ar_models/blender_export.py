from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector


def hex_to_rgba(value: str) -> tuple[float, float, float, float]:
    value = value.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
        1.0,
    )


def cleanup_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for _ in range(3):
        bpy.ops.outliner.orphans_purge()


def make_vertex_color_material(obj: bpy.types.Object, name: str) -> None:
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    attribute = nodes.new(type="ShaderNodeAttribute")
    attribute.attribute_name = "Col"
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    output = nodes.new(type="ShaderNodeOutputMaterial")

    links.new(attribute.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    obj.data.materials.clear()
    obj.data.materials.append(material)


def make_flat_material(obj: bpy.types.Object, name: str, color: str) -> None:
    material = bpy.data.materials.new(name=name)
    material.diffuse_color = hex_to_rgba(color)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = hex_to_rgba(color)
    obj.data.materials.clear()
    obj.data.materials.append(material)


def object_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_corner = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    max_corner = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return min_corner, max_corner


def scene_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    mins = []
    maxs = []
    for obj in objects:
        minimum, maximum = object_bounds(obj)
        mins.append(minimum)
        maxs.append(maximum)
    return (
        Vector((min(v.x for v in mins), min(v.y for v in mins), min(v.z for v in mins))),
        Vector((max(v.x for v in maxs), max(v.y for v in maxs), max(v.z for v in maxs))),
    )


def transform_values(
    objects: list[bpy.types.Object],
    config: dict[str, object],
) -> tuple[Vector, float, Euler]:
    minimum, maximum = scene_bounds(objects)
    center = (minimum + maximum) * 0.5
    longest = max(maximum.x - minimum.x, maximum.y - minimum.y, maximum.z - minimum.z)
    fit_meters = float(config["fit_meters"])
    scale = fit_meters / longest if longest else 1.0
    rotation_deg = [float(value) for value in config["rotation_deg"]]
    rotation = Euler(tuple(math.radians(value) for value in rotation_deg), "XYZ")
    return center, scale, rotation


def apply_scene_transform(
    obj: bpy.types.Object,
    config: dict[str, object],
    center: Vector,
    scale: float,
    rotation: Euler,
) -> None:
    if bool(config["centered"]):
        obj.location = (obj.location - center) * scale
    else:
        obj.location = obj.location * scale
    obj.scale = tuple(component * scale for component in obj.scale)
    obj.rotation_euler = rotation
    if bool(config["shade_smooth"]):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()


def apply_decimation(objects: list[bpy.types.Object], ratio: float) -> None:
    if ratio >= 0.999:
        return
    for obj in objects:
        modifier = obj.modifiers.new(name="ARDecimate", type="DECIMATE")
        modifier.ratio = ratio
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def import_ply(path: Path, name: str) -> bpy.types.Object:
    bpy.ops.wm.ply_import(filepath=str(path))
    obj = bpy.context.object
    obj.name = name
    return obj


def export_assets(config_path: Path) -> None:
    config = json.loads(config_path.read_text())
    cleanup_scene()
    mode = config.get("mode", "static")
    if mode == "animated":
        export_animated_assets(config)
        return
    export_static_assets(config)


def export_static_assets(config: dict[str, object]) -> None:
    objects = []
    for item in config["inputs"]:
        source = Path(item["ply"])
        obj = import_ply(source, str(item["part_name"]))
        if config["color_mode"] == "vertex":
            make_vertex_color_material(obj, f"{obj.name}_vertex")
        else:
            make_flat_material(obj, f"{obj.name}_flat", str(item["color"]))
        objects.append(obj)

    center, scale, rotation = transform_values(objects, config)
    for obj in objects:
        apply_scene_transform(obj, config, center, scale, rotation)
    apply_decimation(objects, float(config["decimate_ratio"]))
    export_selection(
        output_glb=Path(config["output_glb"]),
        output_usdz=Path(config["output_usdz"]),
    )


def export_animated_assets(config: dict[str, object]) -> None:
    representative_ply = Path(config["representative_ply"])
    frame_plys = [Path(raw_path) for raw_path in config["frame_plys"]]
    representative_frame_index = int(config["representative_frame_index"])
    fps = int(config["fps"])

    base_object = import_ply(representative_ply, "pressure_surface")
    make_vertex_color_material(base_object, "pressure_surface_vertex")

    imported_frames = [base_object]
    shape_sources: list[tuple[int, bpy.types.Object]] = []
    for frame_index, frame_path in enumerate(frame_plys):
        if frame_index == representative_frame_index:
            continue
        frame_object = import_ply(frame_path, f"Frame_{frame_index:03d}")
        shape_sources.append((frame_index, frame_object))
        imported_frames.append(frame_object)

    center, scale, rotation = transform_values(imported_frames, config)
    join_shape_keys(base_object, shape_sources)
    for _, frame_object in shape_sources:
        bpy.data.objects.remove(frame_object, do_unlink=True)

    apply_scene_transform(base_object, config, center, scale, rotation)
    animate_shape_keys(base_object, len(frame_plys), fps, representative_frame_index)

    output_glb = Path(config["output_glb"])
    output_download_glb = Path(config["output_download_glb"])
    output_usdz = Path(config["output_usdz"])
    output_glb.parent.mkdir(parents=True, exist_ok=True)

    select_only(base_object)
    bpy.context.scene.frame_set(1)
    bpy.ops.export_scene.gltf(
        filepath=str(output_glb),
        export_format="GLB",
        export_animations=True,
    )
    bpy.context.scene.frame_set(representative_frame_index + 1)
    bpy.ops.export_scene.gltf(
        filepath=str(output_download_glb),
        export_format="GLB",
        export_animations=False,
    )
    bpy.ops.wm.usd_export(filepath=str(output_usdz), selected_objects_only=False)
    print(f"wrote {output_glb}")
    print(f"wrote {output_download_glb}")
    print(f"wrote {output_usdz}")


def join_shape_keys(base_object: bpy.types.Object, shape_sources: list[tuple[int, bpy.types.Object]]) -> None:
    if not shape_sources:
        return
    bpy.ops.object.select_all(action="DESELECT")
    base_object.select_set(True)
    for _, source_object in shape_sources:
        source_object.select_set(True)
    bpy.context.view_layer.objects.active = base_object
    bpy.ops.object.join_shapes()


def animate_shape_keys(
    base_object: bpy.types.Object,
    frame_count: int,
    fps: int,
    representative_frame_index: int,
) -> None:
    shape_keys = base_object.data.shape_keys
    if shape_keys is None:
        return

    shape_keys.animation_data_create()
    action = bpy.data.actions.new(name=f"{base_object.name}_Action")
    shape_keys.animation_data.action = action

    bpy.context.scene.render.fps = fps
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = frame_count - 1
    bpy.context.scene.frame_current = 0

    key_blocks = {key_block.name: key_block for key_block in shape_keys.key_blocks if key_block.name != "Basis"}
    frame_key_names = {
        frame_index: f"Frame_{frame_index:03d}"
        for frame_index in range(frame_count)
        if frame_index != representative_frame_index
    }
    for key_block in key_blocks.values():
        key_block.value = 0.0

    for frame_index, key_name in frame_key_names.items():
        key_block = key_blocks[key_name]
        for timeline_index in range(frame_count):
            key_block.value = 1.0 if timeline_index == frame_index else 0.0
            key_block.keyframe_insert(data_path="value", frame=timeline_index)

    for key_block in key_blocks.values():
        key_block.value = 0.0


def select_only(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def export_selection(output_glb: Path, output_usdz: Path) -> None:
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB")
    bpy.ops.wm.usd_export(filepath=str(output_usdz), selected_objects_only=False)
    print(f"wrote {output_glb}")
    print(f"wrote {output_usdz}")


def main() -> None:
    try:
        separator = sys.argv.index("--")
    except ValueError as exc:
        raise SystemExit("Expected Blender args after '--'.") from exc
    config_path = Path(sys.argv[separator + 1]).resolve()
    export_assets(config_path)


if __name__ == "__main__":
    main()
