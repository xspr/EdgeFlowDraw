'''
Copyright (C) 2026 David Boudreau
Created by David Boudreau
This file is part of EdgeFlowDraw.
    EdgeFlowDraw is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 3
    of the License, or (at your option) any later version.
    
    This version is distributed in the hope that it will be useful
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with this program; if not, see <https://www.gnu.org/licenses>.
'''
import bpy

from bpy_extras import view3d_utils
from mathutils import Vector, Quaternion

# EdgeFlowDraw tool allows drawing a path of quads. The main goal is to provide 3D artists
# with the ability to focus primarily on the edgeflow from the start of modelling, as opposed to
# starting with blocking out using primitives (cube/sphere for basic shapes), or the tediousness
# of point modelling (extruding vertices one-by-one). This approach provides artists something in
# between those approaches, with the main focus on defining edgeflow and silhouette first.
# Hopefully this will help avoid or make for easier/better planning of edge poles with more than
# five edges connected (which require solutions like deleting faces and knife-tooling it all again).
# F3 and select EdgeFlowDraw Tool, start drawing with mouse; can resize quads with scrollwheel.
# RMB to undo last quad. Hold MMB to orbit left/right. No zoom in/out feature for now. 

class DrawByQuadModalOp(bpy.types.Operator):
    """Draw edgeflow with mouse as a path of quads; LMB to finish each time"""
    bl_idname = "object.modal_drawbyquad_op"
    bl_label = "EdgeFlowDraw Tool"
    bl_options = {'REGISTER', 'UNDO'}
    
    mode = 'NONE' # Make a faked enum of DRAWQUAD, ORBIT, UNDOLASTFACE, START. (No native python enum)
    sizeOfQuad3D = 1.0 # 3D space length and height of quad to be drawn. Adjust with scrollwheel
    sizeOfQuad2D = 20 # 2D pixels value; default size (set in invoke) 3D equivalent at 3D cursor depth
    mx = 0 # mouse coords from previous quad drawing
    my = 0
    prevX = 0 # Used for orbitting, undo
    #curvatureMwheel = 0 # Not used for ver 1.0.0
    mmbDown = False
    
    def modal(self, context, event):
        
        if event.type == 'MOUSEMOVE':
            if self.mode == 'START':
                #print("in START") # Should NOT be able to ORBIT at all or change zoom level etc. yet!
                if event.mouse_region_x >= self.mx + (self.sizeOfQuad2D * 0.5):
                    # Select right edge (all selected by default):
                    bpy.ops.object.mode_set(mode='OBJECT') # Exiting initial quad on RIGHT side
                    for e in self.mesh.edges:
                        lastVerts = self.mesh.edges[e.index].vertices
                        if (lastVerts[0] == 2 and lastVerts[1] == 3) or (lastVerts[0] == 3 and lastVerts[1] == 2):
                            e.select = True
                    bpy.ops.object.mode_set(mode='EDIT')
                    self.mode = 'DRAWQUAD'
                    return {'RUNNING_MODAL'}
                
                if event.mouse_region_x <= self.mx - (self.sizeOfQuad2D * 0.5):
                    bpy.ops.object.mode_set(mode='OBJECT') # Exiting LEFT side
                    for e in self.mesh.edges:
                        lastVerts = self.mesh.edges[e.index].vertices
                        if (lastVerts[0] == 0 and lastVerts[1] == 1) or (lastVerts[0] == 1 and lastVerts[1] == 0):
                            e.select = True
                    bpy.ops.object.mode_set(mode='EDIT')
                    self.mode = 'DRAWQUAD'
                    return {'RUNNING_MODAL'}
                if event.mouse_region_y >= self.my + (self.sizeOfQuad2D * 0.5):
                    bpy.ops.object.mode_set(mode='OBJECT') # Exiting TOP side
                    for e in self.mesh.edges:
                        lastVerts = self.mesh.edges[e.index].vertices
                        if (lastVerts[0] == 3 and lastVerts[1] == 0) or (lastVerts[0] == 0 and lastVerts[1] == 3):
                            e.select = True
                    bpy.ops.object.mode_set(mode='EDIT')
                    self.mode = 'DRAWQUAD'
                    return {'RUNNING_MODAL'}
                if event.mouse_region_y <= self.my - (self.sizeOfQuad2D * 0.5):
                    bpy.ops.object.mode_set(mode='OBJECT') # Exiting BOTTOM side
                    for e in self.mesh.edges:
                        lastVerts = self.mesh.edges[e.index].vertices
                        if (lastVerts[0] == 1 and lastVerts[1] == 2) or (lastVerts[0] == 2 and lastVerts[1] == 1):
                            e.select = True
                    bpy.ops.object.mode_set(mode='EDIT')
                    self.mode = 'DRAWQUAD'
                    return {'RUNNING_MODAL'}
            
            if self.mode == 'DRAWQUAD': 
                
                context.window.cursor_modal_set("PAINT_BRUSH")
                
                if (event.mouse_region_x > self.mx + self.sizeOfQuad2D or \
                 event.mouse_region_x < self.mx - self.sizeOfQuad2D) or \
                 (event.mouse_region_y > self.my + self.sizeOfQuad2D or event.mouse_region_y < self.my - self.sizeOfQuad2D):
                     
                     #print()
                     #print("NEW quad.")
                     
                     # We've gone the set distance, so make an extrusion from the selected
                     # edge (the last edge index's vertices) to the 3D coords of the current mouse pos
                     # (found by bpy_extras). To steer path, rotate new quad's entrance verts based on
                     # dirEdge exit verts. Cross products are used to construct proper perpendicularity
                     # (dirPerp), which is the direction perpendicular to dirEdge and on which exit 
                     # verts are placed. Path of quads occurs on plane of mouse3Dpos's (mesh's) depth
                     # level. The mouseTop/Right points are used to construct vectors on this plane 
                     # (parallel with view3d camera plane), which are used to get the cross products.                     
                     
                     # Record 3D coords of mouse cursor:
                     
                     lastpolygon = len(self.mesh.polygons) -1 # len(bpy.data.meshes['Plane'].polygons) - 1
                     depth = self.mesh.polygons[lastpolygon].center
                     
                     mouse3Dpos = view3d_utils.region_2d_to_location_3d(context.region,
                                                                        context.space_data.region_3d,
                                                        (event.mouse_region_x, event.mouse_region_y),
                        depth)
                     
                     # Extrude, but don't move new verts yet:
                     bpy.ops.mesh.extrude_region()
                     
                     # Make changes in OBJECT mode:
                     bpy.ops.object.mode_set(mode='OBJECT') #bpy.ops.object.mode_set(mode='EDIT')
                     lastEdgeIndex = len(self.mesh.edges) - 1
                     lastEdgeIndex -= 2
                     lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                     
                     midPointOfEdge = (self.mesh.vertices[lastVerts[0]].co +
                                        self.mesh.vertices[lastVerts[1]].co) * 0.5
                     
                     dirEdge = Vector((mouse3Dpos - midPointOfEdge)) # Direction from exit to entrance
                     dirEdgeN = dirEdge.normalized()
                     mouseRight = view3d_utils.region_2d_to_location_3d(context.region,
                                                                        context.space_data.region_3d,
                                                        (event.mouse_region_x+20, event.mouse_region_y),
                                          mouse3Dpos)
                     mouseTop = view3d_utils.region_2d_to_location_3d(context.region,
                                                                        context.space_data.region_3d,
                                                        (event.mouse_region_x, event.mouse_region_y+20),
                                        mouse3Dpos)
                     vecTop = mouseTop - mouse3Dpos
                     vecRight = mouseRight - mouse3Dpos
                     directionCamera = vecRight.normalized().cross(vecTop.normalized())
                     dirPerp = directionCamera.normalized().cross(dirEdgeN)
                     
                     for edge in self.mesh.edges:
                         if edge.select == True:
                             #print("\nEdge ", edge.index, " is selected.")
                             v0index = self.mesh.edges[edge.index].vertices[0]
                             v1index = self.mesh.edges[edge.index].vertices[1]
                             self.mesh.vertices[v0index].co = mouse3Dpos - (dirPerp * (0.5 * self.sizeOfQuad3D))
                             self.mesh.vertices[v1index].co = mouse3Dpos + (dirPerp * (0.5 * self.sizeOfQuad3D))
                             
                     self.mx = event.mouse_region_x
                     self.my = event.mouse_region_y
                     
                     # Return to EDIT mode
                     bpy.ops.object.mode_set(mode='EDIT')
                     
                     
            else:
                if self.mode == 'ORBIT': 
                    context.window.cursor_modal_set("HAND_CLOSED") #context.window.cursor_set("HAND_CLOSED")
                
                if self.mode == 'ORBIT' and \
                    (event.mouse_region_x > self.mx + self.sizeOfQuad2D or \
                    event.mouse_region_x < self.mx - self.sizeOfQuad2D) or \
                    (event.mouse_region_y > self.my + self.sizeOfQuad2D or \
                    event.mouse_region_y < self.my - self.sizeOfQuad2D):
                    
                    if event.mouse_region_x < self.prevX:
                        bpy.ops.view3d.view_orbit(angle=0.1, type='ORBITRIGHT') # Mouse moved LEFT, so opposite.
                        #print("orbitRIGHT")
                    if event.mouse_region_x > self.prevX:
                        bpy.ops.view3d.view_orbit(angle=0.1, type='ORBITLEFT') # Mouse moved RIGHT, so opposite.
                        #print("orbitLEFT")
                    
                    lastpolygon = len(self.mesh.polygons) - 1
                    depth = self.mesh.polygons[lastpolygon].center
                    mouse3Dpos = view3d_utils.region_2d_to_location_3d(context.region,
                                                                    context.space_data.region_3d,
                                                    (event.mouse_region_x, event.mouse_region_y),
                        depth)
                    #bpy.ops.object.mode_set(mode='OBJECT') #bpy.ops.object.mode_set(mode='EDIT')
                    lastEdgeIndex = len(self.mesh.edges) - 1
                    lastEdgeIndex -= 2
                    lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                 
                    midPointOfEdge = (self.mesh.vertices[lastVerts[0]].co +
                                        self.mesh.vertices[lastVerts[1]].co) * 0.5
                    dirEdge = Vector((mouse3Dpos - midPointOfEdge)) # Direction from exit to entrance
                    dirEdgeN = dirEdge.normalized()
                    mouseRight = view3d_utils.region_2d_to_location_3d(context.region,
                                                                        context.space_data.region_3d,
                                                        (event.mouse_region_x+20, event.mouse_region_y),
                                          mouse3Dpos)
                    mouseTop = view3d_utils.region_2d_to_location_3d(context.region,
                                                                        context.space_data.region_3d,
                                                        (event.mouse_region_x, event.mouse_region_y+20),
                                        mouse3Dpos)
                    vecTop = mouseTop - mouse3Dpos
                    vecRight = mouseRight - mouse3Dpos
                    directionCamera = vecRight.normalized().cross(vecTop.normalized())
                    
                    bpy.ops.object.mode_set(mode='OBJECT')
                    lastpolygon = len(self.mesh.polygons) - 1
                    rotation_axis = self.mesh.polygons[lastpolygon].normal.cross(directionCamera)
                    angle = self.mesh.polygons[lastpolygon].normal.angle(directionCamera)
                    quat = Quaternion(rotation_axis, angle)
                    
                    # FACE the camera (latest polygon face):
                    # ------------------------------
                    newFaceIndex = len(self.mesh.polygons) - 1
                    for face in self.mesh.polygons:
                        if face.index == newFaceIndex:
                            self.mesh.polygons[face.index].select = True
                            for vertex_index in face.vertices:
                                vert = self.mesh.vertices[vertex_index]
                                vert.co = quat @ (vert.co -face.center) + face.center
                            self.mesh.polygons[face.index].select = False
                        else:
                            #print("Not face ", face.index)
                            self.mesh.polygons[face.index].select = False
                    # ------------------------------
                    
                    
                    # BUG in Blender!! can't use cursor_warp due to Y offset bug. Sinks and inconsistently to Layout.
                    # I discovered a WORKAROUND, implemented below. Nvidia? updated driver, but not a fix. Workaround
                    # simply to add 2 to region_x, and add global event.mouse_y to y (plus change you want regionally
                    # as below). Should just be region_x, region_y if fixed. Issue # 151064 on dev forum. DlF3raHX16g
                    midP = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                                                    midPointOfEdge)
                    wx = int(midP.x)
                    wy = int(midP.y)
                    context.window.cursor_warp(wx + 2, event.mouse_y + (wy - event.mouse_region_y))
                    
                    self.prevX = wx + 2 # This is necessary to consistently determine direction of mouse movements.
                    
                    self.mx = wx + 2 #event.mouse_region_x
                    self.my = event.mouse_region_y
                    
                    bpy.ops.object.mode_set(mode='EDIT')
                    
                else:
                    self.prevX = event.mouse_region_x
                    
            if self.mode == 'UNDOLASTFACE':
                #print("edges count: ", len(self.mesh.edges))
                if len(self.mesh.edges) <= 7:
                    self.report({'INFO'}, "Cannot undo last face.")
                    lastEdgeIndex = len(self.mesh.edges) - 1
                    lastEdgeIndex -= 2
                    lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                    #bpy.ops.mesh.delete(type='VERT')
                    self.mode = "DRAWQUAD"
                    context.window.cursor_modal_restore()
                    strInfo = "Finishing after deleting " + str(len(self.mesh.edges)) + " quads."
                    self.report({'INFO'}, strInfo)
                    # Delete entire mesh with .remove, and return CANCELLED? or Finished to keep an Undo stacked.
                    return {'FINISHED'}
                else:
                    bpy.ops.mesh.delete(type='VERT') # Delete vertices of SELECTED edge
                bpy.ops.object.mode_set(mode='OBJECT')
                # Select new last edge, and warp cursor to it:
                lastEdgeIndex = len(self.mesh.edges) - 1
                lastEdgeIndex -= 2
                lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                self.mesh.edges[lastEdgeIndex].select = True
                midPointOfEdge = (self.mesh.vertices[lastVerts[0]].co +
                                        self.mesh.vertices[lastVerts[1]].co) * 0.5
                midP = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                                            midPointOfEdge)
                wx = int(midP.x)
                wy = int(midP.y)
                context.window.cursor_warp(wx + 2, event.mouse_y + (wy - event.mouse_region_y))
                
                self.prevX = wx + 2 # bug 151064 workaround
                self.mx = wx + 2 #event.mouse_region_x
                self.my = event.mouse_region_y
                
                bpy.ops.object.mode_set(mode='EDIT')
                self.mode = 'DRAWQUAD' 
                return {'RUNNING_MODAL'}
            
            if self.mode == 'DECREASESIZE':
                if self.sizeOfQuad3D - 0.1 >= 0.01:
                    self.sizeOfQuad3D -= 0.1
                    # Update sizeOfQuad2D as well
                    lastEdgeIndex = len(self.mesh.edges) - 1
                    lastEdgeIndex -= 2
                    lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                    
                    some3Dpoint = self.mesh.vertices[lastVerts[0]].co
                    other3Dpoint = some3Dpoint + Vector((self.sizeOfQuad3D, 0, 0))
                    some2Dpoint = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                        some3Dpoint)
                    other2Dpoint = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                        other3Dpoint)
                    self.sizeOfQuad2D = int((some2Dpoint - other2Dpoint).length) # Absolute value?
                else:
                    self.report({'INFO'}, 'Cannot decrease quad size further.')
                #print("size2D: ", self.sizeOfQuad2D)
                self.mode = 'DRAWQUAD'
                return {'RUNNING_MODAL'}
            if self.mode == 'INCREASESIZE':
                if self.sizeOfQuad3D + 0.1 <= 5:
                    self.sizeOfQuad3D += 0.1
                    # Update sizeOfQuad2D as well
                    lastEdgeIndex = len(self.mesh.edges) - 1
                    lastEdgeIndex -= 2
                    lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                    
                    some3Dpoint = self.mesh.vertices[lastVerts[0]].co
                    other3Dpoint = some3Dpoint + Vector((self.sizeOfQuad3D, 0, 0))
                    some2Dpoint = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                        some3Dpoint)
                    other2Dpoint = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                        other3Dpoint)
                    self.sizeOfQuad2D = int((some2Dpoint - other2Dpoint).length) # Absolute value?
                else:
                    self.report({'INFO'}, 'Cannot increase quad size further.')
                #print("size2D: ", self.sizeOfQuad2D, " size3D: ", self.sizeOfQuad3D)
                self.mode = 'DRAWQUAD'
                return {'RUNNING_MODAL'}
                
        
        # Input checks:
        elif event.type == 'ESC':
            self.report({'INFO'}, 'Cancelling EdgeFlowDraw Tool.')
            context.window.cursor_modal_restore()
            steve = self.mesh
            bpy.data.meshes.remove(steve)
            return {'CANCELLED'} # .remove the EFD mesh as well as object.
        
        elif event.type == 'RIGHTMOUSE':
            if event.value == "RELEASE":
                #print("UNDO last quad draw.")
                if self.mode in {'ORBIT', 'START', 'DECREASESIZE', 'INCREASESIZE'}: #if self.mode == 'ORBIT': # ignore attempt!
                    self.report({'INFO'}, 'Cannot undo last quad draw while orbitting/starting/resizing.')
                    return {'RUNNING_MODAL'}
                if len(self.mesh.edges) <= 5:
                    self.report({'INFO'}, 'Cannot undo last face this early.') # self.report
                    lastEdgeIndex = len(self.mesh.edges) - 1
                    lastEdgeIndex -= 2
                    lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                    bpy.ops.mesh.delete(type='VERT')
                    self.mode = "DRAWQUAD"
                    context.window.cursor_modal_restore()
                    print("Finishing EdgeFlowDraw Tool. edges:", len(self.mesh.edges))
                    # Better to delete entire mesh with .remove, and return CANCELLED?
                    return {'FINISHED'}
                self.mode = "UNDOLASTFACE"
            if event.value == "PRESS" and self.mode not in {'ORBIT', 'START', 'DECREASESIZE', 'INCREASESIZE'}:
                context.window.cursor_modal_set("ERASER") # Holding press before release
                #return {'RUNNING_MODAL'}
            
        elif event.type in {'LEFTMOUSE'}:
            if self.mode == 'DRAWQUAD': 
                self.report({'INFO'}, 'Finished EdgeFlowDraw tool.')
                print("Finishing EdgeFlowDraw Tool.")
                context.window.cursor_modal_restore() #context.window.cursor_set("DEFAULT")
                return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'}:
            print("Middlemouse ", event.value)
            if self.mode == 'DECREASESIZE' or self.mode == 'INCREASESIZE' or self.mode == 'START':
                #print("preventing orbit while resizing.")
                return {'RUNNING_MODAL'}
            self.prevX = event.mouse_region_x # Confirm this! This gets called on press and release
            if event.value == 'PRESS':
                #print("MMB press")
                self.mode = 'ORBIT'
                context.window.cursor_modal_set("HAND") #context.window.cursor_set("HAND")
#                return {'PASS_THROUGH'}
            if event.value == 'RELEASE':
                #print("MMB release") # will NOT be called if press passed through
                self.mode = 'DRAWQUAD'
                context.window.cursor_modal_set("PAINT_BRUSH")
                #context.window.cursor_modal_restore() #context.window.cursor_set("DEFAULT")
#                return {'PASS_THROUGH'}
#            else:
#                print("passing MMB through. value: ", event.value)
        if event.type == 'WHEELUPMOUSE':
            #print("decrease quad size: ", event.value, " mode:", self.mode )
            if self.mode == 'START' or self.mode == 'STARTDECREASE':
                self.mode = 'STARTDECREASE'
                
                bpy.ops.object.mode_set(mode='OBJECT')
                if self.sizeOfQuad3D - 0.1 >= 0.01:
                    self.sizeOfQuad3D -= 0.1
                    if self.sizeOfQuad3D * 10 > int(self.sizeOfQuad3D) * 10: # floor(self.sizeOfQuad3D * 10):
                        self.sizeOfQuad3D = int(self.sizeOfQuad3D * 10) / 10
                    # Decrease initial face. First, update sizeOfQuad2D: 
                    lastEdgeIndex = len(self.mesh.edges) - 1
                    lastEdgeIndex -= 2
                    lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                    
                    some3Dpoint = self.mesh.vertices[lastVerts[0]].co
                    other3Dpoint = some3Dpoint + Vector((self.sizeOfQuad3D, 0, 0))
                    some2Dpoint = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                        some3Dpoint)
                    other2Dpoint = view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d,
                                        other3Dpoint)
                    self.sizeOfQuad2D = int((some2Dpoint - other2Dpoint).length) # Absolute value?
                    self.mx = event.mouse_region_x
                    self.my = event.mouse_region_y
                    
                    # Place vertices according to mouse 2D coordinates at mouse3Dpos depth:
                    cursor_location = context.scene.cursor.location.copy() # depth for mouse3Dpos
                    mouse3Dpos = view3d_utils.region_2d_to_location_3d(context.region,context.space_data.region_3d,
                                            (event.mouse_region_x, event.mouse_region_y), cursor_location)
                    self.mesh.vertices[0].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x - (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y + (0.5 * self.sizeOfQuad2D)), cursor_location)
                    self.mesh.vertices[1].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x - (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y - (0.5 * self.sizeOfQuad2D)), cursor_location)
                    self.mesh.vertices[2].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x + (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y - (0.5 * self.sizeOfQuad2D)), cursor_location)
                    self.mesh.vertices[3].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x + (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y + (0.5 * self.sizeOfQuad2D)), cursor_location)
                               
                    # Adjustments after loss of precision when converted to 2D points (some/other2Dpoint, above):
                    self.mesh.vertices[0].co = (self.mesh.vertices[1].co + self.mesh.vertices[0].co) * 0.5
                    self.mesh.vertices[0].co += (self.mesh.vertices[0].co - self.mesh.vertices[1].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # top left vertex
                    self.mesh.vertices[1].co = (self.mesh.vertices[0].co + self.mesh.vertices[1].co) * 0.5
                    self.mesh.vertices[1].co -= (self.mesh.vertices[0].co - self.mesh.vertices[1].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # bottom left vertex
                    self.mesh.vertices[3].co = (self.mesh.vertices[3].co + self.mesh.vertices[2].co) * 0.5
                    self.mesh.vertices[3].co += (self.mesh.vertices[3].co - self.mesh.vertices[2].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # top right vertex
                    self.mesh.vertices[2].co = (self.mesh.vertices[2].co + self.mesh.vertices[1].co) * 0.5
                    self.mesh.vertices[2].co += (self.mesh.vertices[2].co - self.mesh.vertices[1].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # bottom right vertex
                    self.mesh.vertices[0].co = (self.mesh.vertices[3].co + self.mesh.vertices[0].co) * 0.5
                    self.mesh.vertices[0].co -= (self.mesh.vertices[3].co - self.mesh.vertices[0].co).normalized() * \
                        self.sizeOfQuad3D * 0.5
                    # Confirm precision- slight diff, only half a hundredth of a meter:
                    #print("sizeOfQuad3D: ", self.sizeOfQuad3D, " should match 0-1: ", 
                    #    (self.mesh.vertices[0].co - self.mesh.vertices[1].co).length)
                    #print(" should match 1-2: ", (self.mesh.vertices[1].co - self.mesh.vertices[2].co).length)
                    #print(" should match 2-3: ", (self.mesh.vertices[2].co - self.mesh.vertices[3].co).length)
                    #print(" should match 3-0: ", (self.mesh.vertices[3].co - self.mesh.vertices[0].co).length)
                    #context.view_layer.update()
                    #self.mesh.update()
                else:
                    self.report({'INFO'}, 'Cannot decrease quad size further.')
                bpy.ops.object.mode_set(mode='EDIT')
                #print("in STARTDECR. size2D: ", self.sizeOfQuad2D)
                strInfo = "Resizing quad length to " + str(self.sizeOfQuad3D) + " m"
                self.report({'INFO'}, strInfo)
                self.mode = 'START'
                return {'RUNNING_MODAL'}
            elif self.mode != 'ORBIT' and self.mode != 'UNDOLASTFACE':
                self.mode = 'DECREASESIZE'
#            else:
#                print("line reached; examine.")

        if event.type == 'WHEELDOWNMOUSE':
            #print("increase quad size: ", event.value, " mode:", self.mode )
            if self.mode == 'START' or self.mode == 'STARTINCREASE' or self.mode == 'STARTDECREASE':
                self.mode = 'STARTINCREASE'
                bpy.ops.object.mode_set(mode='OBJECT')
                if self.sizeOfQuad3D + 0.1 <= 5:
                    if self.sizeOfQuad3D * 100 > int(self.sizeOfQuad3D * 100) : # ceil(self.sizeOfQuad3D * 10):
                        self.sizeOfQuad3D = int(self.sizeOfQuad3D * 100) / 100
                    self.sizeOfQuad3D += 0.1 
                    # bug? Will get like 0.7999999999 instead of 0.8 without this way above of * 100 / 100.
                    
                    # Increase initial face. First, update sizeOfQuad2D: 
                    lastEdgeIndex = len(self.mesh.edges) - 1
                    lastEdgeIndex -= 2
                    lastVerts = self.mesh.edges[lastEdgeIndex].vertices
                    
                    some3Dpoint = self.mesh.vertices[lastVerts[0]].co
                    other3Dpoint = some3Dpoint + Vector((self.sizeOfQuad3D, 0, 0))
                    some2Dpoint = view3d_utils.location_3d_to_region_2d(context.region,
                                        context.space_data.region_3d, some3Dpoint)
                    other2Dpoint = view3d_utils.location_3d_to_region_2d(context.region,
                                        context.space_data.region_3d, other3Dpoint)
                    self.sizeOfQuad2D = int((some2Dpoint - other2Dpoint).length) # Absolute value?
                    self.mx = event.mouse_region_x
                    self.my = event.mouse_region_y
                    
                    # Place vertices according to mouse 2D coordinates at mouse3Dpos depth:
                    cursor_location = context.scene.cursor.location.copy() # depth for mouse3Dpos
                    mouse3Dpos = view3d_utils.region_2d_to_location_3d(context.region,context.space_data.region_3d,
                                            (event.mouse_region_x, event.mouse_region_y), cursor_location)
                    self.mesh.vertices[0].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x - (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y + (0.5 * self.sizeOfQuad2D)), cursor_location)
                    self.mesh.vertices[1].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x - (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y - (0.5 * self.sizeOfQuad2D)), cursor_location)
                    self.mesh.vertices[2].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x + (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y - (0.5 * self.sizeOfQuad2D)), cursor_location)
                    self.mesh.vertices[3].co = view3d_utils.region_2d_to_location_3d(context.region,
                              context.space_data.region_3d, (event.mouse_region_x + (0.5 * self.sizeOfQuad2D), 
                               event.mouse_region_y + (0.5 * self.sizeOfQuad2D)), cursor_location)
                               
                    # Adjustments after loss of precision when converted to 2D points (some/other2Dpoint, above):
                    self.mesh.vertices[0].co = (self.mesh.vertices[1].co + self.mesh.vertices[0].co) * 0.5
                    self.mesh.vertices[0].co += (self.mesh.vertices[0].co - self.mesh.vertices[1].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # top left vertex
                    self.mesh.vertices[1].co = (self.mesh.vertices[0].co + self.mesh.vertices[1].co) * 0.5
                    self.mesh.vertices[1].co -= (self.mesh.vertices[0].co - self.mesh.vertices[1].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # bottom left vertex
                    self.mesh.vertices[3].co = (self.mesh.vertices[3].co + self.mesh.vertices[2].co) * 0.5
                    self.mesh.vertices[3].co += (self.mesh.vertices[3].co - self.mesh.vertices[2].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # top right vertex
                    self.mesh.vertices[2].co = (self.mesh.vertices[2].co + self.mesh.vertices[1].co) * 0.5
                    self.mesh.vertices[2].co += (self.mesh.vertices[2].co - self.mesh.vertices[1].co).normalized() * \
                        self.sizeOfQuad3D * 0.5 # bottom right vertex
                    self.mesh.vertices[0].co = (self.mesh.vertices[3].co + self.mesh.vertices[0].co) * 0.5
                    self.mesh.vertices[0].co -= (self.mesh.vertices[3].co - self.mesh.vertices[0].co).normalized() * \
                        self.sizeOfQuad3D * 0.5
                else:
                    self.report({'INFO'}, 'Cannot increase quad size further.')
                bpy.ops.object.mode_set(mode='EDIT')
                #print("size2D: ", self.sizeOfQuad2D)
                strInfo = "Resizing quad length to " + str(self.sizeOfQuad3D) + " m"
                self.report({'INFO'}, strInfo)
                self.mode = 'START'
                return {'RUNNING_MODAL'}
            elif self.mode != 'ORBIT' and self.mode != 'UNDOLASTFACE':
                self.mode = 'INCREASESIZE'
#            else:
#                print("line reached, catch this state!")
#            print("increase quad size ", event.value)
#            if self.mode != 'START' and self.mode != 'ORBIT' and self.mode != 'UNDOLASTFACE':
#                self.mode = 'INCREASESIZE'
            
        return {'RUNNING_MODAL'}
    
    
    @classmethod
    def poll(cls, context):
        #print("poll top.") #self.report({'INFO'}, "poll")
        if bpy.ops.view3d.render_border.poll():
            return {'CANCELLED'}
            # Another way is to simply do: return context.area.type == 'VIEW_3D'
    
    def invoke(self, context, event):
        
        if context.area.type == 'VIEW_3D':
            
            print("\nEdgeFlowDraw Tool ver. 1.0.0")
            self.report({'INFO'}, "EdgeFlowDraw: Start drawing quads with mouse. LMB to finish.")
            
            # Use of 3D cursor provides the depth for mouse3Dpos.
            
            # Adds new plane mesh object with center at mouse3Dpos
            # Mesh and obj created by API calls, not bpy.ops
            # Plane faces camera. (if use bpy.ops (bad), must do it differently to align face.)
            
            cursor_location = context.scene.cursor.location.copy() # depth for mouse3Dpos
            mouse3Dpos = view3d_utils.region_2d_to_location_3d(context.region,
                                                            context.space_data.region_3d,
                                            (event.mouse_region_x, event.mouse_region_y),
                                            cursor_location)
            # Place vertices according to mouse 2D coordinates at mouse3Dpos depth:
            topLeftVertex3D = view3d_utils.region_2d_to_location_3d(context.region,
                                                            context.space_data.region_3d,
                                            (event.mouse_region_x - (0.5 * self.sizeOfQuad2D), 
                                                event.mouse_region_y + (0.5 * self.sizeOfQuad2D)),
                                            cursor_location)
            topRightVertex3D = view3d_utils.region_2d_to_location_3d(context.region,
                                                            context.space_data.region_3d,
                                            (event.mouse_region_x + (0.5 * self.sizeOfQuad2D), 
                                                event.mouse_region_y + (0.5 * self.sizeOfQuad2D)),
                                            cursor_location)
            bottomRightVertex3D = view3d_utils.region_2d_to_location_3d(context.region,
                                                            context.space_data.region_3d,
                                            (event.mouse_region_x + (0.5 * self.sizeOfQuad2D), 
                                                event.mouse_region_y - (0.5 * self.sizeOfQuad2D)),
                                            cursor_location)
            bottomLeftVertex3D = view3d_utils.region_2d_to_location_3d(context.region,
                                                            context.space_data.region_3d,
                                            (event.mouse_region_x - (0.5 * self.sizeOfQuad2D), 
                                                event.mouse_region_y - (0.5 * self.sizeOfQuad2D)),
                                            cursor_location)
            self.sizeOfQuad3D = (topLeftVertex3D - topRightVertex3D).length
            #print("sizeOfQuad3D: ", self.sizeOfQuad3D)
            
            if context.active_object != None or context.selected_objects:
                bpy.ops.object.mode_set(mode='OBJECT')
                for polygon in context.active_object.data.polygons:
                    polygon.select = False
                for e in context.active_object.data.edges:
                    e.select = False
                for v in context.active_object.data.vertices:
                    v.select = False
            bpy.ops.object.select_all(action='DESELECT')
            
            Vertices = \
            [
                topLeftVertex3D, bottomLeftVertex3D, bottomRightVertex3D, topRightVertex3D,
            ]
            #topLeftVertex3D, bottomLeftVertex3D, bottomRightVertex3D, topRightVertex3D,
            # Counter-clockwise direction to see front of face
            self.mesh = bpy.data.meshes.new(name="EFD")
            self.mesh.from_pydata \
            (
                Vertices,
                [],
                [[0,1,2,3]]
            )
            # [[0,1,2,3]]
            
            temp = self.mesh.edges[0].vertices[0] # For some reason, edge zero's vertices need to be swapped.
            self.mesh.edges[0].vertices[0] = self.mesh.edges[0].vertices[1] # If not swapped, edge is flipped.
            self.mesh.edges[0].vertices[1] = temp
            
            if self.mesh.validate(verbose=True):
                print("Mesh had problems and was altered; see console output.")
                self.report({'WARNING'}, "Problem occurred during mesh creation! Please report console output.")
            self.mesh.update()
            self.obj = bpy.data.objects.new("EFD", self.mesh)
            context.scene.collection.objects.link(self.obj)
            self.obj.select_set(True)
            context.view_layer.objects.active = self.obj
            
            self.obj.rotation_mode = 'QUATERNION'
            bpy.ops.object.mode_set(mode='OBJECT')
            for polygon in context.active_object.data.polygons:
                polygon.select = False
            for e in self.mesh.edges:
                e.select = False
            for v in self.mesh.vertices:
                v.select = False
            self.mode = 'START' 
            
            # Face Camera code- not needed, now that API calls used to place mesh around mouse:
#            regionMidPtX = context.region.width / 2
#            regionMidPtY = context.region.height / 2
#            #mouseX = (regionMidPtX - event.mouse_region_x) + regionMidPtX + self.curvatureMwheel
#            #mouseY = (regionMidPtY - event.mouse_region_y) + regionMidPtY + self.curvatureMwheel
#            mouseX = regionMidPtX # First quad, so make it CONSISTENTLY flat with rest of path!
#            mouseY = regionMidPtY # For subsequent quads, can try commented code above (mousewheel)
#            dirC = view3d_utils.region_2d_to_vector_3d(context.region,
#                                                                     context.space_data.region_3d,
#                                                     (mouseX, mouseY))
#            bpy.ops.object.mode_set(mode='OBJECT')
#            dirQ = dirC.to_track_quat('-Z','Y') # this is similar to a "lookAt()" function.
#            bpy.data.objects['Plane'].rotation_quaternion = dirQ 
#            bpy.ops.object.transform_apply(rotation=True) # THIS is necessary! ensure obj is selected
#            bpy.ops.object.mode_set(mode='EDIT')
            
            context.window_manager.modal_handler_add(self)
            
            self.mx = event.mouse_region_x
            self.my = event.mouse_region_y
            
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found; cannot run operator")
            return {'CANCELLED'}
    
#def menu_func(self, context):
#    self.layout.operator(DrawByQuadModalOp.bl_idname, text="EdgeFlowDraw tool")
    
#def register():
#    bpy.utils.register_class(DrawByQuadModalOp)
#    bpy.types.VIEW3D_MT_view.append(menu_func)
#    
#def unregister():
#    bpy.utils.unregister_class(DrawByQuadModalOp)
#    bpy.types.VIEW3D_MT_view.remove(menu_func)
    
#if __name__ == "__main__":
#    register()
    #bpy.ops.object.modal_drawbyquad_op('INVOKE_DEFAULT')
        
        
        
        



    
    