from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector


IOS_BAKE_TEXTURE_SIZE = 2048


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
    material.use_backface_culling = False
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
    material.use_backface_culling = False
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = hex_to_rgba(color)
    obj.data.materials.clear()
    obj.data.materials.append(material)


def make_baked_texture_material(obj: bpy.types.Object, name: str, image: bpy.types.Image) -> None:
    material = bpy.data.materials.new(name=name)
    material.use_backface_culling = False
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    image_node = nodes.new(type="ShaderNodeTexImage")
    image_node.image = image
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    output = nodes.new(type="ShaderNodeOutputMaterial")

    links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

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
        repair_mesh_normals(obj)


def import_ply(path: Path, name: str) -> bpy.types.Object:
    bpy.ops.wm.ply_import(filepath=str(path))
    obj = bpy.context.object
    obj.name = name
    repair_mesh_normals(obj)
    return obj


def duplicate_mesh_object(source: bpy.types.Object, name: str) -> bpy.types.Object:
    duplicate = source.copy()
    duplicate.data = source.data.copy()
    duplicate.animation_data_clear()
    duplicate.name = name
    bpy.context.collection.objects.link(duplicate)
    return duplicate


def repair_mesh_normals(obj: bpy.types.Object) -> None:
    mesh = obj.data
    select_only(obj)
    if getattr(mesh, "has_custom_normals", False):
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.update()


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
    ios_object = duplicate_mesh_object(base_object, "pressure_surface_ios")
    make_vertex_color_material(base_object, "pressure_surface_vertex")
    make_vertex_color_material(ios_object, "pressure_surface_ios_vertex")

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
    apply_scene_transform(ios_object, config, center, scale, rotation)
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
        use_selection=True,
    )
    bpy.context.scene.frame_set(representative_frame_index + 1)
    bpy.ops.export_scene.gltf(
        filepath=str(output_download_glb),
        export_format="GLB",
        export_animations=False,
        use_selection=True,
    )
    bake_vertex_colors_for_ios_usdz(
        obj=ios_object,
        output_usdz=output_usdz,
        texture_size=int(config.get("ios_bake_texture_size", IOS_BAKE_TEXTURE_SIZE)),
    )
    print(f"wrote {output_glb}")
    print(f"wrote {output_download_glb}")
    print(f"wrote {output_usdz}")


def bake_vertex_colors_for_ios_usdz(
    obj: bpy.types.Object,
    output_usdz: Path,
    texture_size: int,
) -> None:
    texture_path = output_usdz.with_name(f"{output_usdz.stem}-baked-color.png")
    image = bpy.data.images.new(
        name=f"{obj.name}_ios_bake",
        width=texture_size,
        height=texture_size,
        alpha=False,
    )
    image.file_format = "PNG"
    image.filepath_raw = str(texture_path)

    bake_material = bpy.data.materials.new(name=f"{obj.name}_ios_bake")
    bake_material.use_nodes = True
    bake_nodes = bake_material.node_tree.nodes
    bake_links = bake_material.node_tree.links
    bake_nodes.clear()

    attribute = bake_nodes.new(type="ShaderNodeAttribute")
    attribute.attribute_name = "Col"
    emission = bake_nodes.new(type="ShaderNodeEmission")
    output = bake_nodes.new(type="ShaderNodeOutputMaterial")
    image_node = bake_nodes.new(type="ShaderNodeTexImage")
    image_node.image = image
    bake_nodes.active = image_node

    bake_links.new(attribute.outputs["Color"], emission.inputs["Color"])
    bake_links.new(emission.outputs["Emission"], output.inputs["Surface"])

    obj.data.materials.clear()
    obj.data.materials.append(bake_material)
    ensure_uv_map(obj)
    bake_object_emission_to_image(obj)
    image.save()

    make_baked_texture_material(obj, f"{obj.name}_ios_texture", image)
    select_only(obj)
    bpy.ops.wm.usd_export(filepath=str(output_usdz), selected_objects_only=True)

    if texture_path.exists():
        texture_path.unlink()


def ensure_uv_map(obj: bpy.types.Object) -> None:
    mesh = obj.data
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    select_only(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_object_emission_to_image(obj: bpy.types.Object) -> None:
    scene = bpy.context.scene
    previous_engine = scene.render.engine
    previous_samples = getattr(scene.cycles, "samples", 1)
    previous_margin = scene.render.bake.margin

    try:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 1
        scene.render.bake.margin = 16
        select_only(obj)
        bpy.ops.object.bake(type="EMIT")
    finally:
        scene.render.engine = previous_engine
        scene.cycles.samples = previous_samples
        scene.render.bake.margin = previous_margin


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
