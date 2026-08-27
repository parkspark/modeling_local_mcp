"""Headless Blender bridge with constrained prompt-based post-processing."""

import argparse
import json
import os
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--postprocess-plan")
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(script_args)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


TARGET_ALIASES = {
    "lens": ("lens", "glass", "렌즈", "안경알"),
    "frame": ("frame", "rim", "temple", "arm", "프레임", "안경테"),
}


def mesh_objects() -> list:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def normalized(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def matching_objects(target: str) -> list:
    objects = mesh_objects()
    if target == "all":
        return objects
    aliases = tuple(normalized(alias) for alias in TARGET_ALIASES.get(target, (target,)))
    matched = []
    for obj in objects:
        searchable = [normalized(obj.name)]
        searchable.extend(
            normalized(slot.material.name)
            for slot in obj.material_slots
            if slot.material is not None
        )
        if any(alias in value for alias in aliases for value in searchable):
            matched.append(obj)
    return matched


def materials_for(target: str) -> list:
    objects = matching_objects(target)
    materials = []
    seen = set()
    for obj in objects:
        if not obj.material_slots:
            material = bpy.data.materials.new(name=f"Postprocess_{target}")
            material.use_nodes = True
            obj.data.materials.append(material)
        for slot in obj.material_slots:
            material = slot.material
            if material is not None and material.name not in seen:
                materials.append(material)
                seen.add(material.name)
    return materials


def principled_node(material):
    material.use_nodes = True
    return next(
        (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
        None,
    )


def apply_material(operation: dict) -> int:
    target = operation.get("target", "all")
    materials = materials_for(target)
    if not materials:
        print(
            f"[POSTPROCESS][WARN] Target '{target}' did not match an object or material name; "
            "the material operation was skipped."
        )
        return 0

    for material in materials:
        node = principled_node(material)
        if node is None:
            print(f"[POSTPROCESS][WARN] Material '{material.name}' has no Principled BSDF node.")
            continue
        if "base_color" in operation:
            color = tuple(operation["base_color"])
            node.inputs["Base Color"].default_value = color
            material.diffuse_color = color
        if "roughness" in operation:
            node.inputs["Roughness"].default_value = float(operation["roughness"])
        if "metallic" in operation:
            node.inputs["Metallic"].default_value = float(operation["metallic"])
        if "alpha" in operation:
            alpha = min(1.0, max(0.0, float(operation["alpha"])))
            node.inputs["Alpha"].default_value = alpha
            base_color = list(node.inputs["Base Color"].default_value)
            base_color[3] = alpha
            node.inputs["Base Color"].default_value = base_color
            diffuse = list(material.diffuse_color)
            diffuse[3] = alpha
            material.diffuse_color = diffuse
            if hasattr(material, "surface_render_method"):
                material.surface_render_method = "DITHERED"
            elif hasattr(material, "blend_method"):
                material.blend_method = "BLEND"
    print(f"[POSTPROCESS] Material operation applied to {len(materials)} material(s), target={target}")
    return len(materials)


def apply_object_operation(operation: dict) -> int:
    operation_type = operation.get("type")
    target = operation.get("target", "all")
    objects = matching_objects(target)
    if not objects:
        print(f"[POSTPROCESS][WARN] Target '{target}' did not match; {operation_type} was skipped.")
        return 0

    for obj in objects:
        if operation_type == "transform":
            scale = max(0.01, float(operation.get("scale", 1.0)))
            obj.scale = tuple(component * scale for component in obj.scale)
        elif operation_type == "smooth":
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
        elif operation_type == "bevel":
            largest_dimension = max(float(value) for value in obj.dimensions)
            modifier = obj.modifiers.new(name="Prompt Bevel", type="BEVEL")
            modifier.width = largest_dimension * float(operation.get("width_ratio", 0.005))
            modifier.segments = int(operation.get("segments", 3))
        elif operation_type == "decimate":
            modifier = obj.modifiers.new(name="Prompt Decimate", type="DECIMATE")
            modifier.ratio = min(1.0, max(0.01, float(operation.get("ratio", 1.0))))
    print(f"[POSTPROCESS] {operation_type} applied to {len(objects)} object(s), target={target}")
    return len(objects)


def apply_postprocess(plan_path: Path | None) -> int:
    if plan_path is None:
        print("[POSTPROCESS] No plan supplied; conversion only.")
        return 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    operations = plan.get("operations", [])
    if not operations:
        print("[POSTPROCESS] Plan contains no recognized operations.")
        return 0
    applied = 0
    for operation in operations:
        if operation.get("type") == "material":
            applied += apply_material(operation)
        else:
            applied += apply_object_operation(operation)
    print(f"[POSTPROCESS] Completed {len(operations)} operation(s); affected entries={applied}")
    return applied


def export_updated_glb(input_path: Path) -> None:
    temporary_path = input_path.with_name(f"{input_path.stem}.postprocessed.glb")
    bpy.ops.export_scene.gltf(
        filepath=str(temporary_path),
        export_format="GLB",
        export_apply=True,
    )
    os.replace(temporary_path, input_path)
    print(f"[POSTPROCESS] Updated GLB: {input_path}")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    blend_path = Path(args.blend).resolve()
    fbx_path = Path(args.fbx).resolve()
    plan_path = Path(args.postprocess_plan).resolve() if args.postprocess_plan else None
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    fbx_path.parent.mkdir(parents=True, exist_ok=True)

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(input_path))
    applied = apply_postprocess(plan_path)

    for obj in bpy.context.scene.objects:
        obj.select_set(obj.type == "MESH")

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_path),
        use_selection=False,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        path_mode="COPY",
        embed_textures=True,
        add_leaf_bones=False,
        bake_anim=False,
    )
    if applied:
        export_updated_glb(input_path)
    print(f"Saved editable scene: {blend_path}")
    print(f"Saved engine export: {fbx_path}")


if __name__ == "__main__":
    main()
