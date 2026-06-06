import os
import yaml

DEFAULT_CONFIG = {
    'server': {
        'host': '0.0.0.0',
        'http_port': 8000,
        'flv_port': 8081,
        'debug': False
    },
    'stream': {
        'framerate': 30,
        'video_bitrate': '4M',
        'audio_bitrate': '128k',
        'audio_sample_rate': 44100,
        'use_hwaccel': 'auto',
        'gop_size': 30,
        'b_frames': 0
    },
    'mouse': {
        'scroll_sensitivity': 4.0,
        'move_sensitivity': 1.0,
        'long_press_delay': 500,
        'move_threshold': 10
    },
    'advanced': {
        'flv_listen_timeout': 30,
        'ffmpeg_loglevel': 'error',
        'socketio_ping_timeout': 60,
        'socketio_ping_interval': 25
    }
}

_config = None

def _deep_merge(base, override):
    result = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def load_config(config_path=None):
    global _config
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yaml')
    
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config and isinstance(user_config, dict):
                    config = _deep_merge(config, user_config)
        except Exception as e:
            print(f'WARNING: Failed to load config file {config_path}: {e}')
            print('Using default configuration')
    
    _config = config
    return config

def get_config():
    global _config
    if _config is None:
        load_config()
    return _config

def get_server_config():
    return get_config()['server']

def get_stream_config():
    return get_config()['stream']

def get_mouse_config():
    return get_config()['mouse']

def get_advanced_config():
    return get_config()['advanced']
