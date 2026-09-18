import sounddevice as sd
import numpy as np
import bpy

import sys
sys.path.append("/Users/angelabi/.local/lib/python3.11/site-packages") # replace with own path
import cv2

##################
# SOURCES
##################
# https://github.com/F1dg3tXD/MAD/blob/main/MAD_OSX/mad.py
# https://github.com/CGArtPython/blender_plus_python/blob/main/add-ons/simple_custom_panel/simple_custom_panel.py


##################
# HELPER FUNCTIONS 
##################

def get_microphone_items(self, context):
    items = []
    for i, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            label = f"{i}:{device['name']}"
            items.append((label, device["name"], ""))
    return items

# todo: implement camera source selection for opencv

def list_gp_layers(obj=None):
    if obj is None:
        obj = bpy.context.active_object
    if not obj or obj.type != 'GPENCIL':
        print("No active Grease Pencil object selected.")
        return
    gp_data = obj.data
    print(f"Grease Pencil layers in '{obj.name}':")
    for i, layer in enumerate(gp_data.layers):
        print(f"  Layer {i}: {layer.info}")
        print(f"    - Visible: {layer.hide is False}")
        print(f"    - Locked: {layer.lock}")
        print(f"    - Frames: {[frame.frame_number for frame in layer.frames]}")
        
def normalize(array):
    # returns array but normalized
    return (array - np.min(array)) / (np.max(array) - np.min(array))
        
def safe_sample(array):
    # returns a random sample of the array used
    return float(np.random.choice(array))

def change_rgb(bool_tuple, color_tuple, new_val):
    # takes in a tuple of booleans (r,g,b) and returns a tuple with the values marked "true" changed
    red, green, blue = bool_tuple
    r, g, b = color_tuple

    new_val = max(0.0, min(1.0, new_val))
    if red:
        r = new_val
    if green:
        g = new_val
    if blue:
        b = new_val

    new_color = (r, g, b)
    print("old:", color_tuple, "→ new:", new_color)
    return new_color


##################
# SETTINGS/OPTION CLASSES
##################

class InputMappingSettings(bpy.types.PropertyGroup):
    input_source: bpy.props.EnumProperty(
        name="Input Source",
        description="Choose input type",
        items=[
            ('AUDIO', "Audio", "Use microphone input"),
            ('CAMERA', "Camera", "Use webcam input"),
        ],
        default='AUDIO'
    )
    
class OutputMappingSettings(bpy.types.PropertyGroup):
    output_source: bpy.props.EnumProperty(
        name="Output Source",
        description="Choose output type",
        items=[
            ('COLOR', "Brush Color", "Change brush color"),
            ('SIZE', "Brush Size", "Change brush size"),
        ],
        default='COLOR'
    )

class AudioRigSettings(bpy.types.PropertyGroup):
    mic_list: bpy.props.EnumProperty(
        name="Microphone",
        description="Select input device",
        items=get_microphone_items
    )
    volume_scale: bpy.props.FloatProperty(name="Volume to Value Scale", default=1.0)
    # not implemented yet
    recording_length: bpy.props.FloatProperty(name="Recording Length (s)", default=1.0, min=0.0, max=3.0)
    # make more ways to interact with input data


# property group for selecting color channel
checkboxes = 3
checkbox_names = [ "Red", "Green", "Blue"]
class color_channel_settings(bpy.types.PropertyGroup):
    channel_list: bpy.props.BoolVectorProperty(
        name="Channels",
        description="Select color channels",
        size=checkboxes,
        default = (False,) * checkboxes
    )
    

##################
# OPERATORS
##################

class BRUSH_MAPPING_OT(bpy.types.Operator):
    bl_idname = "brush.mapping_operator"
    bl_label = "Mapping Operator"
    bl_description = "Maps selected input to output"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        layout = self.layout
        scene = context.scene
        input_mapping = scene.input_mapping
        output_mapping = scene.output_mapping
        # these contain the input and output the user has selected
        color_channel = scene.color_channel
        audio_rig = scene.audio_rig
        
        # current operators modify the brush
        brush = bpy.data.brushes.get("Pencil") # brush should be a choice as well...
        
        if input_mapping.input_source == "AUDIO":
            try:
                duration = 1
                sample_rate = 44100
                audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
                sd.wait()
                audio = np.array(audio).flatten()
                print('audio:', audio)
                normalized_audio = normalize(audio)
                new_value = safe_sample(normalized_audio)
                print('new_value', new_value)
                
            except Exception as e:
                self.report({'ERROR'}, f"Error: {str(e)}")
                
                
        elif input_mapping.input_source == "CAMERA":
            try:
                cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
                cv2.namedWindow("Webcam Brightness Tracker", cv2.WINDOW_NORMAL)
                arr = []
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        print("failed to read frame.")
                        break

                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    brightness = np.mean(gray)
                    arr.append(brightness)

                    cv2.putText(frame, f"Brightness: {brightness:.2f}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    cv2.imshow("Webcam Brightness Tracker", frame)

                    key = cv2.waitKey(1)
                    if key == ord('q'):
                        print("exiting")
                        break
                    
            except Exception as e:
                self.report({'ERROR'}, f"Error: {str(e)}")

        if output_mapping.output_source == "COLOR":
            color_channel = context.scene.color_channel
            red = color_channel.channel_list[0]
            green = color_channel.channel_list[1]
            blue = color_channel.channel_list[2]
            
            print("old brush rgb", brush.color)
            brush.color = change_rgb((red, green, blue), brush.color, new_value)
            print("new brush rgb", brush.color)

        elif output_mapping.output_source == "SIZE":
            print("old brush size", brush.size)
            brush.size = new_value
            print("new brush size", brush.size)
        
        else:
            print('something went wrong', input_mapping, output_mapping)
        
        return {'FINISHED'}
               

##################
# MAIN UI
##################

class VIEW3D_PT_creative_constraints(bpy.types.Panel):  # class naming convention ‘CATEGORY_PT_name’

    # where to add the panel in the UI
    bl_space_type = "VIEW_3D"  # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_region_type = "UI"  # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)

    bl_category = "Creative Constraints"  # found in the Sidebar
    bl_label = "Input to Output Mapping"  # found at the top of the Panel

    def draw(self, context): # function that defines layout
        layout = self.layout
        scene = context.scene
        input_mapping = scene.input_mapping
        output_mapping = scene.output_mapping
        color_channel = scene.color_channel
        audio_rig = scene.audio_rig
        
        layout.label(text="Select Input:")
        layout.prop(input_mapping, "input_source", expand=True)
        row = layout.row()
        
        if input_mapping.input_source == 'AUDIO':
            layout.prop(audio_rig, "mic_list")
            layout.prop(audio_rig, "volume_scale")
            layout.prop(audio_rig, "recording_length")

            
        layout.label(text="Select Ouput:")
        layout.prop(output_mapping, "output_source", expand=True)
        row = layout.row()
        
        if output_mapping.output_source == 'COLOR':
            row = layout.row()
            row.label(text="Channels:")
            # color_channel, "channel_list"
            for idx in range(len(color_channel.channel_list)):
                layout.prop(color_channel, "channel_list", index=idx, text=checkbox_names[idx])
                
                
        row = layout.row()
        layout.operator("brush.mapping_operator", text="Map")
                  
            
        
classes = (
    InputMappingSettings,
    OutputMappingSettings,
    AudioRigSettings,
    color_channel_settings,
    BRUSH_MAPPING_OT,
    VIEW3D_PT_creative_constraints,
)
        

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.color_channel = bpy.props.PointerProperty(type= color_channel_settings) # this creates a variable that can be referenced
    bpy.types.Scene.audio_rig = bpy.props.PointerProperty(type= AudioRigSettings)
    bpy.types.Scene.input_mapping = bpy.props.PointerProperty(type=InputMappingSettings)
    bpy.types.Scene.output_mapping = bpy.props.PointerProperty(type=OutputMappingSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.input_mapping
    del bpy.types.Scene.output_mapping
    del bpy.types.Scene.color_channel
    del bpy.types.Scene.audio_rig


if __name__ == "__main__":
    register()