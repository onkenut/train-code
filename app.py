import sys
import os

try:
    import eventlet
    eventlet.monkey_patch()
except ImportError as e:
    print(f'ERROR: Failed to import eventlet: {e}')
    print('Please install dependencies: pip install -r requirements.txt')
    sys.exit(1)

import ctypes
import urllib.request
from flask import Flask, render_template, jsonify, Response, request
from flask_socketio import SocketIO, emit

from modules.config import load_config, get_server_config, get_advanced_config

load_config()
server_cfg = get_server_config()
advanced_cfg = get_advanced_config()

try:
    from modules.streamer import Streamer
except ImportError as e:
    print(f'ERROR: Failed to import streamer module: {e}')
    Streamer = None

try:
    from modules.input_control import (
        mouse_move_absolute, mouse_move_relative,
        mouse_left_down, mouse_left_up, mouse_left_click,
        mouse_right_down, mouse_right_up, mouse_right_click,
        mouse_middle_down, mouse_middle_up, mouse_middle_click,
        mouse_wheel,
        key_down, key_up, key_press, key_combination
    )
except ImportError as e:
    print(f'WARNING: Failed to import input_control: {e}')
    mouse_move_absolute = lambda *a, **k: None
    mouse_move_relative = lambda *a, **k: None
    mouse_left_down = lambda *a, **k: None
    mouse_left_up = lambda *a, **k: None
    mouse_left_click = lambda *a, **k: None
    mouse_right_down = lambda *a, **k: None
    mouse_right_up = lambda *a, **k: None
    mouse_right_click = lambda *a, **k: None
    mouse_middle_down = lambda *a, **k: None
    mouse_middle_up = lambda *a, **k: None
    mouse_middle_click = lambda *a, **k: None
    mouse_wheel = lambda *a, **k: None
    key_down = lambda *a, **k: None
    key_up = lambda *a, **k: None
    key_press = lambda *a, **k: None
    key_combination = lambda *a, **k: None

try:
    from modules.clipboard import paste_text
except ImportError as e:
    print(f'WARNING: Failed to import clipboard: {e}')
    paste_text = lambda *a, **k: False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'remote-desktop-secret'

socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins='*',
    ping_timeout=advanced_cfg['socketio_ping_timeout'],
    ping_interval=advanced_cfg['socketio_ping_interval']
)

streamer = None
if Streamer:
    try:
        streamer = Streamer(host='127.0.0.1')
    except Exception as e:
        print(f'WARNING: Failed to initialize streamer: {e}')

def _flv_generator(resp):
    chunk_size = 8192
    try:
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            yield chunk
    except GeneratorExit:
        pass
    except Exception:
        pass
    finally:
        try:
            resp.close()
        except Exception:
            pass

def _proxy_flv():
    if not streamer or not streamer.is_running():
        return Response('Stream not available', status=503)
    try:
        internal_url = streamer.get_internal_url()
        req = urllib.request.Request(internal_url)
        resp = urllib.request.urlopen(req, timeout=10)
        response = Response(
            _flv_generator(resp),
            status=200,
            mimetype='video/x-flv'
        )
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f'FLV proxy error: {e}')
        return Response(f'Proxy error: {e}', status=502)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/live.flv')
def live_flv():
    return _proxy_flv()

def _get_desktop_resolution():
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080

@app.route('/api/status')
def status():
    width, height = _get_desktop_resolution()
    return jsonify({
        'streaming': streamer.is_running() if streamer else False,
        'stream_url': streamer.get_proxied_url() if streamer else '',
        'is_admin': is_admin(),
        'desktop_width': width,
        'desktop_height': height
    })

@app.route('/api/start', methods=['POST'])
def start_stream():
    if not streamer:
        return jsonify({'success': False, 'message': 'Streamer not available'})
    if streamer.is_running():
        return jsonify({'success': True, 'message': 'Already streaming', 'stream_url': streamer.get_proxied_url()})
    success = streamer.start()
    return jsonify({
        'success': success,
        'stream_url': streamer.get_proxied_url() if streamer else ''
    })

@app.route('/api/stop', methods=['POST'])
def stop_stream():
    if streamer:
        streamer.stop()
    return jsonify({'success': True})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('mouse:move:abs')
def handle_mouse_move_abs(data):
    mouse_move_absolute(data.get('x', 0), data.get('y', 0))

@socketio.on('mouse:move:rel')
def handle_mouse_move_rel(data):
    mouse_move_relative(data.get('dx', 0), data.get('dy', 0))

@socketio.on('mouse:left:down')
def handle_mouse_left_down(data=None):
    mouse_left_down()

@socketio.on('mouse:left:up')
def handle_mouse_left_up(data=None):
    mouse_left_up()

@socketio.on('mouse:left:click')
def handle_mouse_left_click(data=None):
    mouse_left_click()

@socketio.on('mouse:right:down')
def handle_mouse_right_down(data=None):
    mouse_right_down()

@socketio.on('mouse:right:up')
def handle_mouse_right_up(data=None):
    mouse_right_up()

@socketio.on('mouse:right:click')
def handle_mouse_right_click(data=None):
    mouse_right_click()

@socketio.on('mouse:middle:down')
def handle_mouse_middle_down(data=None):
    mouse_middle_down()

@socketio.on('mouse:middle:up')
def handle_mouse_middle_up(data=None):
    mouse_middle_up()

@socketio.on('mouse:middle:click')
def handle_mouse_middle_click(data=None):
    mouse_middle_click()

@socketio.on('mouse:wheel')
def handle_mouse_wheel(data):
    mouse_wheel(data.get('dx', 0), data.get('dy', 0))

@socketio.on('key:down')
def handle_key_down(data):
    key_down(data.get('key'))

@socketio.on('key:up')
def handle_key_up(data):
    key_up(data.get('key'))

@socketio.on('key:press')
def handle_key_press(data):
    key_press(data.get('key'))

@socketio.on('key:combination')
def handle_key_combination(data):
    keys = data.get('keys', [])
    key_combination(*keys)

@socketio.on('paste:text')
def handle_paste_text(data):
    text = data.get('text', '')
    if text:
        success = paste_text(text)
        emit('paste:result', {'success': success})

if __name__ == '__main__':
    if not is_admin():
        print('WARNING: Not running as administrator. Some features may not work.')
        print('Please restart with administrator privileges for full functionality.')
    
    if streamer:
        try:
            streamer.start()
        except Exception as e:
            print(f'Failed to start streamer: {e}')
    else:
        print('WARNING: Streamer not available, video streaming disabled')
    
    print('=' * 50)
    print(f'Server started on http://{server_cfg["host"]}:{server_cfg["http_port"]}')
    if streamer:
        print(f'Stream proxy: /live.flv')
    print('=' * 50)
    socketio.run(
        app,
        host=server_cfg['host'],
        port=server_cfg['http_port'],
        debug=server_cfg['debug']
    )
