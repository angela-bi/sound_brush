import bpy
import sys
import json
import asyncio

# add project folder so blender_server can be imported as a real module
SERVER_DIR = "/Users/angelabi/UIUC/sound_brush/blender"
if SERVER_DIR not in sys.path:
    sys.path.append(SERVER_DIR)

import blender_server as _server
if _server._loop is None:
    _server.register()
    print(">>> server started")
else:
    print(">>> server already running")

print(">>> [1] basic imports done")

sys.path.append("/Users/angelabi/.local/lib/python3.11/site-packages")
print(">>> [2] sys.path updated")

import sounddevice as sd
import numpy as np
print(">>> [3] sounddevice and numpy imported")
print(sd.query_devices())

# -------------------------
# Globals
# -------------------------
_audio_stream = None
_current_level = 0.0
BRUSH_MIN = 1
BRUSH_MAX = 200
_smoothed_level = 0.0
SMOOTH_FACTOR = 0.15

print(">>> [4] globals set")

# -------------------------
# Helpers
# -------------------------
def get_microphone_items(self, context):
    items = []
    for i, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            label = f"{i}:{device['name']}"
            items.append((label, device["name"], ""))
    return items

def normalize_rms(audio_block, scale=1.0):
    rms = float(np.sqrt(np.mean(audio_block ** 2)))
    return min(rms * scale, 1.0)

def lerp(a, b, t):
    return a + (b - a) * t

def broadcast_level(level: float):
    """Look up blender_server from sys.modules — never import it directly."""
    try:
        server = sys.modules.get("blender_server")
        if server is None:
            print(">>> broadcast skipped: blender_server not in sys.modules (run it first)")
            return
        if not server._clients:
            print(">>> broadcast skipped: no browser clients connected")
            return
        if server._loop is None:
            print(">>> broadcast skipped: server loop is None")
            return
        brush = bpy.data.brushes.get("Pencil")
        brush_size = brush.size if brush else 0
        scale = bpy.context.scene.audio_rig.volume_scale if hasattr(bpy.context.scene, "audio_rig") else 1.0
        payload = json.dumps({
            "type": "level",
            "level": round(level, 4),
            "brush_size": brush_size,
            "sensitivity": round(float(scale), 2)
        })
        asyncio.run_coroutine_threadsafe(server._broadcast(payload), server._loop)
        print(f">>> broadcast sent: level={round(level,4)} brush={brush_size}px")
    except Exception as e:
        print(f">>> Broadcast error: {e}")

# -------------------------
# Audio callback (background thread)
# -------------------------
def audio_callback(indata, frames, time, status):
    global _current_level
    if status:
        print(f">>> audio status warning: {status}")
    scene = bpy.context.scene
    scale = scene.audio_rig.volume_scale if hasattr(scene, "audio_rig") else 1.0
    _current_level = normalize_rms(indata, scale=float(scale) * 10)

# -------------------------
# Blender timer (main thread)
# -------------------------
def update_brush_from_audio():
    global _smoothed_level

    if _audio_stream is None or not _audio_stream.active:
        print(">>> timer: stream gone, stopping")
        return None

    _smoothed_level = lerp(_smoothed_level, _current_level, SMOOTH_FACTOR)
    new_size = int(BRUSH_MIN + _smoothed_level * (BRUSH_MAX - BRUSH_MIN))

    brush = bpy.data.brushes.get("Pencil")
    if brush:
        brush.size = new_size
        print(f">>> brush size set to {new_size}px (level={_current_level:.3f})")
    else:
        print(">>> WARNING: brush 'Pencil' not found — check your brush name!")

    broadcast_level(_smoothed_level)
    return 0.05

# -------------------------
# Operators
# -------------------------
class BRUSH_AUDIO_START_OT(bpy.types.Operator):
    bl_idname = "brush.audio_start"
    bl_label = "Start Audio Mapping"
    bl_description = "Begin continuous audio → brush size mapping"

    def execute(self, context):
        global _audio_stream
        print(">>> START operator called")

        if _audio_stream is not None and _audio_stream.active:
            self.report({'WARNING'}, "Audio mapping already running")
            return {'CANCELLED'}

        scene = context.scene
        mic_label = scene.audio_rig.mic_list
        print(f">>> mic: {mic_label}")
        device_index = int(mic_label.split(":")[0]) if mic_label else None

        try:
            _audio_stream = sd.InputStream(
                device=device_index,
                channels=1,
                samplerate=44100,
                blocksize=2048,
                callback=audio_callback,
            )
            _audio_stream.start()
            print(f">>> stream active: {_audio_stream.active}")
            bpy.app.timers.register(update_brush_from_audio)
            print(">>> timer registered")
            self.report({'INFO'}, "Audio mapping started")
        except Exception as e:
            print(f">>> ERROR: {e}")
            self.report({'ERROR'}, f"Could not start audio stream: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


class BRUSH_AUDIO_STOP_OT(bpy.types.Operator):
    bl_idname = "brush.audio_stop"
    bl_label = "Stop Audio Mapping"
    bl_description = "Stop continuous audio → brush size mapping"

    def execute(self, context):
        global _audio_stream
        print(">>> STOP operator called")

        if _audio_stream is None or not _audio_stream.active:
            self.report({'WARNING'}, "Audio mapping is not running")
            return {'CANCELLED'}

        _audio_stream.stop()
        _audio_stream.close()
        _audio_stream = None
        self.report({'INFO'}, "Audio mapping stopped")
        return {'FINISHED'}

# -------------------------
# Settings
# -------------------------
class AudioRigSettings(bpy.types.PropertyGroup):
    mic_list: bpy.props.EnumProperty(
        name="Microphone",
        description="Select input device",
        items=get_microphone_items
    )
    volume_scale: bpy.props.FloatProperty(
        name="Sensitivity",
        description="Higher = more reactive to quiet sounds",
        default=1.0,
        min=0.1,
        max=10.0
    )

# -------------------------
# Panel
# -------------------------
class VIEW3D_PT_audio_brush(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Audio Brush"
    bl_label = "Audio → Brush Size"

    def draw(self, context):
        layout = self.layout
        audio_rig = context.scene.audio_rig

        layout.label(text="Microphone:")
        layout.prop(audio_rig, "mic_list", text="")
        layout.prop(audio_rig, "volume_scale")
        layout.separator()

        is_running = _audio_stream is not None and _audio_stream.active
        if is_running:
            layout.label(text=f"● Live  |  level: {_current_level:.2f}  |  size: {int(BRUSH_MIN + _smoothed_level * (BRUSH_MAX - BRUSH_MIN))}px")
            layout.operator("brush.audio_stop", text="Stop", icon="PAUSE")
        else:
            layout.operator("brush.audio_start", text="Start", icon="REC")

        layout.separator()
        layout.label(text=f"Brush range: {BRUSH_MIN}px – {BRUSH_MAX}px")
        layout.label(text="Smooth factor: 0.15 (edit in script)")

# -------------------------
# Register
# -------------------------
classes = (
    AudioRigSettings,
    BRUSH_AUDIO_START_OT,
    BRUSH_AUDIO_STOP_OT,
    VIEW3D_PT_audio_brush,
)

def register():
    print(">>> [5] registering classes")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.audio_rig = bpy.props.PointerProperty(type=AudioRigSettings)
    print(">>> [6] done — open the 'Audio Brush' tab in the N-panel (press N in 3D viewport)")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.audio_rig
    global _audio_stream
    if _audio_stream:
        _audio_stream.stop()
        _audio_stream.close()
        _audio_stream = None

if __name__ == "__main__":
    register()