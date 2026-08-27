"""Create a tiny named GLB for Blender bridge integration checks."""

import argparse
import sys

import bpy


parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
script_arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
arguments = parser.parse_args(script_arguments)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1.0)
cube = bpy.context.object
cube.name = "Lens_Test"
material = bpy.data.materials.new(name="LensMaterial")
material.use_nodes = True
cube.data.materials.append(material)
bpy.ops.export_scene.gltf(filepath=arguments.output, export_format="GLB")
