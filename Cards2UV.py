bl_info = {
    "name": "Hair cards to UV C2UV",
    "blender": (3, 3, 0),
    "location" : "Right 3d View Panel -> Blender Addon",
    "category": "Object"
}

from ast import Attribute
from email.policy import default
from os import name
from pydoc import visiblename
import bpy
import bmesh
import random
from collections import namedtuple

from mathutils import Vector

from dataclasses import dataclass
import re
from bpy.app.handlers import persistent

from bpy.props import (StringProperty,
                       BoolProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       EnumProperty,
                       IntProperty,
                       BoolVectorProperty,
                       PointerProperty,
                       CollectionProperty)

import math

#Activate all debug print's
PRINT_DEBUG = True

#Default rgb gradient colors (softy) for newly created UV array
default_rgb_colors = [
    [1,0.25,0.05,1], #R
    [0.5,1,0.1,1], #G
    [0.1,0.5,1,1], #B
]

rotation_dict = {
    "0" : "0",            #0  degree
    "90" : "1.570796",     #90 degree
    "180" : "3.141592",     #180 degree
    "270" : "4.712388",     #270 degree
    #"360" TODOPASS FIX
}

def print_debug(str, argument = None):
    if PRINT_DEBUG == False:
        return

    str = "C2UV_DEBUG_OUTPUT >> {}".format(str)

    if type(argument) is list:
        print(str.format(*argument))
    if argument is None:
        print(str)
    else:
        print(str.format(argument))

# Switch select object flag in array
def array_selection_object(array, selectflag):
    for so in array:
        so.select_set(selectflag)

#Convert blender color to simple array
def blendercolor_to_RGB(color):
    r = color[0]
    g = color[1]
    b = color[2]
    
    a = color[3]
    return [r, g, b, a]

#Class: Colors array for collection
class CARDS2UV_colorsarray(bpy.types.PropertyGroup):
    color : FloatVectorProperty(
             name = "Color Picker",
             subtype = "COLOR",
             default = (1.0,1.0,1.0,1.0),
             min=0.0, max=1.0,
             size = 4,
    )

#Class: Textures array for collection with selection
class CARDS2UV_texturenodesnames(bpy.types.PropertyGroup):
    node_name : StringProperty(name="Texture Node Name")
    #texturename : StringProperty(name="Texture Name")
    is_selected : BoolProperty(name="Texture Node Selected", default=False)

#Operator: Add color to CARDS2UV_colorsarray
class CARDS2UV_Array_GradientElement(bpy.types.Operator):
    bl_label = "Add Gradient Element For Card Array"
    bl_idname = "cards2uv.gradient_element"
    bl_options = {'REGISTER', 'UNDO'}

    color_index : IntProperty(name="Gradient Array Index", options={'HIDDEN'})
    array_index : IntProperty(name="Array Index", options={'HIDDEN'})

    is_addelement : BoolProperty(name="Is Add Element", options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray[self.array_index]
        gradient_array = C2UV_UVCardsArray.colors
        
        if self.is_addelement:
            gradient_array.add()
        else:
            if self.color_index > 0:
                gradient_array.remove(self.color_index)

        return {'FINISHED'}

#Update all objects active material by card (CARDS2UV_uvelement)
def UpdateObjectsColorByCard(card):
    for o in bpy.data.objects:
        if o.active_material == card.material:
            o.color = card.color

def GetGradientArrayFromBlenderHax(material, colors, count):
    nodes = material.node_tree.nodes
    
    valToRgb = nodes.new("ShaderNodeValToRGB")
    valToRgb.name = "GRADIENT_TEMPORARY"
    #valToRgb.location = (10000, 10000)

    rampElements = valToRgb.color_ramp.elements

    #Change First Ramp Element
    if len(rampElements) > 1:
        rampElements.remove(rampElements[len(rampElements) - 1])
    firstElement = rampElements[0]
    firstElement.position = 0.0

    #Add colors to ramp
    iterator = float(1 / (len(colors) - 1))
    print_debug(f"ITERATOR: {iterator}")

    currentPos = 0.0
    lastIndex = len(colors) - 1

    lastElement = None

    for ci, color in enumerate(colors):
        elem = None
        if ci == 0:
            elem = firstElement
        elif ci == lastIndex:
            elem = rampElements.new(1.0)
            lastElement = elem
        else:
            elem = rampElements.new(currentPos)

        elem.color = (color[0], color[1], color[2], color[3])
        currentPos = currentPos + iterator

    #Caclulate Colors For Output
    outputArray = []

    iterator = float(1 / count)
    currentPos = 0.0
    for ind in range(count):
        if ind == 0:
            outputArray.append(blendercolor_to_RGB(firstElement.color))
            currentPos = currentPos + iterator
        elif ind == count - 1:
            outputArray.append(blendercolor_to_RGB(lastElement.color))
        
        currentPos = currentPos + iterator
        elem = rampElements.new(currentPos)

        outputArray.append(blendercolor_to_RGB(elem.color))

    #Remove Temp Node
    nodes.remove(valToRgb)

    return outputArray

#Operator: Update color for card or array of cards or selected cards (CARDS2UV_uvelement)
class CARDS2UV_Card_ApplyCardColorUI(bpy.types.Operator):
    bl_label = "Apply Colors For Card/s"
    bl_idname = "cards2uv.apply_card_color"
    bl_options = {'REGISTER', 'UNDO'}

    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})
    element_index : IntProperty(name="UV Element Index", options={'HIDDEN'}, default=-1)

    update_mode : EnumProperty(name="Which To Update",
    items=[
        ("ELEMENT", "Update card color", "Only update color for card"),
        ("ARRAY", "Update all cards color", "Update cards with gradient from array"),
        ("SELECTED", "Update selected cards color", "Update selected cards with gradient from array")
    ])

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray
        current_array = C2UV_UVCardsArray[self.array_index]

        if self.update_mode == "ELEMENT":
            elem = current_array.uv_array[self.element_index]
            UpdateObjectsColorByCard(elem)
        elif self.update_mode == "SELECTED":
            selected = [i for i in current_array.uv_array if i.is_selected]
            array_colors = [i.color for i in current_array.colors]
            gradient = GetGradientArrayFromBlenderHax(current_array.material, array_colors, len(selected))

            for s, sel in enumerate(selected):
                for r in range(4):
                    print_debug(f"CHANGING {s}, {sel}, {gradient[s][r]}")

                    sel.color[r] = gradient[s][r]
                UpdateObjectsColorByCard(sel)
        elif self.update_mode == "ARRAY":
            array_colors = [i.color for i in current_array.colors]
            gradient = GetGradientArrayFromBlenderHax(current_array.material, array_colors, len(current_array.uv_array)) #TODOPASS WHAT WRONG WITH YOU
            
            for e, el in enumerate(current_array.uv_array):
                for r in range(4):
                    #print_debug(f"{e}  -----    {r}   ----  {len(gradient)}")
                    el.color[r] = gradient[e][r]
                UpdateObjectsColorByCard(el)
        
        return {"FINISHED"}

#Class: UV card represent hair card with additional features
class CARDS2UV_uvelement(bpy.types.PropertyGroup):
    is_shown : BoolProperty(default=False)
    is_selected : BoolProperty(default=False)

    central : FloatVectorProperty(size=2)
    moda : FloatVectorProperty(size=2)
    scale : FloatVectorProperty(size=2)

    shortname : StringProperty(name="Short name", default="NaN")

    visiblename : StringProperty(name="Visible name", default="NaN")

    groupname : StringProperty(name="Group name", default="NaN")

    material : PointerProperty(
        name="Material",
        type=bpy.types.Material,
    )

    rotationcurrent : FloatProperty(name="Current ratation", default=1.570796)

    mapping_mode : EnumProperty(name="Which To Update",
    items=[
        ("UV", "UV mode", "Uses Texture Coordinate And UV Pin"),
        ("ATTRIBUTE", "Attribute mode", "Uses Attribute With Name")
    ])

    #attribute_mapping_name : StringProperty(name="Attribute Mapping Name", default="C2UV_ATTR")
    attribute_mapping_name : StringProperty(name="Attr Name", default="C2UV_ATTR")

    rotation : EnumProperty(name="UV Rotate Angle",
        items=[
            (rotation_dict["0"], "0", "", "TRIA_RIGHT", 1),
            (rotation_dict["90"], "90", "", "TRIA_DOWN", 2),
            (rotation_dict["180"], "180", "", "TRIA_LEFT", 3),
            (rotation_dict["270"], "270", "", "TRIA_UP", 4),
            ]
    )

    color : FloatVectorProperty(
             name = "Color Picker",
             subtype = "COLOR",
             default = (1.0,1.0,1.0,1.0),
             min=0.0, max=1.0,
             size = 4,
    )

#Class: Array of UV cards (CARDS2UV_uvelement) with additional features
class CARDS2UV_cardsarray(bpy.types.PropertyGroup):
    creation_mode : EnumProperty(name="Cards Creation Mode",
        items=[
            ("ALLFACES", "All faces", "", "MODE_ALLFACES", 1),
            ("VERTEXGROUP", "Vertex Group", "", "MODE_VERTEXGROUP", 2),
            ]
    )

    is_shown : BoolProperty(default=False)
    properties : BoolProperty(default=False)
    texprop_shown : BoolProperty(default=False)

    uv_array : CollectionProperty(type=CARDS2UV_uvelement)
    texnodes_array : CollectionProperty(type=CARDS2UV_texturenodesnames)

    colors_shown : BoolProperty(default=False)
    colors : CollectionProperty(type=CARDS2UV_colorsarray)

    mapping_mode : EnumProperty(name="Which To Update",
    items=[
        ("UV", "UV mode", "Uses Texture Coordinate And UV Pin"),
        ("ATTRIBUTE", "Attribute mode", "Uses Attribute With Name")
    ])

    attribute_mapping_name : StringProperty(name="Attr Name", default="C2UV_ATTR")

    rotation : EnumProperty(name="UV Rotate Angle (ALL)",
        items=[
            (rotation_dict["0"], "0", "", "TRIA_RIGHT", 1),
            (rotation_dict["90"], "90", "", "TRIA_DOWN", 2),
            (rotation_dict["180"], "180", "", "TRIA_LEFT", 3),
            (rotation_dict["270"], "270", "", "TRIA_UP", 4),
            ]
    )

    from_object : PointerProperty(
        name="Object",
        type=bpy.types.Object,
    )

    material : PointerProperty(
        name="Material",
        type=bpy.types.Material,
    )

#Operator: Execute on blender start
class CARDS2UV_initialize(bpy.types.Operator):
    bl_idname = "cards2uv.load_grids_from_materials"
    bl_label = "CARDS2UV_loadgridsfrommaterials"
    bl_description = "CARDS2UV_loadgridsfrommaterials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        arraytodelete = []
        for c in range(len(C2UV_UVCardsArray)):
            #deleteflag = False
            cobject = C2UV_UVCardsArray[c]

            uvelementsdelete = []
            for i in range(len(cobject.uv_array)):
                iobject = cobject.uv_array[i]

                if iobject.material == None:
                    uvelementsdelete.append(i)

            for di in reversed(uvelementsdelete):
                cobject.uv_array.remove(di)

            if len(cobject.uv_array) == 0:
                arraytodelete.append(c)

        for dc in reversed(arraytodelete):
            print_debug("CARDS2UV_initialize Now Delete Array Index {}", dc)
            C2UV_UVCardsArray.remove(dc)

        return {"FINISHED"}

@persistent
def load_handler(self, dummy):
    print_debug("Load Handler Execute")
    CARDS2UV_initialize.execute(self, bpy.context)

bpy.app.handlers.load_post.append(load_handler)

#Get texture nodes from materials
def poll_texture_nodes_from_material(material):
    texnodes = []
    nodes = material.node_tree.nodes

    for n in reversed(nodes):
        if n.type in ['TEX_IMAGE']:
            texnodes.append(n)

    return texnodes

#Create of update texture nodes names in array of cards (CARDS2UV_cardsarray)
def create_or_modify_textures_names(arrayel):
    texture_nodes = poll_texture_nodes_from_material(arrayel.material)
    print_debug(texture_nodes)

    removelist = []
    for i, t in enumerate(arrayel.texnodes_array):
        if t.node_name not in [i.name for i in texture_nodes]:
            print_debug(f"Remove element {t.node_name}")
            removelist.append(i)

    for r in reversed(removelist):
        arrayel.texnodes_array.remove(r)

    for n in texture_nodes:
        if not any(i for i in arrayel.texnodes_array if i.node_name == n.name):
            nw = arrayel.texnodes_array.add()
            nw.node_name = n.name
            nw.is_selected = False

    if len(arrayel.texnodes_array) > 0 and not any(i for i in arrayel.texnodes_array if i.is_selected == True):
        arrayel.texnodes_array[0].is_selected = True

    print_debug(arrayel.texnodes_array)

    return

#Create UV card element in (CARDS2UV_cardsarray) with C2UV temporary material
def CheckMaterialInArray(array, material, create = True):
    ##Create Array Or Get Existed
    existedelement = [el for el in array if el.material == material]
    
    if (len(existedelement) > 0):
        existedelement = existedelement[0]
    else:
        if create == True:
            existedelement = array.add()
            existedelement.material = material
            existedelement.name = material.name

            for col in default_rgb_colors:
                cr = existedelement.colors.add()
                for i in range(4):
                    cr.color[i] = col[i]
            
        else:
            existedelement = None

    return existedelement

#Create or update shader nodes in C2UV temporary material
def CreateOrUpdateShaderNodes(uv_card, textures):
    nodes = uv_card.material.node_tree.nodes
    links = uv_card.material.node_tree.links

    nodeMinX = -2000
    nodeMaxY = -2000

    for node in nodes:
        nodeMinX = node.location.x if node.location.x < nodeMinX else nodeMinX
        nodeMaxY = node.location.y if node.location.y > nodeMaxY else nodeMaxY

    nodeMinX = nodeMinX - 500
    nodeMaxY = nodeMaxY + 500

    texCoordNode = None
    texCoordinate_output = None
    if nodes.find("C2UV_TextureCoord") < 0:

        if uv_card.mapping_mode == "UV":
            texCoordNode = nodes.new("ShaderNodeTexCoord")
        else:
            texCoordNode = nodes.new("ShaderNodeAttribute")


        texCoordNode.location = (nodeMinX, nodeMaxY)
        texCoordNode.name = "C2UV_TextureCoord"

    texCoordNode = nodes["C2UV_TextureCoord"]
    if (texCoordNode.type == 'TEX_COORD' and uv_card.mapping_mode == "ATTRIBUTE") or (texCoordNode.type == 'ATTRIBUTE' and uv_card.mapping_mode == "UV"):
        old_coords = texCoordNode.location

        nodes.remove(texCoordNode)

        if uv_card.mapping_mode == "UV":
            texCoordNode = nodes.new("ShaderNodeTexCoord")
        else:
            texCoordNode = nodes.new("ShaderNodeAttribute")


        texCoordNode.location = old_coords
        texCoordNode.name = "C2UV_TextureCoord"

    if uv_card.mapping_mode == "UV":
        texCoordinate_output = texCoordNode.outputs[2]
    else:
        texCoordNode.attribute_name = uv_card.attribute_mapping_name
        texCoordinate_output = texCoordNode.outputs[1]
        
    nodeMapping = None
    if nodes.find("C2UV_VectorMapping.000") < 0:
        nodeMapping = nodes.new("ShaderNodeMapping")
        nodeMapping.location = (nodeMinX + 400, nodeMaxY)
        nodeMapping.name = "C2UV_VectorMapping.000"
        nodeMapping.label = "Mapping.000"
    nodeMapping = nodes["C2UV_VectorMapping.000"]

    #SETTING OR CREATE RBG COLOR PICKER WITH NAME C2UV_COLOR IF FOUND
    rgb_node = next((i for i in nodes if i.label == "C2UV_COLOR"), None)

    if rgb_node is None:
        rgb_node = nodes.new("ShaderNodeRGB")
        rgb_node.location = (nodeMinX + 500, nodeMaxY)
        rgb_node.name = "C2UV_COLOR"
        rgb_node.label = "C2UV_COLOR"

    rgb_node.outputs['Color'].default_value = uv_card.color

    #imgTexture = next((i for i in nodes if "Image Texture" in i.name), None)
    #if imgTexture is not None:
    #    links.new(nodeMapping.outputs[0], imgTexture.inputs[0])
    nlinks = nodeMapping.outputs[0].links
    for l in nlinks:
        links.remove(l)

    for t in textures:
        if t.is_selected:
            try:
                node = nodes[t.node_name]
                links.new(nodeMapping.outputs[0], node.inputs[0])
            except:
                continue

    locationMathNode = None
    if nodes.find("C2UV_LocationMath.000") < 0:
        locationMathNode = nodes.new("ShaderNodeVectorMath")
        locationMathNode.location = (nodeMinX + 200, nodeMaxY - 100)
        locationMathNode.name = "C2UV_LocationMath.000"
        locationMathNode.label = "Location.000"
        #Set Central Point (input[0] - Central, input[1] - Moda)
        #Location Linking
        links.new(locationMathNode.outputs[0], nodeMapping.inputs[1])
    locationMathNode = nodes["C2UV_LocationMath.000"]
    
    ##TODONE: Operation And inputs Depend On Rotation!!!!!!!!!!!!!!!
    locationMathNode.operation = 'ADD'
    locationMathNode.inputs[0].default_value = [uv_card.central[0], uv_card.central[1], 0]
    
    modaX = uv_card.moda[0]# * -1 ##90 degrees minus-minus
    modaY = uv_card.moda[1] * -1

    if uv_card.rotation == rotation_dict["0"]:
        modaX = uv_card.moda[0] * -1
        modaY = uv_card.moda[1] * -1
    if uv_card.rotation == rotation_dict["180"]:
        modaX = uv_card.moda[0]
        modaY = uv_card.moda[1]
    elif uv_card.rotation == rotation_dict["270"]:
        modaX = uv_card.moda[0] * -1
        modaY = uv_card.moda[1]# * -1
    
    locationMathNode.inputs[1].default_value = [modaX, modaY, 0]

    scaleMathNode = None
    try:
        scaleMathNode = nodes["C2UV_ScaleMath.000"]
    except:
        scaleMathNode = nodes.new("ShaderNodeVectorMath")
        scaleMathNode.location = (nodeMinX + 200, nodeMaxY - 400)
        scaleMathNode.name = "C2UV_ScaleMath.000"
        scaleMathNode.label = "Scale.000"
        #Scale Linking
        links.new(scaleMathNode.outputs[0], nodeMapping.inputs[3])

    scaleX = uv_card.scale[1] ##Scale for 90 degrees
    scaleY = uv_card.scale[0] ## * -1

    if uv_card.rotation == rotation_dict["0"]:
        scaleX = uv_card.scale[0]
        scaleY = uv_card.scale[1]
    if uv_card.rotation == rotation_dict["180"]:
        scaleX = uv_card.scale[0]
        scaleY = uv_card.scale[1]
    #elif uv_card.rotation == rotation_dict["270"]:
    #    scaleX = uv_card.scale[1]
    #    scaleY = uv_card.scale[0]

    #Set Scale
    scaleMathNode.inputs[0].default_value = [scaleX, scaleY, 0]
    
    nodeMapping.inputs[2].default_value = [0, 0, uv_card.rotationcurrent]

    #for 
    links.new(texCoordinate_output, nodeMapping.inputs[0])

    return

#Re/Create or update card (CARDS2UV_uvelement) in array (CARDS2UV_cardsarray)
def CreateOrModifyCard(array, uv_obj, upd):

    uv_name = uv_obj[0]

    shortname = "C2UV.{:03}".format(uv_name)

    processedname = "{}_{}".format(array.material.name, shortname)


    ##Try Get Processed Name From Array
    uv_card = next((i for i in array.uv_array if i.material is not None and i.material.name == processedname), None)
    #findindex = array.uv_array.find(processedname)
    if uv_card is not None:
        uv_card = array.uv_array[processedname]
    else:
        uv_card = array.uv_array.add()

        uv_card.material = array.material.copy()
        uv_card.material.name = processedname
        uv_card.shortname = shortname

        uv_card.visiblename = uv_name
        
        uv_card.rotation = "1.570796"
        uv_card.rotationcurrent = 1.570796

        uv_card.name = processedname
        uv_card.groupname = uv_name

    #REINITIALIZE MATERIAL
    if upd == "RMAT":
        #Replace old C2UV material in GEO nodes!!! TODONE
        geo_setmaterial = []
        for geo in bpy.data.node_groups:
            set_mats = [i for i in geo.nodes if i.type == "SET_MATERIAL" and i.inputs[2].default_value == uv_card.material]
            for sm in set_mats:
                geo_setmaterial.append(sm)

        #Replace old C2UV material in object that used it (after reinitialize it)
        objectsToReplace = []
        for ob in bpy.data.objects:
            if ob.active_material is not None:
                if ob.active_material == uv_card.material:
                    #print("Object: {0}, Have Material: {1}".format(ob.name, originalMaterial.name))
                    ob.active_material = None
                    objectsToReplace.append(ob)

        if bpy.data.materials.find(uv_card.material.name) != -1:
            bpy.data.materials.remove(bpy.data.materials[uv_card.material.name])

        cpy = array.material.copy()
        if uv_card.material is None:
            cpy.name = processedname
        else:
            cpy.name = uv_card.material.name

        uv_card.material = cpy

        for ob in objectsToReplace:
            ob.active_material = uv_card.material

        for gsm in geo_setmaterial:
            gsm.inputs[2].default_value = uv_card.material

    uv = uv_obj[1]

    uv_card.central = uv[0]
    uv_card.moda = uv[1]
    uv_card.scale = uv[2]

    CreateOrUpdateShaderNodes(uv_card, array.texnodes_array)

    return

#Coords from Vertex Groups
def GetCoordsFromGroups(self):
    group_vertecies = []

    for v in bpy.context.object.data.vertices:
        for g in v.groups:
            v_group = bpy.context.object.vertex_groups[g.group]
            exist = next((x for x in group_vertecies if x[0] == v_group.name), None)
            
            if exist is None:
                group_vertecies.append([v_group.name, []])
                
                exist = group_vertecies[-1]
                
            exist[1].append(v.index)
            
    rect_groups = []
    #print(group_vertecies)

    for g in group_vertecies:
        verts = g[1]
        if len(verts) < 4:
            continue
        rect_groups.append(g)
        
    #print(rect_groups)
            
    me = bpy.context.object.data
    bm = bmesh.from_edit_mesh(me)

    group_coords = []

    bm.verts.ensure_lookup_table()
            
    for e in rect_groups:

        bpy.ops.mesh.select_all(action="DESELECT")

        for v in e[1]:
            bm.verts[v].select = True
            
        bm.select_flush_mode()

        #print(len([f for f in bm.faces if f.select]))
            
        uv_layer = bm.loops.layers.uv.verify()
        
        coords = []

        for face in [f for f in bm.faces if f.select]:
            for loop in face.loops:
                coords.append(loop[uv_layer].uv)
                
        if len(coords) != 0:
            group_coords.append([e[0], coords])

    return group_coords

def CalculateCoordsVariables(self, coords):
    min_coord = Vector((100, 100))
    max_coord = Vector((-100, -100))

    for n, item in enumerate(coords):
        min_coord.x = item.x if min_coord.x > item.x else min_coord.x
        min_coord.y = item.y if min_coord.y > item.y else min_coord.y

        max_coord.x = item.x if max_coord.x < item.x else max_coord.x
        max_coord.y = item.y if max_coord.y < item.y else max_coord.y

    central_coord = Vector(((min_coord.x + max_coord.x) / 2 , (min_coord.y + max_coord.y) / 2))
    scale_coord = Vector((max_coord.x - min_coord.x, max_coord.y - min_coord.y))
    moda_coord = Vector((max_coord.x - central_coord.x, max_coord.y - central_coord.y))

    return [central_coord, moda_coord, scale_coord]


#Create or update C2UV array (CARDS2UV_cardsarray)
def CARDS2UV_CreateArray(self, context, upd):
    print_debug("Execution CARDS2UV_GetUVShells started")
    obj = context.object
    me = obj.data

    calledmode = context.object.mode

    C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

    selectedobject = bpy.context.selected_objects[0]

    if selectedobject.active_material is None:
        print_debug("Doesn't Have Material")
        return {"FINISHED"}
    
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

    #BMESH WONT WORK WITHOUT IT
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

    originalMaterial = selectedobject.active_material
    arrayelement = CheckMaterialInArray(C2UV_UVCardsArray, originalMaterial, True)
    arrayelement.from_object = selectedobject
    #if upd in ["RMAT"]:
    create_or_modify_textures_names(arrayelement)
    
    obj_uv_array = []

    groups_coords = GetCoordsFromGroups(self)

    #If mesh doesn't contains correct vert groups, then use all faces method
    if len(groups_coords) == 0:
        #print_debug("Use old method")
        arrayelement.creation_mode = "ALLFACES"
        
        bm = bmesh.from_edit_mesh(me)
        bpy.ops.mesh.select_all(action="DESELECT")

        index = 0

        for face in bm.faces:
            face.select = True

            uv_layer = bm.loops.layers.uv.verify()
            coords = []

            for face in [f for f in bm.faces if f.select]:
                for loop in face.loops:
                    coords.append(loop[uv_layer].uv)

            obj_uv_array.append([index, CalculateCoordsVariables(self, coords)])
            
            index += 1
            face.select = False

        obj_uv_array = sorted(obj_uv_array, key=lambda k: [k[1][0].x, k[1][0].y])
    else:
        #print_debug("Use new method")
        arrayelement.creation_mode = "VERTEXGROUP"

        for grc in groups_coords:
            obj_uv_array.append([grc[0], CalculateCoordsVariables(self, grc[1])])

    for i, uv in enumerate(obj_uv_array):
        CreateOrModifyCard(arrayelement, uv, upd)

    #context.scene.C2UV_UVCardsArray.add()
    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode=calledmode)

    return arrayelement

#Operator: UI button for create array (CARDS2UV_cardsarray) from object with on active_material
class CARDS2UV_CreateUVArray(bpy.types.Operator):
    bl_label = "Create Array"
    bl_idname = "cards2uv.create_uv_array"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Checks to see if there's any active mesh object (selected or in edit mode)
        return len(context.selected_objects) == 1 and context.selected_objects[0].active_material is not None and "_C2UV" not in context.selected_objects[0].active_material.name

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        elem = CARDS2UV_CreateArray(self, context, "RMAT")

        arr = next((i for i in C2UV_UVCardsArray if i == elem), None)
        if arr is not None:
            bpy.ops.cards2uv.apply_card_color(array_index=0, update_mode='ARRAY')

        return {"FINISHED"}

#Operator: Delete array (CARDS2UV_cardsarray)
class CARDS2UV_ClearCollections(bpy.types.Operator):
    bl_label = "Clear Array"
    bl_idname = "cards2uv.clear_collections"
    bl_options = {'REGISTER', 'UNDO'}

    index : IntProperty(name="Array to clear", options={'HIDDEN'})
    delete_mark : BoolProperty(name="Delete mark", default=False)

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray
        clo = context.scene.C2UV_UVCardsArray[self.index]
        
        if self.delete_mark:
            for u in clo.uv_array:
                if u.material is not None:
                    bpy.data.materials.remove(u.material)
            clo.uv_array.clear()

            C2UV_UVCardsArray.remove(self.index)

        return {"FINISHED"}

#Operator: Flip curves
class CARDS2UV_fixcurvedirection(bpy.types.Operator):
    bl_idname = "cards2uv.fix_curve_direction"
    bl_label = "Switch direction and rotate selected curve"
    bl_description = "Switch direction and rotate selected curve by 180 degree"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

        bpy.ops.curve.select_linked()
        bpy.ops.curve.switch_direction()
        bpy.ops.transform.tilt(value=3.14159)

        return {"FINISHED"}

#Get resample geonode
def getresamplenode(self, str, resampletimes):
    nodegr = None

    if bpy.data.node_groups.find(str) < 0:
        nodegr = bpy.data.node_groups.new(str, "GeometryNodeTree")
        
        #node = bpy.data.node_groups[str]
        nodegr.inputs.new('NodeSocketGeometry', 'Curves')
        nodegr.inputs.new('NodeSocketInt', 'ResampleTimes')
        nodegr.outputs.new('NodeSocketGeometry', 'Curves')

        nodegr.nodes.clear()
        input = nodegr.nodes.new("NodeGroupInput")

        resmpl = nodegr.nodes.new("GeometryNodeResampleCurve")
        resmpl.location.x += 1000

        output = nodegr.nodes.new("NodeGroupOutput")
        output.location.x += 2000

        links = nodegr.links
        links.new(input.outputs[0], resmpl.inputs[0])
        links.new(input.outputs[1], resmpl.inputs[2])
        links.new(resmpl.outputs[0], output.inputs[0])
        
    nodegr = bpy.data.node_groups[str]
    nodegr.inputs['ResampleTimes'].default_value = resampletimes

    return nodegr

#Get subdividion geonode
def getresubdivitionnode(self, str, subdividetimes):
    nodegr = None

    if bpy.data.node_groups.find(str) < 0:
        nodegr = bpy.data.node_groups.new(str, "GeometryNodeTree")
        
        #node = bpy.data.node_groups[str]
        nodegr.inputs.new('NodeSocketGeometry', 'Curves')
        nodegr.inputs.new('NodeSocketInt', 'SubdivitionTimes')
        nodegr.outputs.new('NodeSocketGeometry', 'Curves')

        nodegr.nodes.clear()
        input = nodegr.nodes.new("NodeGroupInput")

        sbdv = nodegr.nodes.new("GeometryNodeSubdivisionSurface")
        sbdv.location.x += 1000

        output = nodegr.nodes.new("NodeGroupOutput")
        output.location.x += 2000

        links = nodegr.links
        links.new(input.outputs[0], sbdv.inputs[0])
        links.new(input.outputs[1], sbdv.inputs[1])
        links.new(sbdv.outputs[0], output.inputs[0])
    
    nodegr = bpy.data.node_groups[str]
    nodegr.inputs['SubdivitionTimes'].default_value = subdividetimes

    return nodegr

def GetInterpolatedIndex(sarray_len, tarray_len, target_index):

    if target_index == tarray_len - 1 or target_index > tarray_len - 1:
        return tarray_len - 1

    kof = tarray_len / sarray_len

    interpol_index = round(kof * target_index)

    return interpol_index

#Operation: Update selected curves (tilt, resample, subdivition, extrude)
class CARDS2UV_UpdateSelectedCurves(bpy.types.Operator):
    bl_idname = "cards2uv.update_curves"
    bl_label = "Update selected curves"
    bl_description = "Update selected curves resample/extrude/subdivition"
    bl_options = {'REGISTER', 'UNDO'}

    resample_times : IntProperty(name="Resample Count", min=2, default=10)

    enable_extrude : BoolProperty(name="Enable extrude (Add to current)", default=False, options={'SKIP_SAVE'})
    replace_extrude : BoolProperty(name="Change extrude mode to replace", default=False, options={'SKIP_SAVE'})
    extrude_size : FloatProperty(name="Extrude", min=0, unit="LENGTH")

    subdivide_times : IntProperty(name="Subdivition Count", min=0, default=2)

    enable_tilt : BoolProperty(name="Enable tilt (Add to current)", default=False, options={'SKIP_SAVE'})
    replace_tilt : BoolProperty(name="Change tilt mode to replace", default=False, options={'SKIP_SAVE'})
    tiltvalue : FloatProperty(name="Tilt", default=0)

    reset_radius : BoolProperty(name="Reset radius value", default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        selected_coll = context.selected_objects.copy()

        for o in selected_coll:
            if o.type not in ['CURVE']:
                continue

            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')

            bpy.context.view_layer.objects.active = o

            o.select_set(True)

            #context.view_layer.objects.active = sel

            prev_extrude = o.data.extrude

            splns = o.data.splines
            spline_points = []
            for s in splns:
                points_data = []

                if len(s.points) > 0:
                    for p in s.points:
                        points_data.append([p.tilt, p.radius])
                
                    spline_points.append([s.points[0].co, points_data])

                if len(s.bezier_points) > 0:
                    for p in s.bezier_points:
                        points_data.append([p.tilt, p.radius])
                
                    spline_points.append([s.bezier_points[0].co, points_data])

            prevmat = None
            if o.active_material is not None:
                prevmat = o.active_material

            o.data.extrude = 0

            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

            #Copy original object for Modifiers
            #source_obj = o.copy()
            #source_obj = o.data.copy()
            #source_obj.animation_data_clear()

            C = bpy.context

            source_obj = o.copy()
            source_obj.data = o.data.copy()
            source_obj.animation_data_clear()

            C.collection.objects.link(source_obj)

            source_obj.select_set(False)

            enabled_modifiers = []
            #Disable and store all GN modifiers
            for m in o.modifiers:
                if m.type in ["NODES"] and m.show_viewport:
                    m.show_viewport = False
                    enabled_modifiers.append(m.name)

            bpy.ops.object.convert(target='MESH')
            bpy.ops.object.convert(target='CURVE')

            bpy.ops.object.modifier_add(type='NODES')
            g = bpy.context.object.modifiers["GeometryNodes"]
            g.node_group = getresamplenode(self, "C2UV_ResampleCurves", self.resample_times)

            bpy.ops.object.convert(target='MESH')
            bpy.ops.object.convert(target='CURVE')

            bpy.ops.object.shade_smooth()

            #bpy.ops.object.editmode_toggle()
            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

            o.data.extrude = prev_extrude
            if self.enable_extrude:
                o.data.extrude += self.extrude_size
                if self.replace_extrude:
                    o.data.extrude = self.extrude_size

            splns = o.data.splines
            #Find nearest first point
            for s in splns:
                first_point = s.points[0].co
                
                matched_spline = next((x for x in spline_points if x[0] == first_point), None)
                if matched_spline is not None:
                    for index, elem in enumerate(s.points):
                        #print(f'Index --- {index}  Point tilt --- {matched_spline}')

                        interp_index = GetInterpolatedIndex(len(s.points), len(matched_spline[1]), index)

                        elem.tilt = matched_spline[1][interp_index][0]
                        if self.enable_tilt:
                            elem.tilt += self.tiltvalue
                            if self.replace_tilt:
                                elem.tilt = self.tiltvalue

                        elem.radius = matched_spline[1][interp_index][1]
                        if self.reset_radius:
                            elem.radius = 1
                        
            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

            with bpy.context.temp_override(object=source_obj, selected_objects=(source_obj, o)):
                bpy.ops.object.make_links_data(type='MODIFIERS')

            bpy.data.objects.remove(source_obj, do_unlink=True)

            #bpy.ops.object.modifier_add(type='NODES')
            #g = bpy.context.object.modifiers["GeometryNodes"]
            #g.node_group = getresubdivitionnode(self, "C2UV_Subdivition", self.subdivide_times)
            for em in enabled_modifiers:
                o.modifiers[em].show_viewport = True

            if prevmat is not None:
                o.active_material = prevmat

        return {"FINISHED"}

#Operation: Convert selected edge loops to curve
class CARDS2UV_meshtokurvas(bpy.types.Operator):
    bl_idname = "cards2uv.mesh_to_curves"
    bl_label = "Convert mesh to curves by selected edges"
    bl_description = "Convert mesh to curves by selected edges (expand by loop select)"
    bl_options = {'REGISTER', 'UNDO'}

    resample_times : IntProperty(name="Resample Count", min=2, default=10)
    extrude_size : FloatProperty(name="Extrude", min=0, unit="LENGTH")
    subdivide_times : IntProperty(name="Subdivition Count", min=0, default=2)

    tiltvalue : IntProperty(name="Tilt", default=90)

    def execute(self, context):
        bpy.ops.mesh.loop_multi_select(ring=False)
        bpy.ops.mesh.select_all(action='INVERT')
        
        bpy.ops.mesh.loop_multi_select(ring=False)
        bpy.ops.mesh.delete(type='EDGE')

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

        bpy.ops.object.convert(target='CURVE')

        bpy.ops.object.modifier_add(type='NODES')
        g = bpy.context.object.modifiers["GeometryNodes"]
        g.node_group = getresamplenode(self, "C2UV_ResampleCurves", self.resample_times)

        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.convert(target='CURVE')

        bpy.ops.object.editmode_toggle()
        bpy.ops.curve.select_all(action='SELECT')

        bpy.ops.transform.tilt(value=math.radians(self.tiltvalue))
        context.object.data.extrude = self.extrude_size

        ##CANCER: EXTREME MONKE CODE WARNING
        #Flip first curve
        bpy.ops.curve.select_nth(skip=100, nth=1, offset=0)
        bpy.ops.curve.select_all(action='INVERT')
        CARDS2UV_fixcurvedirection.execute(self, bpy.context)
        bpy.ops.curve.select_all(action='SELECT')

        bpy.ops.object.editmode_toggle()
        bpy.ops.object.shade_smooth()

        bpy.ops.object.modifier_add(type='NODES')
        g = bpy.context.object.modifiers["GeometryNodes"]
        g.node_group = getresubdivitionnode(self, "C2UV_Subdivition", self.subdivide_times)

        bpy.ops.object.editmode_toggle()

        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')

        return {"FINISHED"}

class CARDS2UV_Curve_RandomTilt(bpy.types.Operator):
    bl_idname = "cards2uv.curve_random_tilt"
    bl_label = "Set Random Tilt For Curves"
    bl_description = "Set Random Tilt For Selected/All Curves"
    bl_options = {'REGISTER', 'UNDO'}

    random_seed : IntProperty(name="Random Seed")

    tilt_value : FloatProperty(name="Tilt Value", min=0.0, default=0.261799, subtype="ANGLE")

    points_jitter : BoolProperty(name="Segments Jitter", default=False)

    apply_side : EnumProperty(name="Tilt Side",  
        items=[
            ("BOTH", "BOTH", "", "ARROW_LEFTRIGHT", 1),
            ("POSITIVE", "Positive", "", "ADD", 2),
            ("NEGATIVE", "Negative", "", "REMOVE", 3),
            ],
        default="BOTH"
    )

    @classmethod
    def poll(cls, context):
        return any([ob for ob in context.selected_objects if ob.type in ['CURVE']])

    def execute(self, context):
        random.seed(self.random_seed)

        ob = context.object
        me = ob.data

        if bpy.context.mode in ['OBJECT']:
            for selo in context.selected_objects:
                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

                context.view_layer.objects.active = selo
                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

                if selo.type not in ['CURVE']:
                    continue

                me = selo.data
                
                for spline in me.splines:
                    if self.points_jitter:
                        for point in spline.points:
                            tilt_diff = point.tilt
                            
                            if self.apply_side == "BOTH":
                                tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * random.choice([-1, 1]))
                            else:
                                tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * 1 if self.apply_side == "POSITIVE" else -1)

                            point.tilt = tilt_diff
                            print_debug(f"Max Value: {self.tilt_value}  ----- Current tilt: {tilt_diff}")
                    else:
                        tilt_diff = spline.points[0].tilt
                        if self.apply_side == "BOTH":
                            tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * random.choice([-1, 1]))
                        else:
                            tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * 1 if self.apply_side == "POSITIVE" else -1)
                        
                        for point in spline.points:
                            point.tilt = tilt_diff

            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

        elif bpy.context.mode in ['EDIT_CURVE']:
            selected_splines = [spl for spl in me.splines if any(p for p in spl.points if p.select)]
            selected_points = []
            for spline in selected_splines:
                selected_points = selected_points + [p for p in spline.points if p.select == True]

            for spline in selected_splines:
                if self.points_jitter:
                    for point in selected_points:
                        tilt_diff = point.tilt
                        
                        if self.apply_side == "BOTH":
                            tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * random.choice([-1, 1]))
                        else:
                            tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * 1 if self.apply_side == "POSITIVE" else -1)

                        point.tilt = tilt_diff
                        print_debug(f"Max Value: {self.tilt_value}  ----- Current tilt: {tilt_diff}")
                else:
                    tilt_diff = spline.points[0].tilt
                    if self.apply_side == "BOTH":
                        tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * random.choice([-1, 1]))
                    else:
                        tilt_diff = tilt_diff + (random.uniform(0.0, self.tilt_value) * 1 if self.apply_side == "POSITIVE" else -1)
                    
                    for point in selected_points:
                        point.tilt = tilt_diff

            #for point in selected_points:
            #    point.select = True
            

        return {'FINISHED'}
    
class CARDS2UV_Curves_ConvertToPaths(bpy.types.Operator):
    bl_idname = "cards2uv.curvestopaths"
    bl_label = "Convert CURVES hair to paths"
    bl_description = "Convert CURVES hair system to regular paths curves"
    bl_options = {'REGISTER', 'UNDO'}

    keep_source : BoolProperty(name="Keep source hair system", default=True)

    #def poll(cls, context):
    #    return any([ob for ob in context.selected_objects if ob.type in ['CURVES']])
    
    def execute(self, context):
        source_selected = context.selected_objects.copy()
        #obj = bpy.context.object

        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

        for sel_object in source_selected:
            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

            context.view_layer.objects.active = sel_object
            if self.keep_source:
                prev_obj = sel_object
                bpy.ops.object.duplicate(linked=True)
                prev_obj.hide_set(True)

            obj = context.view_layer.objects.active

            if sel_object.type in ['CURVES']:
                source_obj = obj.copy()
                source_obj.data = obj.data.copy()
                source_obj.animation_data_clear()

                context.collection.objects.link(source_obj)

                source_obj.select_set(False)

                enabled_modifiers = []
                #Disable and store all GN modifiers
                for m in obj.modifiers:
                    if m.type in ["NODES"] and m.show_viewport:
                        print_debug(f'SET DISABLED {m.name}')
                        m.show_viewport = False
                        enabled_modifiers.append(m.name)

                bpy.ops.object.convert(target='MESH')
                bpy.ops.object.convert(target='CURVE')

                with bpy.context.temp_override(object=source_obj, selected_objects=(source_obj, obj)):
                    bpy.ops.object.make_links_data(type='MODIFIERS')

                bpy.data.objects.remove(source_obj, do_unlink=True)

                for em in enabled_modifiers:
                    obj.modifiers[em].show_viewport = True

        return {'FINISHED'} 




def MirrorFaceArray(context, face_array, orientation, axis):
    prev_area = context.area.type

    obj = context.object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()

    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

    #bpy.ops.mesh.reveal()

    bpy.ops.mesh.select_all(action='DESELECT')

    for face in face_array:
        bmface = bm.faces[face]
        bmface.select = True
    
    uvs = obj.data.uv_layers

    #Set C2UV BackUP Layout As Active
    if uvs.find('C2UV_BackUP') > -1:
        uvs.active = uvs['C2UV_BackUP']
    elif uvs.find('C2UVMap') > -1:
        uvs.active = uvs['C2UVMap']
    elif uvs.find('UVMap') > -1:
        uvs.active = uvs['UVMap']
    elif len(uvs) > 0:
        uvs.active = uvs[0]
    else:
        uvs.new("UVMap")
        uvs.active = uvs[0]

    context.area.ui_type = 'UV'

    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

    bpy.ops.uv.select_all(action='SELECT')

    if uvs.active.name == 'C2UV_BackUP':
        reverse_axis = (axis[1], axis[0], axis[2]) #It Just Works
        bpy.ops.transform.mirror(orient_type=orientation, constraint_axis=reverse_axis)
    else:
        bpy.ops.transform.mirror(orient_type=orientation, constraint_axis=axis)

    if uvs.find('C2UVMap') > -1:
        uvs.active = uvs['C2UVMap']
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.transform.mirror(orient_type=orientation, constraint_axis=axis)

    context.area.ui_type = prev_area

def GetSeparatedShellsFromActiveObject(context, selected_object = None):
    shells_array = []
    
    obj = None
    if selected_object is not None:
        obj = selected_object
    else:
        obj = context.object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()

    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

    #Get Selected faces and store it
    faces_ori_selected = [f for f in bm.faces if f.select == True]

    faces_processed = []
    for face in faces_ori_selected:

        #Face Already processed
        if face.index in faces_processed:
            continue

        bpy.ops.mesh.select_all(action='DESELECT')

        #Select Only One Face Then Get Linked To It (It is whole UV shell for separated mesh)
        face.select = True

        bpy.ops.mesh.select_linked()

        #Store All Linked Faces
        temparr = [f.index for f in bm.faces if f.select == True]
        shells_array.append(temparr)
        
        #Append Processed Face Array
        faces_processed = faces_processed + temparr

    return shells_array

class CARDS2UV_Mesh_MirrorUV(bpy.types.Operator):
    bl_idname = "cards2uv.mirror_mesh_uv"
    bl_label = "Mirror selected mesh UV"
    bl_description = "Mirror selected mesh UV and applies on next card"
    bl_options = {'REGISTER', 'UNDO'}

    orientation : EnumProperty(name="Orientation",
        items=[
            ("GLOBAL", "Global", "", "ORIENTATION_GLOBAL", 1),
            ("LOCAL", "Local", "", "ORIENTATION_LOCAL", 2),
            ("NORMAL", "Normal", "", "ORIENTATION_NORMAL", 3),
            ("GIMBAL", "Gimbal", "", "ORIENTATION_GIMBAL", 4),
            ("VIEW", "View", "", "ORIENTATION_VIEW", 5),
            ("CURSOR", "Cursor", "", "ORIENTATION_CURSOR", 6),
            ]
    )

    axis : BoolVectorProperty(name="Constraint Axis", subtype="XYZ", default=(True, False, False))

    random_enabled : BoolProperty(name="Enable Random", default=False)

    random_seed : IntProperty(name="Random Seed")

    random_threshold : FloatProperty(name="Random Threshold", min=0.0, max=1.0, default=0.5)

    #Check Mesh In Selected Pool
    @classmethod
    def poll(cls, context):
        #return True
        return context.object.type in ['MESH']
        #return any(o for o in context.selected_objects if o.type in ['MESH'])

    def execute(self, context):
        shells = []
        prev_mode = context.mode

        random.seed(self.random_seed)

        if context.mode in ['OBJECT']:

            for sel in context.selected_objects:
                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

                context.view_layer.objects.active = sel

                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

                bpy.ops.mesh.select_all(action='SELECT')

                shells = GetSeparatedShellsFromActiveObject(context)

                for shell in shells:
                    if not self.random_enabled or random.random() >= self.random_threshold:
                        MirrorFaceArray(context, shell, self.orientation, self.axis)


        elif context.mode in ['EDIT_MESH']:
            shells = GetSeparatedShellsFromActiveObject(context)

            for shell in shells:
                if not self.random_enabled or random.random() >= self.random_threshold:
                    MirrorFaceArray(context, shell, self.orientation, self.axis)

        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

        obj = context.object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        bm.faces.ensure_lookup_table()

        for shell in shells:
            for elem in shell:
                bm.faces[elem].select = True
        
        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')
        if prev_mode == 'EDIT_MESH':
            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

        return {"FINISHED"}

#Panel: Panel with curves operators
class additional_panel(bpy.types.Panel):
    bl_label = "Object 2 Curves"
    bl_idname = "CARDS_UV_layout_additional"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cards 2 UV"

    def draw(self, context):
        layout = self.layout
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        layout.row().label(text="Objects Actions", icon="LIGHTPROBE_CUBEMAP")

        if context.object is not None and len(context.selected_objects) > 0:
            #CurvesParameters
            kurvaParameterRow = layout.row()
            kurvaCol = layout.column()
            #kurvaParameterRow.label(text="Kurvas Actions", icon="OUTLINER_OB_CURVE")
            if context.object.mode in ["EDIT"]:
                
                if context.selected_objects[0].type in ['MESH']:
                    kurvaCol.operator("cards2uv.mesh_to_curves", text="Mesh to curves")
                    

            if context.object.mode in ["EDIT", "OBJECT"]:

                if any(o for o in context.selected_objects if o.type in ['CURVE']):
                    kurvaCol.operator("cards2uv.fix_curve_direction", text="Flip(fix) curves direction")
                    kurvaCol.operator("cards2uv.update_curves", text="Update curves")
                    kurvaCol.operator("cards2uv.curve_random_tilt", text="Curves tilt jitter")

                if any(o for o in context.selected_objects if o.type in ['MESH']):
                    kurvaCol.operator("cards2uv.mirror_mesh_uv", text="Mirror mesh UV")

                if any(o for o in context.selected_objects if o.type in ['CURVES']):
                    kurvaCol.operator("cards2uv.curvestopaths", text="Hair to curves")

        layout.row().operator("gpencil.surfsk_annotations_to_curves", text="Annotation to curves")

#Index callculation for forward/reverse operation
def indexmath(index, total, forward):
    if forward:
        forward_index = index + 1
        if forward_index >= total:
            return 0
        return forward_index
    else:
        reverse_index = index - 1
        if reverse_index < 0:
            return total - 1
        return reverse_index

def SeparateSplines(context, parentobject, random_threshold):
    return

class CARDS2UV_Array_RandomizeCards(bpy.types.Operator):
    bl_label = "Set Random Cards"
    bl_idname = "cards2uv.randomize_cards"
    bl_options = {'REGISTER', 'UNDO'}

    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})

    #separate_splines : BoolProperty(name="Separate splines", default=False)

    separate_meshes : BoolProperty(name="Separate meshes", default=False)

    random_seed : IntProperty(name="Random Seed", default=0)

    random_threshold : FloatProperty(name="Random Threshold", min=0.0, max=1.0, default=1)

    @classmethod
    def poll(cls, context):
        # Checks to see if there's any active mesh object (selected or in edit mode)
        return len(context.selected_objects) > 0

    def execute(self, context):
        random.seed(self.random_seed)

        cardsarray = context.scene.C2UV_UVCardsArray[self.array_index]
        prevmode = context.mode

        selobjects = context.selected_objects
        activeobject = context.active_object
        if activeobject is None:

            activeobject = context.selected_objects[0]

        selectedcards = [i for i in cardsarray.uv_array if i.is_selected]
        if len(selectedcards) == 0:
            selectedcards = cardsarray.uv_array

        if prevmode in ['OBJECT']:
            #Separate to curve and mesh types
            curves = [i for i in selobjects if i.type == 'CURVE']
            meshes = [i for i in selobjects if i.type == 'MESH']

            #Clear Selected
            last = None
            for selindex, selo in enumerate(context.selected_objects):
                if last is not None:
                    last.select_set(False)
                last = selo

            for curve in curves:
                me = curve.data

                context.view_layer.objects.active = curve

                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

                if random.random() <= self.random_threshold:
                    indexcard = random.choice(selectedcards)
                    intindex = cardsarray.uv_array.find(indexcard.name)

                    bpy.ops.cards2uv.apply_card_ui(array_index=self.array_index, element_index=intindex, from_object=curve.name)

            for mesh in meshes:
                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')
                #bpy.ops.object.select_all(action='DESELECT')

                #mesh.select_set(True)

                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')
                
                bpy.ops.mesh.select_all(action='SELECT')
                context.view_layer.objects.active = mesh
                
                shells = GetSeparatedShellsFromActiveObject(context)
                #print_debug(f"Mesh shells list: {shells}")

                for shell in shells:
                    obj = context.active_object
                    me = obj.data
                    bm = bmesh.from_edit_mesh(me)
                    bm.faces.ensure_lookup_table()

                    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

                    bpy.ops.mesh.reveal()

                    bpy.ops.mesh.select_all(action='DESELECT')

                    for face in shell:
                        bmface = bm.faces[face]
                        bmface.select = True

                    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')
                    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

                    #print_debug(f"SELECT: {shell}")

                    if random.random() <= self.random_threshold:
                        indexcard = random.choice(selectedcards)
                        intindex = cardsarray.uv_array.find(indexcard.name)

                        bpy.ops.cards2uv.apply_card_ui(array_index=self.array_index, element_index=intindex)

                        #bpy.ops.cards2uv.apply_card_ui(array_index=self.array_index, element_index=indexcard)

                    #indexcard = random.choice(range(len(selectedcards)))
                    

            bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

#        elif prevmode in ['EDIT_MESH']:
#            return {'CANCELLED'}
#        elif prevmode in ['EDIT_CURVE']:
#            return {'CANCELLED'}
        
        return {'FINISHED'}

#Operator: Change card index button by indexmath
class CARDS2UV_Array_ChangeCardIndex(bpy.types.Operator):
    bl_label = "Pick Forward UV Shell"
    bl_idname = "cards2uv.change_uv_card_index"
    bl_options = {'REGISTER', 'UNDO'}

    is_forward : BoolProperty(name="Direction", options={'HIDDEN'}, default=True)

    @classmethod
    def poll(cls, context):
        # Checks to see if there's any active mesh object (selected or in edit mode)
        return len(context.selected_objects) > 0 and any(o for o in context.selected_objects if o.type in ['CURVE'])

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray
        for o in context.selected_objects:
            currmat = o.active_material

            done = False
            for arrayindex, arr in enumerate(C2UV_UVCardsArray):
                for c, currcard in enumerate(arr.uv_array):
                    if currcard.material != currmat:
                        continue

                    uv_card_index = indexmath(c, len(arr.uv_array), self.is_forward)

                    bpy.ops.cards2uv.apply_card_ui(array_index=arrayindex, element_index=uv_card_index, from_object=o.name)
                    done = True
                    break
                
                if done:
                    break

        return {"FINISHED"}

#Operator: Update UV array (CARDS2UV_cardsarray) button
class CARDS2UV_Array_UpdateArrayUI(bpy.types.Operator):
    bl_label = "Update UV Shells Array"
    bl_idname = "cards2uv.update_uv_array_ui"
    bl_options = {'REGISTER', 'UNDO'}

    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})
    update_switch : EnumProperty(name="Which To Update",
    items=[
        ("UMAT", "Update materials data", "Only update shader nodes created by C2UV"),
        ("RMAT", "Reinitialize materials", "Delete and replace materials with current created")
    ])

    #updateobject : StringProperty(name="Object to update", options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        upd = C2UV_UVCardsArray[self.array_index].from_object

        previousselected = context.selected_objects
        previousactive = context.view_layer.objects.active

        bpy.context.view_layer.objects.active = upd

        array_selection_object(previousselected, False)

        upd.select_set(True)

        if len(context.selected_objects) > 0 and context.selected_objects[0] == upd:
            CARDS2UV_CreateArray(self, context, self.update_switch)

        upd.select_set(False)

        array_selection_object(previousselected, True)
        context.view_layer.objects.active = previousactive

        return {"FINISHED"}

#Operator: Button which select and unhide object where created UV array (CARDS2UV_cardsarray)
class CARDS2UV_Array_SelectArrayUI(bpy.types.Operator):
    bl_label = "Select UV Shells Array"
    bl_idname = "cards2uv.select_uv_array_ui"
    bl_options = {'REGISTER', 'UNDO'}

    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})
    #updateobject : StringProperty(name="Object to update", options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        array_selection_object(context.selected_objects, False)
        obj = C2UV_UVCardsArray[self.array_index].from_object
        
        obj.hide_set(False)
        #WTF blender
        obj.select_set(False)
        obj.select_set(True)

        if context.area.type == "VIEW_3D":
            bpy.ops.view3d.view_selected()

        bpy.context.view_layer.objects.active = obj
        return {"FINISHED"}
    
#Operator: Button which select and unhide object where created UV array (CARDS2UV_cardsarray)
class CARDS2UV_Card_SelectGroupUI(bpy.types.Operator):
    bl_label = "Select Card Assigned Vertex"
    bl_idname = "cards2uv.select_group_ui"
    bl_options = {'REGISTER', 'UNDO'}

    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})
    element_index : IntProperty(name="UV Element Index", options={'HIDDEN'})
    #updateobject : StringProperty(name="Object to update", options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')

        array_selection_object(context.selected_objects, False)

        arr = C2UV_UVCardsArray[self.array_index]
        obj = arr.from_object
        elem = arr.uv_array[self.element_index]
        
        obj.hide_set(False)
        #WTF blender
        obj.select_set(False)
        obj.select_set(True)

        if context.area.type == "VIEW_3D":
            bpy.ops.view3d.view_selected()

        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')

        bpy.ops.mesh.select_all(action='DESELECT')

        bpy.ops.object.vertex_group_set_active(group=elem.groupname)

        bpy.ops.object.vertex_group_select()

        return {"FINISHED"}
    
def ApplyUVCoordsEditMode(context, arr, card):
    #Get Original Selected
    selected_orig = context.selected_objects.copy()
    active_orig = context.active_object

    for f in selected_orig:
        any([v for v in f.data.vertices])

    bpy.ops.mesh.select_linked()

    bpy.ops.mesh.separate(type='SELECTED')

    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')
    
    selected_diff = [x for x in context.selected_objects.copy() if x not in selected_orig]
    #for ob in selected_diff:
    #    ob.select_set(True)

    for ob in selected_diff:
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)

        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        ApplyUVCoordsFromCard(ob, [card], is_array_mat=True, already_selected=True)
        
    active_orig.select_set(True)
    context.view_layer.objects.active = active_orig
    #context.active_object = active_orig

    bpy.ops.object.join()

    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')

    return

#Operator: Button which apply hair card for object/s
class CARDS2UV_Card_ApplyCardUI(bpy.types.Operator):
    bl_label = "Apply Card (Curve or Mesh)"
    bl_idname = "cards2uv.apply_card_ui"
    bl_options = {'REGISTER', 'UNDO'}

    #materialname : StringProperty(name="Material Name", options={'HIDDEN'})
    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})
    element_index : IntProperty(name="UV Element Index", options={'HIDDEN'})
    #Yo Stupid blender
    from_object : StringProperty(name="Object Name", default="", options={'HIDDEN'})

    def execute(self, context):
        #material = bpy.data.materials[self.materialname]
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        arr = C2UV_UVCardsArray[self.array_index]
        elem = arr.uv_array[self.element_index]
        
        if self.from_object == "":
            for ob in context.selected_objects:
                if ob.active_material != arr.material:
                    ob.active_material = elem.material
                    ob.color = elem.color
                else:
                    if context.mode in ['OBJECT']:
                        #ApplyUVCoordsFromCard(context, arr, elem, [ob])
                        ApplyUVCoordsFromCard(ob, [elem], is_array_mat=True)
                        ReplaceMaterialSlots(ob, arr.material)
                    if context.mode in ['EDIT_MESH']:
                        ApplyUVCoordsEditMode(context, arr, elem)

                geos = [g for g in ob.modifiers if g.type == "NODES" and g.show_viewport == True]
                for geo in geos:
                    mats = [m for m in geo.node_group.nodes if m.mute == False and m.type == "SET_MATERIAL"]
                    for m in mats:
                        #print("_C2UV" in m.inputs[2].default_value.name)
                        if len(m.inputs[2].links) == 0 and m.inputs[2].default_value is not None and "_C2UV" in m.inputs[2].default_value.name:
                            m.inputs[2].default_value = elem.material

        else:
            obj = bpy.data.objects[self.from_object]
            obj.active_material = elem.material
            obj.color = elem.color

            geos = [g for g in obj.modifiers if g.type == "NODES" and g.show_viewport == True]
            for geo in geos:
                mats = [m for m in geo.node_group.nodes if m.mute == False and m.type == "SET_MATERIAL"]
                for m in mats:
                    if len(m.inputs[2].links) == 0 and "_C2UV" in m.inputs[2].default_value:
                        m.inputs[2].default_value = elem.material

        return {"FINISHED"}

#Operator: Update Coordinate Mode/Attribute Name For All Cards
class CARDS2UV_Array_SetCardsMode(bpy.types.Operator):
    bl_label = "Set cards mode"
    bl_idname = "cards2uv.set_cards_mode"
    bl_options = {'REGISTER', 'UNDO'}

    switch_mode : bpy.props.BoolProperty(name= "Switch mode coords/attr name", default= False, options={'HIDDEN'})

    selection_mode : bpy.props.BoolProperty(name= "Apply only on selected", default= False)

    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        arrayel = C2UV_UVCardsArray[self.array_index]

        objs = arrayel.uv_array
        if self.selection_mode:
            objs = [i for i in objs if i.is_selected]

        for el in objs:
            if not self.switch_mode:
                el.mapping_mode = arrayel.mapping_mode
            else:
                el.attribute_mapping_name = arrayel.attribute_mapping_name

        return {'FINISHED'}

#Operator: Button which refresh only one hair card
class CARDS2UV_Card_RefreshCardUI(bpy.types.Operator):
    bl_label = "Refresh Card"
    bl_idname = "cards2uv.refresh_card_ui"
    bl_options = {'REGISTER', 'UNDO'}

    #updateindex : IntProperty(name="Which Parameter To Update", default=0, options={'HIDDEN'})
    update_select : EnumProperty(name="Which Parameter To Update",
    items=[
        ("All", "All", ""),
        ("Rotation", "Rotation", ""),
    ], default="All", options={'HIDDEN'})

    array_index : IntProperty(name="UV Array Index", options={'HIDDEN'})
    element_index : IntProperty(name="UV Element Index", options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        objstoupdate = []
        arrayel = C2UV_UVCardsArray[self.array_index]

        multi = False

        if self.element_index >= 0: #One element
            multi = False
            objstoupdate.append(C2UV_UVCardsArray[self.array_index].uv_array[self.element_index])
        elif self.element_index == -2: #Array
            multi = True
            objs = arrayel.uv_array
            for o in objs:
                objstoupdate.append(o)

        for ou in objstoupdate:
            if self.update_select == "Rotation" or self.update_select == "All":
                #if not multi:
                #    arrayel = ou
                if multi:
                    ou.rotation = arrayel.rotation
                    ou.rotationcurrent = float(arrayel.rotation)
                else:
                    ou.rotationcurrent = float(ou.rotation)
                
            print_debug(f"UPDATING NODE {ou.material.name}")
            CreateOrUpdateShaderNodes(ou, arrayel.texnodes_array)

        return {"FINISHED"}

def LastOrCreateCollectionByName(coll_name, parentcoll):
    colls = [c for c in bpy.data.collections if coll_name in c.name]
    if len(colls) == 0:
        coll = bpy.data.collections.new(coll_name)
        parentcoll.children.link(coll)
        return coll
    else:
        return colls[-1:][0]

def LinkToSingleCollection(object, coll_name, parentcoll = None):
    collection = LastOrCreateCollectionByName(coll_name, parentcoll)

    isexist = False
    for coll in object.users_collection:
        if coll == collection:
            isexist = True
            continue
        coll.objects.unlink(object)
    if not isexist:
        collection.objects.link(object)

def ReplaceMaterialSlots(object, root_material):
    with bpy.context.temp_override(object=object, selected_objects=(object)):
        context = bpy.context
        
        object.active_material_index = 0
        for i in range(len(object.material_slots)):
            bpy.ops.object.material_slot_remove({'object': object})
        object.active_material = root_material

        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.material_slot_assign()
        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

    return

def CreateC2UVMeshFromObject(object, delete_old_mesh = False):
    with bpy.context.temp_override(object=object, selected_objects=(object)):
        context = bpy.context
        context.view_layer.objects.active = object

        bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.object.mode_set.poll()

        object.hide_set(False)
        object.select_set(True)

        if not object.visible_get():
            return None

        evalname = f"{object.name}_mesh_C2UV"

        if bpy.data.objects.find(evalname) != -1 and delete_old_mesh:
            existobj = bpy.data.objects[evalname]
            bpy.data.objects.remove(existobj)

        bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')
        bpy.ops.object.duplicate()
        bpy.ops.object.convert(target='MESH', keep_original=True)
        mesh_object = context.view_layer.objects.active
        mesh_object.name = evalname

        return mesh_object

def ApplyUVCoordsFromCard(object, cards, is_array_mat = False, already_selected = False):

    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

    for _ in (True,):
        with bpy.context.temp_override(object=object, selected_objects=(object)):
            context = bpy.context

            uvlayout_already_created = False
            for card in cards:
                if card.mapping_mode == "ATTRIBUTE":
                    attr_index = object.data.attributes.find(card.attribute_mapping_name)
                    if not attr_index < 0:
                        object.data.attributes.active_index = attr_index
                        bpy.ops.geometry.attribute_convert(domain='CORNER', data_type='FLOAT2')
                
                uvs = object.data.uv_layers
                #Set Default UV As Active
                if uvs.find("UVMap") >= 0:
                    uvs.active = uvs["UVMap"]

                #Make BackUp UV From Active
                if uvs.find("C2UV_BackUP") < 0:
                    uvs.new(name="C2UV_BackUP", do_init=True)

                #Re/Create Main UV And Make Active
                if uvs.find("C2UVMap") >= 0 and uvlayout_already_created == False:
                    uvs.remove(uvs["C2UVMap"])

                #Set BackUp C2UV Active
                if not uvlayout_already_created:
                    uvs.active = uvs["C2UV_BackUP"]

                    uvs.new(name="C2UVMap")
                    uvlayout_already_created = True

                uvs.active = uvs["C2UVMap"]
                uvs.active.active_render = True

                #Find material slot and set it active
                if not is_array_mat:
                    matindex = object.material_slots.find(card.material.name)
                    object.active_material_index = matindex

                #Select uv shells by active material
                context.area.ui_type = 'UV'
                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='EDIT')
                bpy.ops.mesh.reveal()
                
                if not already_selected:
                    #For be sure
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.uv.select_all(action='DESELECT')

                    #Select faces by material slot
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.material_slot_select()

                    if is_array_mat:
                        bpy.ops.mesh.select_all(action='SELECT')

                bpy.ops.uv.select_all(action='SELECT')

                #Apply Rotation From C2UV Card
                bpy.ops.transform.rotate(value=float(card.rotation))

                reverse_axis = (True, True, False) #It Just Works
                bpy.ops.transform.mirror(orient_type="GLOBAL", constraint_axis=reverse_axis)

                #Apply Coords From C2UV Card
                bpy.ops.transform.translate(value=(card.central[0] - .5, card.central[1] - .5, 0))

                #Apply Scale From C2UV Card
                bpy.ops.transform.resize(value=(card.scale[0], card.scale[1], 0))

                context.area.ui_type = 'VIEW_3D'
                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')
                #bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
                
    return

def CheckObjectMaterialInArray(object, cards_array):
    ReturnObject = namedtuple("ObjectCardPair", ["object", "cards"])

    if object.hide_get() == True:
        return None

    matched_cards = []
    
    shaders_cards = [ca for ca in cards_array if ca.material in [ms.material for ms in object.material_slots]]
    if len(shaders_cards) > 0:
        for sc in shaders_cards:
            if sc not in matched_cards:
                matched_cards.append(sc)

    #if object.active_material in cards_materials:
    #    return True
    
    modifiers = [i for i in object.modifiers if i.type == "NODES"]
    for m in modifiers:
        #if m is None and not hasattr(m, "node_group") and m.node_group is None and not hasattr(m.node_group, "nodes") and m.node_group.nodes is None:
        #    continue
        if m.node_group is None:
            continue
        
        set_mats = [st for st in m.node_group.nodes if st.type == "SET_MATERIAL" and not st.mute]
        for sm in set_mats:
            if len(sm.inputs[2].links) == 0: #and sm.inputs[2].default_value in cards_materials
                for c in [ca for ca in cards_array if ca.material == sm.inputs[2].default_value]:
                    if c not in matched_cards:
                        matched_cards.append(c)

    if len(matched_cards) == 0:
        return None
    
    return ReturnObject(object, matched_cards)

#Operation: Convert cards to uv coords
class CARDS2UV_Mesh_ConvertCardToMesh(bpy.types.Operator):
    bl_label = "Apply Coords To Mesh"
    bl_idname = "cards2uv.convert_card_to_mesh"
    bl_options = {'REGISTER', 'UNDO'}

    selection : EnumProperty(name="Which Cards To Convert",
    items=[
        ("ELEMENT", "Convert single card", "Update only one card"),
        ("ARRAY", "Convert all cards", "Convert all cards"),
        ("SELECTED", "Convert selected cards", "Convert selected cards")
    ], options={'SKIP_SAVE'})

    object_mode : BoolProperty(name="Convert UV For Only Selected Object", default=False, options={'SKIP_SAVE'})
    
    move_colletion : BoolProperty(name="Move Created Objects To Collection", default=True)

    replace_mesh : BoolProperty(name="Replace C2UV mesh if exist", default=True)

    hide_source : BoolProperty(name="Hide Source Object", default=True) 

    #newmeshcoll : BoolProperty(name="Create New Processed Collection", default=False)

    array_index : IntProperty(name="UV Array Index", default=-1, options={'HIDDEN'})
    element_index : IntProperty(name="UV Element Index", default=-1, options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray
        arr = C2UV_UVCardsArray[self.array_index]
        eval_collection_name = f"{arr.material.name}_mesh_C2UV"

        cards_array = []
        if self.selection in ["ELEMENT"]:
            cards_array.append(arr.uv_array[self.element_index])
        elif self.selection in ["SELECTED"]:
            for i in [t for t in arr.uv_array if t.is_selected]:
                cards_array.append(i)
        else:
            for i in arr.uv_array:
                cards_array.append(i)

        object_list = []
        if self.object_mode:
            for o in [vis for vis in context.selected_objects if vis.hide_get() == False and "_mesh_C2UV" not in vis.name]:
                proc = CheckObjectMaterialInArray(o, cards_array)
                if proc is not None:
                    object_list.append(proc)
        else:
            for o in [vis for vis in context.scene.objects if vis.hide_get() == False and "_mesh_C2UV" not in vis.name]:
                proc = CheckObjectMaterialInArray(o, cards_array)
                if proc is not None:
                    object_list.append(proc)
                    
        for ob in object_list:
            if ob is not None:
                mesh = CreateC2UVMeshFromObject(ob.object, delete_old_mesh=self.replace_mesh)
                ApplyUVCoordsFromCard(mesh, ob.cards)
                ReplaceMaterialSlots(mesh, arr.material)
                if self.move_colletion:
                    LinkToSingleCollection(mesh, eval_collection_name, mesh.users_collection[0])
                if self.hide_source:
                    ob.object.hide_set(True)

        #TODONE LINK TO COLLECTION AND MOVE SOURCE/CREATED
        

        return {'FINISHED'}

"""#Operation: Convert cards to uv coords
class CARDS2UV_Mesh_ConvertCardToMesh(bpy.types.Operator):
    bl_label = "Apply Coords To Mesh"
    bl_idname = "cards2uv.convert_card_to_mesh"
    bl_options = {'REGISTER', 'UNDO'}

    selection : EnumProperty(name="Which Cards To Convert",
    items=[
        ("ELEMENT", "Convert single card", "Update only one card"),
        ("ARRAY", "Convert all cards", "Convert all cards"),
        ("SELECTED", "Convert selected cards", "Convert selected cards")
    ], options={'SKIP_SAVE'})

    object_mode : BoolProperty(name="Convert UV For Only Selected Object", default=False, options={'SKIP_SAVE'})
    
    move_colletion : BoolProperty(name="Move Source Objects To Collection", default=True)
    #newmeshcoll : BoolProperty(name="Create New Processed Collection", default=False)

    array_index : IntProperty(name="UV Array Index", default=-1, options={'HIDDEN'})
    element_index : IntProperty(name="UV Element Index", default=-1, options={'HIDDEN'})

    def execute(self, context):
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray
        arr = C2UV_UVCardsArray[self.array_index]
        eval_collection_name = f"{arr.material.name}_mesh_C2UV"

        operatable_pull_objects = []
        source_pull_objects = []
        #unlinked_objects = []

        if self.selection == "ELEMENT":
            el = arr.uv_array[self.element_index]
            context.area.ui_type = 'VIEW_3D'
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

            object_pool = bpy.data.objects

            if self.object_mode:
                object_pool = context.selected_objects.copy()

            contains_material = []
            for oa in object_pool:
                if oa.active_material == el.material:
                    contains_material.append(oa)
                    continue
                
                modifiers = [i for i in oa.modifiers if i.type == "NODES"]
                for m in modifiers:
                    set_mats = [st for st in m.node_group.nodes if st.type == "SET_MATERIAL" and not st.mute]
                    
                    break_flag = False
                    for sm in set_mats:
                        if len(sm.inputs[2].links) == 0 and sm.inputs[2].default_value == el.material:
                            contains_material.append(oa)
                            break_flag = True
                            break
                    if break_flag:
                        break

                
                #elif len([i for i in oa.modifiers if len([st for st in i.node_group.nodes if st.type == "SET_MATERIAL" and len(st.inputs[2].links) == 0 and st.inputs[2].default_value == el.material]) > 0]) > 0:
                #    print_debug(f'Contains')
                #    contains_material.append(oa)
            #object_pool = contains_material

            if len(contains_material) > 0:
                #print(objects_array)

                converted_objects = CreateMeshesFromArray(context, contains_material)
                
                operatable_pull_objects = operatable_pull_objects + converted_objects

                source_pull_objects = source_pull_objects + contains_material

                ApplyUVCoordsFromCard(context, arr, card, converted_objects)

        elif self.selection == "ARRAY":
            
            object_pool = bpy.data.objects
            if self.object_mode:
                object_pool = context.selected_objects.copy()

            for card in arr.uv_array:
                context.area.ui_type = 'VIEW_3D'
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

                contains_material = []
                for oa in object_pool:
                    if oa.active_material == card.material:
                        contains_material.append(oa)
                        continue
                    
                    modifiers = [i for i in oa.modifiers if i.type == "NODES" and i.node_group is not None and i.node_group.nodes is not None]
                    for m in modifiers:
                        set_mats = [st for st in m.node_group.nodes if st.type == "SET_MATERIAL" and not st.mute]
                        
                        break_flag = False
                        for sm in set_mats:
                            print_debug(sm.inputs[2].default_value)
                            if len(sm.inputs[2].links) == 0 and sm.inputs[2].default_value == card.material:
                                contains_material.append(oa)
                                break_flag = True
                                break
                        if break_flag:
                            break

                #BURN IN HELL (Create objects duplicate for unlinking)
                #unlinked_objects = []
                #for obj in contains_material:
                #    bpy.ops.object.duplicate(linked = False)
                #    unlinked_objects.append(context.object)
                    #with bpy.context.temp_override(object=obj, selected_objects=(obj)):
                    #    cnt = bpy.context
                    #    bpy.ops.object.duplicate(linked = False)
                    #    unlinked_objects.append(cnt.object)

                #object_pool = contains_material

                #print(object_pool)
                #objects_array = [f for f in object_pool if f.active_material == card.material and "_mesh_C2UV" not in f.name]
                if len(contains_material) > 0:
                    #print(objects_array)

                    converted_objects = CreateMeshesFromArray(context, contains_material)
                    
                    operatable_pull_objects = operatable_pull_objects + converted_objects

                    source_pull_objects = source_pull_objects + contains_material

                    ApplyUVCoordsFromCard(context, arr, card, converted_objects)

        elif self.selection == "SELECTED":
            selarr = [i for i in C2UV_UVCardsArray[self.array_index].uv_array if i.is_selected]

            object_pool = bpy.data.objects
            if self.object_mode:
                object_pool = context.selected_objects.copy()

            for card in selarr:
                context.area.ui_type = 'VIEW_3D'
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set('INVOKE_REGION_WIN', mode='OBJECT')

                contains_material = []
                for oa in object_pool:
                    if oa.active_material == card.material:
                        contains_material.append(oa)
                        continue
                    
                    modifiers = [i for i in oa.modifiers if i.type == "NODES"]
                    for m in modifiers:
                        set_mats = [st for st in m.node_group.nodes if st.type == "SET_MATERIAL" and not st.mute]
                        
                        break_flag = False
                        for sm in set_mats:
                            if len(sm.inputs[2].links) == 0 and sm.inputs[2].default_value == card.material:
                                contains_material.append(oa)
                                break_flag = True
                                break
                        if break_flag:
                            break

                #object_pool = contains_material

                if len(contains_material) > 0:
                    #print(objects_array)

                    converted_objects = CreateMeshesFromArray(context, contains_material)
                    
                    operatable_pull_objects = operatable_pull_objects + converted_objects

                    source_pull_objects = source_pull_objects + contains_material

                    ApplyUVCoordsFromCard(context, arr, card, converted_objects)

        if len(operatable_pull_objects) > 0:
            LinkToSingleCollection(operatable_pull_objects, eval_collection_name, context.scene.collection)

        if self.move_colletion and len(source_pull_objects) > 0:
            LinkToSingleCollection(source_pull_objects, f"{arr.material.name}_source", parentcoll=context.scene.collection)

        #for dup in unlinked_objects:
        #    bpy.data.objects.remove(dup)

        return {'FINISHED'}"""

#Panel: Main panel which contains UV arrays
class main_panel(bpy.types.Panel):
    bl_label = "Cards 2 UV"
    bl_idname = "CARDS_UV_layout"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cards 2 UV"

    ShowFlag : bpy.props.BoolProperty(name= "ShowFlag", default= True)

    def draw(self, context):
        layout = self.layout
        C2UV_UVCardsArray = context.scene.C2UV_UVCardsArray

        selectedMaterial = []
        for o in context.selected_objects:
            selectedMaterial.append(o.active_material)

        #KEK
        kekrow = layout.row()
        kekrow.label(icon="EVENT_K")
        kekrow.label(icon="EVENT_E")
        kekrow.label(icon="EVENT_K")
        
        if context.active_object is not None and context.object is not None and len(context.selected_objects) > 0:
            meshCol = layout.column()
            #meshCol.prop(self, "creation_mode")
            meshCol.operator("cards2uv.create_uv_array", text="Create Array")

        elif len(context.selected_objects) == 0:
            objectParameterRow = layout.row()
            objectParameterRow.label(text="Select An Object", icon='ERROR')

        #Draw Cards Arrays
        for arrayindex, ggwp in enumerate(C2UV_UVCardsArray):
            box = layout.box()
            split = box.split()
            column = split.column()
            row = column.row(align=True)
            
            row.prop(ggwp, "is_shown", text=ggwp.material.name if ggwp.material is not None else "NaN",
                    icon='DISCLOSURE_TRI_DOWN' if ggwp.is_shown else 'KEYTYPE_JITTER_VEC')

            if ggwp.is_shown:
                row.prop(ggwp, "properties", text="",
                        icon='PROPERTIES')

            #row.label(text=ggwp.material.name if ggwp.material is not None else "NaN")
            ops = row.operator("cards2uv.select_uv_array_ui", text="", icon='VIS_SEL_11')
            ops.array_index = arrayindex

            ops = row.operator("cards2uv.update_uv_array_ui", text="", icon='FILE_REFRESH')
            ops.array_index = arrayindex

            ops = row.operator("cards2uv.clear_collections", text="", icon='PANEL_CLOSE')
            ops.delete_mark = False
            ops.index = arrayindex

            if ggwp.is_shown:
                column.row()

                ##Draw Properties
                if ggwp.properties:
                    wpbox = column.box()
                    col = wpbox.column(align=True)

                    #col.row().label(text="Rotation")

                    row = col.row(align=True)
                    row.prop(ggwp, "mapping_mode", expand=True)
                    op = row.operator("cards2uv.set_cards_mode", text="", icon="VIEW_PERSPECTIVE")
                    op.array_index = arrayindex
                    op.switch_mode = False

                    row = col.row(align=True)
                    row.prop(ggwp, "attribute_mapping_name", expand=True)
                    op = row.operator("cards2uv.set_cards_mode", text="", icon="SORTALPHA")
                    op.array_index = arrayindex
                    op.switch_mode = True

                    row = wpbox.row(align=True)
                    row.prop(ggwp, "rotation", expand=True)
                    op = row.operator("cards2uv.refresh_card_ui", text="", icon="DRIVER_ROTATIONAL_DIFFERENCE")
                    op.array_index = arrayindex
                    op.element_index = -2 #Array
                    op.update_select = "Rotation"

                    #Gradient Colors Tab
                    row = wpbox.row(align=True)
                    row.prop(ggwp, "colors_shown", text="Colors tab", icon="COLORSET_04_VEC")
                    if ggwp.colors_shown:
                        box = wpbox.box()
                        #col = box.column()
                        col = box.column(align=True)

                        for c, color in enumerate(ggwp.colors):
                            row = col.row(align=True)
                            row.prop(color, "color", text="")
                            if c > 1:
                                op = row.operator("cards2uv.gradient_element", text="", icon="PANEL_CLOSE")
                                op.color_index = c
                                op.array_index = arrayindex
                                op.is_addelement = False

                        row = col.row(align=True)
                        
                        op = row.operator("cards2uv.gradient_element", text="Add Color")
                        op.array_index = arrayindex
                        op.is_addelement = True

                        op = row.operator("cards2uv.apply_card_color", text="Apply Gradient")
                        op.array_index = arrayindex
                        #op.elementindex = e
                        op.update_mode = "ARRAY"

                    #Texture Selection Tab
                    row = wpbox.row(align=True)
                    row.prop(ggwp, "texprop_shown", text="Textures tab", icon="TEXTURE")
                    if ggwp.texprop_shown:
                        box = wpbox.box()
                        col = box.column(align=True)

                        for t, tex in enumerate(ggwp.texnodes_array):
                            row = col.row(align=True)
                            
                            row.label(text=f"{tex.node_name}")
                            try:
                                texture_name = ggwp.material.node_tree.nodes[tex.node_name].image.name
                                row.label(text=f"{texture_name}")
                            except:
                                texture_name = ""

                            row.prop(tex, "is_selected", text="", icon="RADIOBUT_ON" if tex.is_selected else "RADIOBUT_OFF")

                        row = col.row(align=True)
                        op = row.operator("cards2uv.update_uv_array_ui", text="Update Textures Links")
                        op.array_index = arrayindex
                        op.update_switch = 'RMAT'

                    row = wpbox.row(align=True)
                    op = row.operator("cards2uv.change_uv_card_index", text="Prev card")
                    op.is_forward = False

                    op = row.operator("cards2uv.change_uv_card_index", text="Next card")
                    op.is_forward = True

                    row = wpbox.row(align=True)
                    op = row.operator("cards2uv.randomize_cards", text="Set Random Cards")
                    op.array_index = arrayindex

                    row = wpbox.row(align=True)
                    op = row.operator("cards2uv.convert_card_to_mesh", text="Convert Cards To UV")
                    op.array_index = arrayindex
                    op.selection = "ARRAY"

                    row = wpbox.row(align=True)
                    op = row.operator("cards2uv.convert_card_to_mesh", text="Convert Object UV")
                    op.array_index = arrayindex
                    op.selection = "ARRAY"
                    op.object_mode = True
                
                ##Draw Cards
                for cardindex, ggbb in enumerate(ggwp.uv_array):
                    if ggbb.material is not None:
                        row = column.row(align=True)
                        row.prop(ggbb, "is_selected", text="", icon='RADIOBUT_ON' if ggbb.is_selected else 'RADIOBUT_OFF')

                        row.prop(ggbb, "is_shown", text=ggbb.visiblename, icon='DISCLOSURE_TRI_DOWN' if ggbb.is_shown else 'SETTINGS')

                        if ggbb.material in selectedMaterial:
                            row.prop(ggbb, "is_shown", text="", icon="RESTRICT_SELECT_OFF")
                        
                        if ggbb.is_shown:

                            if ggwp.creation_mode == "VERTEXGROUP":
                                #row.label(text="VERTEX")
                                op = row.operator("cards2uv.select_group_ui", text="", icon='VIS_SEL_11')

                                op.array_index = arrayindex
                                op.element_index = cardindex

                            op = row.operator("cards2uv.refresh_card_ui", text="", icon='FILE_REFRESH')
                            op.array_index = arrayindex
                            op.element_index = cardindex
                            op.update_select = "All"

                        op = row.operator("cards2uv.apply_card_ui", text="", icon='CHECKMARK')
                        op.array_index = arrayindex
                        op.element_index = cardindex
                        #op.update_select = "Rotation"

                        #op.materialname = ggbb.material.name

                        if ggbb.is_shown:
                            bbbox = column.box()
                            col = bbbox.column(align=True)

                            col = bbbox.column(align=True)
                            col.row().prop(ggbb, "mapping_mode", expand=True)
                            col.prop(ggbb, "attribute_mapping_name", expand=True)

                            col = bbbox.column(align=True)
                            col.prop(ggbb, "visiblename")

                            col.label(text="Rotation: {:.0f} current".format(ggbb.rotationcurrent / 1.570796 * 90))
                            col.row().prop(ggbb, "rotation", expand=True)
                            #COLOR
                            row = col.row(align=True)
                            row.prop(ggbb, "color")

                            op = row.operator("cards2uv.apply_card_color", text="", icon="RESTRICT_COLOR_ON")
                            op.array_index = arrayindex
                            op.element_index = cardindex
                            op.update_mode = "ELEMENT"

ClassNames = [
    ##Panel Declaration
    additional_panel,
    main_panel,
    ##Class Declaration
    CARDS2UV_texturenodesnames,
    CARDS2UV_colorsarray,
    CARDS2UV_uvelement,
    CARDS2UV_cardsarray,
    ##Operators Declaration
    CARDS2UV_initialize,
    CARDS2UV_CreateUVArray,
    CARDS2UV_Array_UpdateArrayUI,
    CARDS2UV_Array_SelectArrayUI,
    CARDS2UV_Array_SetCardsMode,
    CARDS2UV_Card_SelectGroupUI,
    CARDS2UV_ClearCollections,
    CARDS2UV_Card_ApplyCardUI,
    CARDS2UV_Card_RefreshCardUI,

    CARDS2UV_Card_ApplyCardColorUI,
    CARDS2UV_Array_ChangeCardIndex,
    CARDS2UV_Array_RandomizeCards,

    CARDS2UV_Array_GradientElement,

    CARDS2UV_Mesh_ConvertCardToMesh,
    
    #Additional Operators
    CARDS2UV_fixcurvedirection,
    CARDS2UV_meshtokurvas,
    CARDS2UV_Mesh_MirrorUV,
    CARDS2UV_Curve_RandomTilt,
    CARDS2UV_Curves_ConvertToPaths,
    CARDS2UV_UpdateSelectedCurves
]

addon_keymaps = []

#Keymaps for operator shortcuts
def init_keymaps():
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = [
        km.keymap_items.new("cards2uv.change_uv_card_index", 'NONE', 'PRESS'),
        #km.keymap_items.new("sorcar.clear_preview", 'E', 'PRESS', alt=True),
        #km.keymap_items.new("sorcar.group_nodes", 'G', 'PRESS', ctrl=True),
        #km.keymap_items.new("sorcar.edit_group", 'TAB', 'PRESS')
    ]
    return km, kmi

def register():
    for cls in ClassNames:
        try:
            bpy.utils.register_class(cls)
        except:
            print_debug(f"{cls.__name__} already registred")

    try:
        print_debug(f"{bpy.types.Scene.C2UV_UVCardsArray} existed")
    except:
        bpy.types.Scene.C2UV_UVCardsArray = bpy.props.CollectionProperty(type=CARDS2UV_cardsarray)

    addon_keymaps = init_keymaps()

def unregister():
    for cls in ClassNames:
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    addon_keymaps.clear()

    del bpy.types.Scene.C2UV_UVCardsArray

# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()