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


def apply_scene_transform(objects: list[bpy.types.Object], config: dict[str, object]) -> None:
    minimum, maximum = scene_bounds(objects)
    center = (minimum + maximum) * 0.5
    longest = max(maximum.x - minimum.x, maximum.y - minimum.y, maximum.z - minimum.z)
    fit_meters = float(config["fit_meters"])
    scale = fit_meters / longest if longest else 1.0
    rotation_deg = [float(value) for value in config["rotation_deg"]]
    rotation = Euler(tuple(math.radians(value) for value in rotation_deg), "XYZ")

    for obj in objects:
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


def export_assets(config_path: Path) -> None:
    config = json.loads(config_path.read_text())
    cleanup_scene()

    objects = []
    for item in config["inputs"]:
        source = Path(item["ply"])
        bpy.ops.wm.ply_import(filepath=str(source))
        obj = bpy.context.object
        obj.name = item["part_name"]
        if config["color_mode"] == "vertex":
            make_vertex_color_material(obj, f"{obj.name}_vertex")
        else:
            make_flat_material(obj, f"{obj.name}_flat", item["color"])
        objects.append(obj)

    apply_scene_transform(objects, config)
    apply_decimation(objects, float(config["decimate_ratio"]))

    output_glb = Path(config["output_glb"])
    output_usdz = Path(config["output_usdz"])
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
