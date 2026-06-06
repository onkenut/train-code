import subprocess
import threading
import time
import socket
import os
import re

class Streamer:
    def __init__(self, host='0.0.0.0', port=8081, framerate=30, video_bitrate='4M'):
        self.host = host
        self.port = port
        self.framerate = framerate
        self.video_bitrate = video_bitrate
        self.process = None
        self._monitor_thread = None
        self._running = False
        self.use_nvenc = self._check_nvenc()

    def _check_nvenc(self):
        try:
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return 'h264_nvenc' in result.stdout
        except Exception:
            return False

    def _find_audio_device(self):
        try:
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stderr
            audio_section = False
            devices = []
            for line in output.split('\n'):
                if 'DirectShow audio devices' in line:
                    audio_section = True
                    continue
                if 'DirectShow video devices' in line:
                    audio_section = False
                    continue
                if audio_section and line.strip().startswith('[dshow') and 'Alternative name' not in line:
                    match = re.search(r'\"(.+?)\"', line)
                    if match:
                        devices.append(match.group(1))
            if devices:
                return devices[0]
            return None
        except Exception:
            return None

    def _get_resolution(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080

    def _build_command(self):
        width, height = self._get_resolution()
        audio_device = self._find_audio_device()

        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error']

        if self.use_nvenc:
            cmd.extend([
                '-vsync', '0',
                '-f', 'ddagrab',
                '-framerate', str(self.framerate),
                '-i', 'desktop'
            ])
        else:
            cmd.extend([
                '-f', 'gdigrab',
                '-framerate', str(self.framerate),
                '-i', 'desktop'
            ])

        if audio_device:
            cmd.extend([
                '-f', 'dshow',
                '-i', f'audio={audio_device}'
            ])

        if self.use_nvenc:
            cmd.extend([
                '-c:v', 'h264_nvenc',
                '-preset', 'p1',
                '-tune', 'zerolatency',
                '-bf', '0',
                '-g', '30',
                '-b:v', self.video_bitrate,
                '-maxrate', self.video_bitrate,
                '-bufsize', self.video_bitrate,
            ])
        else:
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-bf', '0',
                '-g', '30',
                '-b:v', self.video_bitrate,
                '-maxrate', self.video_bitrate,
                '-bufsize', self.video_bitrate,
            ])

        if audio_device:
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '44100',
            ])

        cmd.extend([
            '-f', 'flv',
            '-listen', '1',
            f'http://{self.host}:{self.port}/live.flv'
        ])

        return cmd

    def start(self):
        if self._running:
            return False

        cmd = self._build_command()
        print(f'Starting streamer with command: {" ".join(cmd)}')

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
            self._monitor_thread.start()
            time.sleep(2)
            return self.process.poll() is None
        except Exception as e:
            print(f'Streamer start error: {e}')
            return False

    def _monitor(self):
        while self._running and self.process:
            try:
                if self.process.poll() is not None:
                    stderr = self.process.stderr.read() if self.process.stderr else b''
                    print(f'Streamer exited with code {self.process.returncode}')
                    if stderr:
                        print(f'Stderr: {stderr.decode("utf-8", errors="ignore")}')
                    break
                time.sleep(1)
            except Exception:
                break
        self._running = False

    def stop(self):
        self._running = False
        if self.process:
            try:
                self.process.stdin.write(b'q\n')
                self.process.stdin.flush()
            except Exception:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    def is_running(self):
        return self._running and self.process and self.process.poll() is None

    def get_stream_url(self, host=None):
        if host is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                host = s.getsockname()[0]
                s.close()
            except Exception:
                host = '127.0.0.1'
        return f'http://{host}:{self.port}/live.flv'
