import bpy
import asyncio
import threading
import sys
import socket
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import queue

sys.path.append("/Users/angelabi/.local/lib/python3.11/site-packages")
import websockets

# -------------------------
# Globals
# -------------------------
_server_thread = None
_loop = None
_clients = set()
_job_queue = queue.Queue()
_WS_PORT = None
_HTTP_PORT = 8000

# -------------------------
# WebSocket server
# -------------------------
async def echo(websocket):
    print(f">>> client connected: {websocket.remote_address}")
    _clients.add(websocket)
    print(f">>> total clients: {len(_clients)}")
    try:
        _job_queue.put(send_grease_pencil_layers)
        _job_queue.put(send_brush_info)
        async for message in websocket:
            print("Received from browser:", message)
            if message == "layers":
                _job_queue.put(send_grease_pencil_layers)
                _job_queue.put(send_brush_info)
    except Exception as e:
        print(f"Client error: {e}")
    finally:
        _clients.discard(websocket)
        print(f">>> client disconnected, remaining: {len(_clients)}")

def find_free_port(start=8765, max_tries=20):
    for port in range(start, start + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    raise OSError(f"No free port found in range {start}-{start+max_tries-1}")

def start_server():
    global _loop, _WS_PORT
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _WS_PORT = find_free_port(8765)

    async def run_ws():
        async with websockets.serve(echo, "localhost", _WS_PORT):
            print(f"✅ WebSocket server started on ws://localhost:{_WS_PORT}")
            await asyncio.Future()

    _loop.run_until_complete(run_ws())
    _loop.run_forever()

# -------------------------
# HTTP discovery server
# -------------------------
class PortHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress noisy HTTP logs

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"port": _WS_PORT}).encode())

def start_http_server():
    httpd = HTTPServer(("localhost", _HTTP_PORT), PortHandler)
    print(f"🌐 HTTP discovery server on http://localhost:{_HTTP_PORT}")
    httpd.serve_forever()

# -------------------------
# Blender job queue
# -------------------------
def process_jobs():
    while not _job_queue.empty():
        job = _job_queue.get()
        try:
            job()
        except Exception as e:
            print(f"Job error: {e}")
    return 0.1

# -------------------------
# Brush info
# -------------------------
def get_brush_info():
    ts = bpy.context.tool_settings
    brush = None
    if ts.gpencil_paint and ts.gpencil_paint.brush:
        brush = ts.gpencil_paint.brush
    if not brush:
        return {"error": "No active Grease Pencil brush"}
    return {
        "name": brush.name,
        "size": brush.size,
        "strength": brush.strength,
        "color": list(brush.color),
        "blend": brush.blend
    }

def send_brush_info():
    data = get_brush_info()
    if "error" in data:
        print("⚠️", data["error"])
        return
    send_to_clients(json.dumps({"type": "brush", "brush": data}))

# -------------------------
# Grease Pencil layers
# -------------------------
def get_active_grease_pencil_layers():
    obj = bpy.context.active_object
    if not obj or obj.type != 'GPENCIL':
        return {"error": "No active Grease Pencil object"}
    gp_data = obj.data
    layers_info = []
    for layer in gp_data.layers:
        layers_info.append({
            "name": layer.info,
            "frames": len(layer.frames),
            "active": layer == gp_data.layers.active,
            "visible": not layer.hide,
            "locked": layer.lock
        })
    return {"object_name": obj.name, "layers": layers_info}

def send_grease_pencil_layers():
    data = get_active_grease_pencil_layers()
    if "error" in data:
        print("⚠️", data["error"])
        return
    payload = {
        "type": "layers",
        "layers": [
            {"id": idx, "name": layer["name"], "visible": layer["visible"]}
            for idx, layer in enumerate(data["layers"])
        ]
    }
    send_to_clients(json.dumps(payload))

# -------------------------
# Broadcast helpers
# -------------------------
def send_to_clients(message: str):
    if _loop and _clients:
        asyncio.run_coroutine_threadsafe(_broadcast(message), _loop)

async def _broadcast(message: str):
    for ws in list(_clients):
        try:
            await ws.send(message)
        except Exception as e:
            print(f"Failed to send to client: {e}")

# -------------------------
# Register / Unregister
# -------------------------
def register():
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        print("⚠️ Server already running")
        return

    ws_thread = threading.Thread(target=start_server, daemon=True)
    ws_thread.start()

    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    bpy.app.timers.register(process_jobs, persistent=True)
    print("✅ Server threads started")

def unregister():
    global _loop
    if _loop:
        _loop.call_soon_threadsafe(_loop.stop)
        _loop = None
    print("🛑 Servers stopped")
    
import sys as _sys
_sys.modules["blender_server"] = _sys.modules[__name__]

if __name__ == "__main__":
    register()