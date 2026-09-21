import bpy
import sys
import json
import asyncio


sys.path.append("/Users/angelabi/.local/lib/python3.11/site-packages")

import sounddevice as sd
import numpy as np
print(sd.query_devices())

# -------------------------
# Single settings dict — shared across all functions
# -------------------------
SETTINGS = {
    "brush_min":    1,
    "brush_max":    200,
    "smooth_factor": 0.15,
}

# -------------------------
# Globals
# -------------------------
_audio_stream = None
_current_level = 0.0
_smoothed_level = 0.0


# -------------------------
# Import and start server
# -------------------------
SERVER_DIR = "/Users/angelabi/UIUC/sound_brush/blender"
if SERVER_DIR not in sys.path:
    sys.path.append(SERVER_DIR)

import blender_server as _server
if _server._loop is None:
    _server.register()
    print(">>> server started")
else:
    print(">>> server already running")

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

def get_sensitivity():
    if hasattr(bpy.context.scene, "audio_rig"):
        return float(bpy.context.scene.audio_rig.volume_scale)
    return 1.0

def broadcast_level(level: float):
    try:
        if not _server._clients or _server._loop is None:
            return
        brush = bpy.data.brushes.get("Pencil")
        brush_size = brush.size if brush else 0
        payload = json.dumps({
            "type":         "level",
            "level":        round(level, 4),
            "brush_size":   brush_size,
            "sensitivity":  round(get_sensitivity(), 2),
            "smooth_factor": round(SETTINGS["smooth_factor"], 3),
            "brush_min":    SETTINGS["brush_min"],
            "brush_max":    SETTINGS["brush_max"],
        })
        asyncio.run_coroutine_threadsafe(_server._broadcast(payload), _server._loop)
    except Exception as e:
        print(f">>> Broadcast error: {e}")

# -------------------------
# Incoming message handler
# -------------------------
def handle_browser_message(message: str):
    """Runs on Blender's main thread via job queue."""
    try:
        data = json.loads(message)
        msg_type = data.get("type")
        print(f">>> handling message: {data}")

        if msg_type == "set_smooth":
            SETTINGS["smooth_factor"] = max(0.01, min(1.0, float(data["value"])))
            print(f">>> smooth factor → {SETTINGS['smooth_factor']}")

        elif msg_type == "set_brush_min":
            SETTINGS["brush_min"] = max(1, int(float(data["value"])))
            print(f">>> brush min → {SETTINGS['brush_min']}")

        elif msg_type == "set_brush_max":
            SETTINGS["brush_max"] = min(500, int(float(data["value"])))
            print(f">>> brush max → {SETTINGS['brush_max']}")

        elif msg_type == "set_sensitivity":
            if hasattr(bpy.context.scene, "audio_rig"):
                val = max(0.1, min(10.0, float(data["value"])))
                bpy.context.scene.audio_rig.volume_scale = val
                print(f">>> sensitivity → {val}")

        else:
            print(f">>> unknown message type: {msg_type}")

    except Exception as e:
        print(f">>> handle_browser_message error: {e}")

# -------------------------
# Patch server echo
# -------------------------
async def _patched_echo(websocket):
    print(f">>> client connected: {websocket.remote_address}")
    _server._clients.add(websocket)
    try:
        _server._job_queue.put(_server.send_grease_pencil_layers)
        _server._job_queue.put(_server.send_brush_info)
        async for message in websocket:
            print(f">>> received from browser: {message}")
            _server._job_queue.put(lambda m=message: handle_browser_message(m))
    except Exception as e:
        print(f">>> client error: {e}")
    finally:
        _server._clients.discard(websocket)
        print(f">>> client disconnected, remaining: {len(_server._clients)}")

_server.echo = _patched_echo
print(">>> echo handler patched")

# -------------------------
# Audio callback (background thread)
# -------------------------
def audio_callback(indata, frames, time, status):
    global _current_level
    if status:
        print(f">>> audio status warning: {status}")
    scale = get_sensitivity()
    _current_level = normalize_rms(indata, scale=scale * 10)

# -------------------------
# Blender timer (main thread)
# -------------------------
def update_brush_from_audio():
    global _smoothed_level

    if _audio_stream is None or not _audio_stream.active:
        print(">>> timer: stream gone, stopping")
        return None

    smooth   = SETTINGS["smooth_factor"]
    bmin     = SETTINGS["brush_min"]
    bmax     = SETTINGS["brush_max"]

    _smoothed_level = lerp(_smoothed_level, _current_level, smooth)
    new_size = int(bmin + _smoothed_level * (bmax - bmin))

    brush = bpy.data.brushes.get("Pencil")
    if brush:
        brush.size = new_size
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
            bmin = SETTINGS["brush_min"]
            bmax = SETTINGS["brush_max"]
            size = int(bmin + _smoothed_level * (bmax - bmin))
            layout.label(text=f"● Live  |  level: {_current_level:.2f}  |  size: {size}px")
            layout.operator("brush.audio_stop", text="Stop", icon="PAUSE")
        else:
            layout.operator("brush.audio_start", text="Start", icon="REC")

        layout.separator()
        layout.label(text=f"Brush range: {SETTINGS['brush_min']}px – {SETTINGS['brush_max']}px")
        layout.label(text=f"Smooth factor: {SETTINGS['smooth_factor']}")

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
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.audio_rig = bpy.props.PointerProperty(type=AudioRigSettings)

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