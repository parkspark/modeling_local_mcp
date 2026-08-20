"""Render a quick validation preview of a GLB in headless Blender."""

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pose", action="store_true")
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(values)


def look_at(obj: bpy.types.Object, point: Vector) -> None:
    obj.rotation_euler = (point - obj.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    args = arguments()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input).resolve()
    if input_path.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(input_path))
    else:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        bpy.ops.import_scene.gltf(filepath=str(input_path))

    if args.pose:
        armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
        if not armatures:
            raise RuntimeError("--pose requires an armature")
        armature = armatures[0]
        pose_values = {
            "LeftUpperArm": (math.radians(25), 0.0, math.radians(-20)),
            "RightUpperArm": (math.radians(-25), 0.0, math.radians(20)),
            "LeftLowerArm": (math.radians(35), 0.0, 0.0),
            "RightLowerArm": (math.radians(35), 0.0, 0.0),
            "LeftUpperLeg": (math.radians(-15), 0.0, 0.0),
            "RightUpperLeg": (math.radians(15), 0.0, 0.0),
            "LeftLowerLeg": (math.radians(20), 0.0, 0.0),
        }
        for bone_name, rotation in pose_values.items():
            bone = armature.pose.bones.get(bone_name)
            if bone is None:
                continue
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = rotation
        bpy.context.view_layer.update()

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_meshes = [obj.evaluated_get(depsgraph) for obj in meshes]
    corners = [obj.matrix_world @ Vector(corner) for obj in evaluated_meshes for corner in obj.bound_box]
    low = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    high = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    center = (low + high) * 0.5
    extent = max(high.x - low.x, high.y - low.y, high.z - low.z)

    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = center + Vector((1.6, -2.2, 1.4)) * extent
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = extent * 1.55
    look_at(camera, center)
    bpy.context.scene.camera = camera

    for name, offset, energy, size in (
        ("Key", (2.0, -2.0, 3.0), 900.0, 3.0),
        ("Fill", (-2.0, -1.0, 1.5), 500.0, 2.5),
        ("Rim", (0.5, 2.0, 2.5), 700.0, 2.0),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size * extent
        light = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(light)
        light.location = center + Vector(offset) * extent
        look_at(light, center)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    scene.render.filepath = str(output)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)
    print(f"Preview saved: {output}")


if __name__ == "__main__":
    main()
