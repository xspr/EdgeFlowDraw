bl_info = {
	"name": "EdgeFlowDraw Tool",
	"author": "David Boudreau",
	"version": (1, 0, 0),
	"blender": (5, 1, 0),
	"description": "Draw a path of quads; LMB to confirm, RMB undo last, MMB orbits",
}

import bpy
from .edgeFlowDraw import DrawByQuadModalOp

def register():
    bpy.utils.register_class(DrawByQuadModalOp)
    
def unregister():
    bpy.utils.unregister_class(DrawByQuadModalOp)
