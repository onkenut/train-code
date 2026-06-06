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
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

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
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

streamer = None
if Streamer:
    try:
        streamer = Streamer(host='0.0.0.0', port=8081)
    except Exception as e:
        print(f'WARNING: Failed to initialize streamer: {e}')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify({
        'streaming': streamer.is_running() if streamer else False,
        'stream_url': streamer.get_stream_url() if streamer else '',
        'is_admin': is_admin()
    })

@app.route('/api/start', methods=['POST'])
def start_stream():
    if not streamer:
        return jsonify({'success': False, 'message': 'Streamer not available'})
    if streamer.is_running():
        return jsonify({'success': True, 'message': 'Already streaming'})
    success = streamer.start()
    return jsonify({'success': success, 'stream_url': streamer.get_stream_url() if streamer else ''})

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
def handle_mouse_left_down():
    mouse_left_down()

@socketio.on('mouse:left:up')
def handle_mouse_left_up():
    mouse_left_up()

@socketio.on('mouse:left:click')
def handle_mouse_left_click():
    mouse_left_click()

@socketio.on('mouse:right:down')
def handle_mouse_right_down():
    mouse_right_down()

@socketio.on('mouse:right:up')
def handle_mouse_right_up():
    mouse_right_up()

@socketio.on('mouse:right:click')
def handle_mouse_right_click():
    mouse_right_click()

@socketio.on('mouse:middle:down')
def handle_mouse_middle_down():
    mouse_middle_down()

@socketio.on('mouse:middle:up')
def handle_mouse_middle_up():
    mouse_middle_up()

@socketio.on('mouse:middle:click')
def handle_mouse_middle_click():
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
    print(f'Server started on http://0.0.0.0:8000')
    if streamer:
        print(f'Stream URL: {streamer.get_stream_url()}')
    print('=' * 50)
    socketio.run(app, host='0.0.0.0', port=8000, debug=False)
