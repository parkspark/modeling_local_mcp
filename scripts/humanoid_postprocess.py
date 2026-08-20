"""Prepare a UniRig biped result for Unity Humanoid import."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--report", required=True)
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(script_args)


def children(bone: bpy.types.Bone) -> list[bpy.types.Bone]:
    return list(bone.children)


def linear_chain(start: bpy.types.Bone) -> list[bpy.types.Bone]:
    chain = [start]
    current = start
    while len(children(current)) == 1:
        current = children(current)[0]
        chain.append(current)
    return chain


def require_length(label: str, chain: list[bpy.types.Bone], minimum: int) -> None:
    if len(chain) < minimum:
        raise RuntimeError(f"{label} chain has {len(chain)} bones; expected at least {minimum}")


def side_for(bone: bpy.types.Bone) -> str:
    # Pixal3D assets face Blender -Y after GLB import, so negative X is
    # the character's anatomical right side.
    return "Right" if bone.head_local.x < 0 else "Left"


def build_humanoid_mapping(armature: bpy.types.Object) -> dict[str, str]:
    roots = [bone for bone in armature.data.bones if bone.parent is None]
    if len(roots) != 1:
        raise RuntimeError(f"expected one root bone, found {len(roots)}")

    hips = roots[0]
    root_children = children(hips)
    if len(root_children) != 3:
        raise RuntimeError(f"hips must have one spine and two legs; found {len(root_children)} children")

    spine_start = max(root_children, key=lambda bone: bone.tail_local.z)
    leg_starts = [bone for bone in root_children if bone != spine_start]
    spine_chain = linear_chain(spine_start)
    require_length("spine", spine_chain, 3)
    upper_chest = spine_chain[-1]
    chest_children = children(upper_chest)
    if len(chest_children) != 3:
        raise RuntimeError(f"upper chest must have neck and two shoulders; found {len(chest_children)}")

    neck_start = max(chest_children, key=lambda bone: bone.tail_local.z)
    shoulder_starts = [bone for bone in chest_children if bone != neck_start]
    neck_chain = linear_chain(neck_start)
    require_length("neck", neck_chain, 2)

    mapping: dict[str, str] = {
        hips.name: "Hips",
        spine_chain[0].name: "Spine",
        spine_chain[-2].name: "Chest",
        spine_chain[-1].name: "UpperChest",
        neck_chain[0].name: "Neck",
        neck_chain[1].name: "Head",
    }

    for leg_start in leg_starts:
        chain = linear_chain(leg_start)
        require_length("leg", chain, 4)
        side = side_for(leg_start)
        names = ("UpperLeg", "LowerLeg", "Foot", "Toes")
        for bone, suffix in zip(chain[:4], names, strict=True):
            mapping[bone.name] = f"{side}{suffix}"

    for shoulder_start in shoulder_starts:
        chain = linear_chain(shoulder_start)
        require_length("arm", chain, 4)
        side = side_for(shoulder_start)
        names = ("Shoulder", "UpperArm", "LowerArm", "Hand")
        for bone, suffix in zip(chain[:4], names, strict=True):
            mapping[bone.name] = f"{side}{suffix}"

        hand = chain[3]
        finger_starts = children(hand)
        if len(finger_starts) < 2:
            continue
        finger_chains = [linear_chain(start) for start in finger_starts]
        finger_chains = [finger for finger in finger_chains if len(finger) >= 3]
        if len(finger_chains) < 2:
            continue
        finger_chains.sort(key=lambda finger: abs(finger[-1].tail_local.x))
        for finger, finger_name in zip(finger_chains[:2], ("Thumb", "Middle"), strict=True):
            for bone, segment in zip(
                finger[:3], ("Proximal", "Intermediate", "Distal"), strict=True
            ):
                mapping[bone.name] = f"{side}{finger_name}{segment}"

    return mapping


def remove_debug_meshes(primary_mesh: bpy.types.Object) -> list[str]:
    removed: list[str] = []
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or obj == primary_mesh:
            continue
        has_armature = any(modifier.type == "ARMATURE" for modifier in obj.modifiers)
        if not has_armature and not obj.vertex_groups:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    return removed


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    blend_path = Path(args.blend).resolve()
    fbx_path = Path(args.fbx).resolve()
    report_path = Path(args.report).resolve()
    for path in (blend_path, fbx_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(armatures) != 1 or not meshes:
        raise RuntimeError(f"expected one armature and at least one mesh; got {len(armatures)}, {len(meshes)}")

    armature = armatures[0]
    primary_mesh = max(meshes, key=lambda obj: len(obj.data.vertices))
    mapping = build_humanoid_mapping(armature)
    removed_meshes = remove_debug_meshes(primary_mesh)

    for old_name, new_name in mapping.items():
        bone = armature.data.bones.get(old_name)
        if bone is not None:
            bone.name = new_name
        vertex_group = primary_mesh.vertex_groups.get(old_name)
        if vertex_group is not None:
            vertex_group.name = new_name

    weighted_vertices = sum(1 for vertex in primary_mesh.data.vertices if vertex.groups)
    max_influences = max((len(vertex.groups) for vertex in primary_mesh.data.vertices), default=0)
    required = {
        "Hips", "Spine", "Chest", "Neck", "Head",
        "LeftUpperArm", "LeftLowerArm", "LeftHand",
        "RightUpperArm", "RightLowerArm", "RightHand",
        "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
        "RightUpperLeg", "RightLowerLeg", "RightFoot",
    }
    final_bones = {bone.name for bone in armature.data.bones}
    missing_required = sorted(required - final_bones)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_path),
        use_selection=False,
        object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        path_mode="COPY",
        embed_textures=True,
        add_leaf_bones=False,
        bake_anim=False,
    )

    report = {
        "status": "PASS" if not missing_required and weighted_vertices == len(primary_mesh.data.vertices) else "FAIL",
        "source": str(input_path),
        "blend": str(blend_path),
        "fbx": str(fbx_path),
        "armature": armature.name,
        "bone_count": len(armature.data.bones),
        "bone_mapping": mapping,
        "missing_required_bones": missing_required,
        "mesh": primary_mesh.name,
        "vertex_count": len(primary_mesh.data.vertices),
        "weighted_vertices": weighted_vertices,
        "max_influences": max_influences,
        "removed_debug_meshes": removed_meshes,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
