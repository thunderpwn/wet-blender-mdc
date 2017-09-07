# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Module: blender_scene.py
# Description: read/write blender scene via Blender API.

# TODO
# - this whole thing needs to be cleaned up
# - BlenderNormal class

import bpy
import mathutils
import os

from .util import Util
from .options import ImportOptions, ExportOptions

'''
================================================================================
BlenderObject

Description: resembles mdc surface data mainly.
================================================================================
'''

class BlenderObject:

    def __init__(self, name):

        self.name = name
        self.verts = []              # numFrames * numVerts
        self.normals = []            # numFrames * numVerts
        self.uvMap = []              # numVerts
        self.faces = []
        self.materialNames = []

'''
================================================================================
BlenderTag

Description: resembles mdc tag. Tags are modelled by the user via an empty of
type 'arrow'.
================================================================================
'''

class BlenderTag:

    def __init__(self, name):

        self.name = name
        self.locRot = []  # numFrames


    def encodeLocRot(x, y, z, yaw, pitch, roll):

        location = mathutils.Matrix.Translation((x, y, z))

        euler = mathutils.Euler((yaw, pitch, roll), 'XYZ')
        rotation = euler.to_matrix()

        locRot = location * rotation.to_4x4()

        return locRot


    def decodeLocRot(locRot):

        xyz = locRot.to_translation()
        x = xyz[0]
        y = xyz[1]
        z = xyz[2]

        angles = locRot.to_euler()
        yaw = angles[2]
        pitch = angles[1]
        roll = angles[0]

        return x, y, z, yaw, pitch, roll

'''
================================================================================
BlenderScene

Description: resembles converted mdc data in blender. Holds references to all
data needed to read and write a scene via the blender API.
================================================================================
'''

class BlenderScene:

    def __init__(self, name):

        self.name = name
        self.numFrames = 0
        self.frameNames = []   # numFrames
        self.frameOrigins = [] # numFrames
        self.tags = []         # numTags
        self.objects = []      # numSurfaces


    def read(exportOptions):

        sceneName = bpy.context.scene.name
        blenderScene = BlenderScene(sceneName)

        # numFrames
        blenderScene.numFrames = bpy.context.scene.frame_end + 1 \
                                 - bpy.context.scene.frame_start \

        # frameNames, frameOrigins - TODO for now hardcoded
        for i in range(0, blenderScene.numFrames):

            blenderScene.frameNames.append("(from Blender)")
            blenderScene.frameOrigins.append((0, 0, 0))

        # choose tags, objects and normalObjects for export
        tags = []
        objects = []
        normalObjects = []

        if exportOptions.selection == True:

            for o in bpy.context.selected_objects:

                if o.type == 'MESH':
                    objects.append(o)

                if o.type == 'EMPTY' and o.empty_draw_type == 'ARROWS':
                    tags.append(o)

                if exportOptions.normalObjects == True and \
                    o.type == 'EMPTY' and \
                    o.empty_draw_type == 'SINGLE_ARROW' and \
                    o.parent_type == 'VERTEX':
                       normalObjects.append(o)

        else:

            for o in bpy.context.scene.objects:

                if o.type == 'MESH':
                    objects.append(o)

                if o.type == 'EMPTY' and o.empty_draw_type == 'ARROWS':
                    tags.append(o)

                if exportOptions.normalObjects == True and \
                    o.type == 'EMPTY' and \
                    o.empty_draw_type == 'SINGLE_ARROW' and \
                    o.parent_type == 'VERTEX':
                       normalObjects.append(o)

        # tags
        for tag in tags:

            blenderTag = BlenderTag(tag.name)

            for i in range(0, blenderScene.numFrames):

                bpy.context.scene.frame_set(i)
                locRot = tag.matrix_basis.copy()
                blenderTag.locRot.append(locRot)

            blenderScene.tags.append(blenderTag)

        bpy.context.scene.frame_set(0) # TODO is this needed?

        # objects
        for object in objects:

            blenderObject = BlenderObject(object.name)

            # get a triangulated mesh
            bpy.context.scene.objects.active = object
            bpy.ops.object.modifier_add(type='TRIANGULATE')

            # verts, normals
            for i in range(0, blenderScene.numFrames):

                bpy.context.scene.frame_set(i)
                mesh = object.to_mesh(bpy.context.scene, True, 'PREVIEW')

                frameVerts = []
                frameNormals = []

                for vert in mesh.vertices:

                    globalVert = object.matrix_world * vert.co
                    frameVerts.append(globalVert)

                    globalNormal = object.matrix_world * vert.normal
                    globalNormal.normalize()
                    frameNormals.append(globalNormal)

                # make an extra run for the user modelled vertex normals
                for normalObject in normalObjects:

                    if normalObject.parent.name != object.name:
                        continue

                    matrix_basis = normalObject.matrix_basis

                    x = matrix_basis[0][2]
                    y = matrix_basis[1][2]
                    z = matrix_basis[2][2]
                    normal = (x, y, z)

                    vertexIndex = normalObject.parent_vertices[0]
                    frameNormals[vertexIndex] = normal

                blenderObject.verts.append(frameVerts)
                blenderObject.normals.append(frameNormals)

                bpy.data.meshes.remove(mesh)


            # get a new mesh
            bpy.context.scene.frame_set(0) # TODO is this needed?
            mesh = object.to_mesh(bpy.context.scene, True, 'PREVIEW')

            # faces
            for face in mesh.polygons:

                faceIndexes = []

                for index in face.vertices:

                    faceIndexes.append(index)

                blenderObject.faces.append(faceIndexes)

            # uvMap
            bpy.ops.object.mode_set(mode='OBJECT')

            uv_layer = mesh.uv_layers.active

            uvMap = []
            uvMapQueue = []

            newVertexCount = 0

            for i in range(0, len(mesh.vertices)):
                uvMap.append(None)
                uvMapQueue.append(None)

            # prepare uvMapQueue
            # this is to handle 1 to many mappings of a vertex to the uvMap
            for polygon in mesh.polygons:

                faceNum = polygon.index

                for loopIndex in polygon.loop_indices:

                    loop = mesh.loops[loopIndex]

                    vertexIndex = loop.vertex_index
                    uvCoordinates = uv_layer.data[loop.index].uv

                    if uvMapQueue[vertexIndex] == None:
                        uvMapQueue[vertexIndex] = []

                    uvMapQueue[vertexIndex].append((faceNum, uvCoordinates))


            for vertexIndex, vertexMappings in enumerate(uvMapQueue):

                # split vertex by different uv mapping
                splitQueue = []

                for mapping in vertexMappings:

                    faceNum = mapping[0]
                    uvCoords = mapping[1]

                    if uvMap[vertexIndex] == None:

                        uvMap[vertexIndex] = uvCoords

                    else:

                        if uvMap[vertexIndex] != uvCoords:
                            splitQueue.append(mapping)

                # process splitQueue, create new verts and faces if needed
                originalUvMapLen = len(uvMap) - 1

                for splitQueueItem in splitQueue:

                    uvCoords = splitQueueItem[1]

                    # find out if we need to create a new vertex

                    j = len(uvMap) - 1
                    uvMapIndex = vertexIndex
                    uvMapIndexFound = False

                    while originalUvMapLen < j:

                        if uvMap[j] == uvCoords:

                            if uvMapIndexFound == True:
                                print("multiple uv indexes, this shouldn't happen")

                            uvMapIndexFound = True
                            uvMapIndex = j
                            newVertexCount += 1

                        j -= 1

                    # modify verts and normals (simply append)
                    if uvMapIndexFound == False:

                        uvMap.append(uvCoords)
                        uvMapIndex = len(uvMap) - 1

                        for frameNum in range(0, blenderScene.numFrames):

                            frameVert = blenderObject.verts[frameNum][vertexIndex]
                            frameNormal = blenderObject.normals[frameNum][vertexIndex]

                            blenderObject.verts[frameNum].append(frameVert)
                            blenderObject.normals[frameNum].append(frameNormal)

                    # modify face indexes to match new vertex
                    faceNum = splitQueueItem[0]
                    face = blenderObject.faces[faceNum]
                    oldVertexNum = vertexIndex
                    newVertexNum = uvMapIndex

                    if face[0] == oldVertexNum:
                        newFace = (newVertexNum, face[1], face[2])
                        blenderObject.faces[faceNum] = newFace
                    elif face[1] == oldVertexNum:
                        newFace = (face[0], newVertexNum, face[2])
                        blenderObject.faces[faceNum] = newFace
                    else:
                        newFace = (face[0], face[1], newVertexNum)
                        blenderObject.faces[faceNum] = newFace

            blenderObject.uvMap = uvMap

            if newVertexCount > 0:
                print("MDCExport Info: new vertices added for object=: " \
                      + str(blenderObject.name) + \
                      ", count=" + str(newVertexCount))

            '''
            # old uvMap code
            uvMap = []
            uv_layer = mesh.uv_layers.active

            if uv_layer == None:
                uvMap = None
            else:
                for i in range(0, len(mesh.vertices)):
                    uvMap.append(None)

                for index, uv_loop in enumerate(uv_layer.data):

                    vertexIndex = mesh.loops[index].vertex_index
                    uv = uv_loop.uv

                    if uvMap[vertexIndex] == None:

                        uvMap[vertexIndex] = uv

            blenderObject.uvMap = uvMap
            '''

            # materialNames
            for slot in object.material_slots:

                blenderObject.materialNames.append(slot.name)

            # remove Triangulate modifier
            bpy.ops.object.modifier_remove(modifier=object.modifiers[-1].name)

            blenderScene.objects.append(blenderObject)

        return blenderScene


    def write(self, importOptions):

        if importOptions.toNewScene == True:
            bpy.ops.scene.new()

        # objects
        for i in range(0, len(self.objects)):

            name = self.objects[i].name

            mesh = bpy.data.meshes.new(name)
            object = bpy.data.objects.new(name, mesh)
            object.location = (0,0,0)
            object.show_name = True

            # link object to scene and make active
            scene = bpy.context.scene
            scene.objects.link(object)
            scene.objects.active = object
            object.select = True

            # verts, faces
            mesh.from_pydata(self.objects[i].verts[0], [], \
                             self.objects[i].faces)
            mesh.update()

            # shape keys for animation
            shapeKey = object.shape_key_add(name=self.frameNames[0], \
                                            from_mix=False)
            mesh.shape_keys.use_relative = False

            for j in range(1, self.numFrames):

                verts = self.objects[i].verts[j]
                shapeKey = object.shape_key_add(name=self.frameNames[j], \
                                                from_mix=False)
                for k in range(0, len(object.data.vertices)):

                    x = verts[k][0]
                    y = verts[k][1]
                    z = verts[k][2]
                    shapeKey.data[k].co = (x, y, z)

            bpy.context.scene.objects.active = object
            bpy.context.object.active_shape_key_index = 0
            bpy.ops.object.shape_key_retime()

            for j in range(0, self.numFrames):

                mesh.shape_keys.eval_time = 10.0 * (j + 1)
                mesh.shape_keys.keyframe_insert('eval_time', frame=j)

            # update mesh with new data
            mesh.update()

            # uvMap
            mesh.uv_textures.new('UVMap')

            for polygon in mesh.polygons:
                for j in range(polygon.loop_start, polygon.loop_start + polygon.loop_total):
                    vertexIndex = mesh.loops[j].vertex_index
                    mesh.uv_layers['UVMap'].data[j].uv = \
                        self.objects[i].uvMap[vertexIndex]

            # materialNames and textures
            for j in range(0, len(self.objects[i].materialNames)):
                materialName = self.objects[i].materialNames[j]
                material = bpy.data.materials.new(materialName)
                mesh.materials.append(material)

                # add texture if possible
                textureSuccess = False
                textureName = importOptions.gamePath + "\\" + materialName

                # first try
                if os.path.isfile(textureName):
                    textureSuccess = True

                # second try
                if textureSuccess == False:
                    textureName = Util.swapAddFileExtension(textureName)
                    if os.path.isfile(textureName):
                        textureSuccess = True

                # third try
                if textureSuccess == False:
                    textureName = Util.swapAddFileExtension(textureName)
                    if os.path.isfile(textureName):
                        textureSuccess = True

                if textureSuccess == True:

                    texture = bpy.data.textures.new('Texture', 'IMAGE')
                    texture_slot = material.texture_slots.create(0)
                    texture_slot.uv_layer = 'UVMap'
                    texture_slot.use = True
                    texture_slot.texture_coords = 'UV'
                    texture_slot.texture = texture
                    image = bpy.data.images.load(textureName)
                    texture.image = image

            # update mesh with new data
            mesh.update(calc_edges=True)
            mesh.validate()

            # normals
            # add first frame
            # 'blender', "blenderObject' 'mdcObject'

            if importOptions.normals == "mdcObject":

                verts = self.objects[i].verts[0]
                normals = self.objects[i].normals[0]

                addedNormals = []

                for j in range(0, len(normals)):

                    vert = verts[j]
                    normal = normals[j]

                    # TODO encodeLocRot für BlenderNormal

                    b3 = mathutils.Vector(normal)

                    # find orthogonal basis vectors
                    b2 = mathutils.Vector(Util.getOrthogonal(b3))
                    b1 = b2.cross(b3)

                    # normalize
                    b1.normalize()
                    b2.normalize()
                    b3.normalize()

                    # build transformation matrix
                    basis = mathutils.Matrix()
                    basis[0].xyz = b1
                    basis[1].xyz = b2
                    basis[2].xyz = b3
                    basis.transpose()
                    basis.translation = object.matrix_world * mathutils.Vector((0,0,0))

                    # draw an arrow from normal
                    normalObject = bpy.data.objects.new("empty", None)
                    bpy.context.scene.objects.link(normalObject)
                    normalObject.name = 'vertex_normal'
                    normalObject.empty_draw_type = 'SINGLE_ARROW'
                    '''
                    bpy.ops.object.add(type='EMPTY')
                    normalObject = bpy.context.object
                    normalObject.name = 'vertex_normal'
                    normalObject.empty_draw_type = 'SINGLE_ARROW'
                    '''

                    # parent object to vertex
                    normalObject.parent = object
                    normalObject.parent_type = 'VERTEX'
                    normalObject.parent_vertices[0] = j

                    normalObject.matrix_basis = basis

                    normalObject.keyframe_insert('location', \
                                              frame=0, \
                                              group='LocRot')
                    normalObject.keyframe_insert('rotation_euler', \
                                              frame=0, \
                                              group='LocRot')

                    layer = [False]*20
                    layer[int(importOptions.normalsLayer) - 1] = True
                    normalObject.layers = layer



                    addedNormals.append(normalObject)

                # add other frames
                for j in range(1, self.numFrames):

                    verts = self.objects[i].verts[j]
                    normals = self.objects[i].normals[j]

                    for k in range(0, len(normals)):

                        vert = verts[k]
                        normal = normals[k]

                        # TODO locRot func

                        b3 = mathutils.Vector(normal)

                        # find orthogonal basis vectors
                        b2 = mathutils.Vector(Util.getOrthogonal(b3))
                        b1 = b2.cross(b3)

                        # normalize
                        b1.normalize()
                        b2.normalize()
                        b3.normalize()

                        # build transformation matrix
                        basis = mathutils.Matrix()
                        basis[0].xyz = b1
                        basis[1].xyz = b2
                        basis[2].xyz = b3
                        basis.transpose()
                        basis.translation = object.matrix_world * mathutils.Vector((0,0,0))

                        normalObject = addedNormals[k]

                        normalObject.matrix_basis = basis

                        normalObject.keyframe_insert('location', \
                                                  frame=j, \
                                                  group='LocRot')
                        normalObject.keyframe_insert('rotation_euler', \
                                                  frame=j, \
                                                  group='LocRot')

            # TODO
            #else if importOptions.normals == "blenderObject":


        # tags
        if len(self.tags) > 0:

            addedTags = []

            # add first frame
            for i in range(0, len(self.tags)):

                tag = self.tags[i]

                tagObject = bpy.data.objects.new("empty", None)
                bpy.context.scene.objects.link(tagObject)
                tagObject.name = tag.name
                tagObject.empty_draw_type = 'ARROWS'
                tagObject.rotation_mode = 'XYZ'
                tagObject.matrix_basis = tag.locRot[0]

                '''
                bpy.ops.object.add(type='EMPTY')
                tagObject = bpy.context.object
                tagObject.name = tag.name
                tagObject.empty_draw_type = 'ARROWS'
                tagObject.rotation_mode = 'XYZ'
                tagObject.matrix_basis = tag.locRot[0]
                '''

                tagObject.keyframe_insert('location', \
                                          frame=0, \
                                          group='LocRot')
                tagObject.keyframe_insert('rotation_euler', \
                                          frame=0, \
                                          group='LocRot')

                addedTags.append(tagObject)

            # add other frames
            for i in range(1, self.numFrames):

                for j in range(0, len(self.tags)):

                    tag = self.tags[j]

                    tagObject = addedTags[j]
                    tagObject.matrix_basis = tag.locRot[i]

                    tagObject.keyframe_insert('location', \
                                              frame=i, \
                                              group='LocRot')
                    tagObject.keyframe_insert('rotation_euler', \
                                              frame=i, \
                                              group='LocRot')

        # frames
        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_end = self.numFrames - 1

        # TODO frameOrigins

        if importOptions.toNewScene == True:

            # name
            bpy.context.scene.name = self.name

            # some final settings
            bpy.context.scene.game_settings.material_mode = 'GLSL'
            bpy.ops.object.lamp_add(type='HEMI')

        bpy.context.scene.frame_set(0)
