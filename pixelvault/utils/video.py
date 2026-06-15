import os
import logging
import tempfile
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


def extract_keyframes(filepath: str, interval: float = 5.0, max_frames: int = 10) -> List[str]:
    try:
        import cv2
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        frame_interval = int(fps * interval)
        output_paths = []
        tmp_dir = tempfile.mkdtemp(prefix="pixelvault_kf_")

        frame_count = 0
        saved_count = 0

        while saved_count < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
            ret, frame = cap.read()
            if not ret:
                break

            out_path = os.path.join(tmp_dir, f"frame_{saved_count:04d}.jpg")
            cv2.imwrite(out_path, frame)
            output_paths.append(out_path)

            frame_count += frame_interval
            saved_count += 1

        cap.release()
        return output_paths
    except Exception as e:
        logger.error(f"Keyframe extraction failed for {filepath}: {e}")
        return []


def get_video_info(filepath: str) -> Optional[dict]:
    try:
        import ffmpeg
        probe = ffmpeg.probe(filepath)
        info = {"duration": 0, "width": 0, "height": 0, "codec": "", "fps": "", "audio_codec": ""}

        for stream in probe.get("streams", []):
            if stream["codec_type"] == "video":
                info["width"] = int(stream.get("width", 0))
                info["height"] = int(stream.get("height", 0))
                info["codec"] = stream.get("codec_name", "")
                info["fps"] = stream.get("r_frame_rate", "")
            elif stream["codec_type"] == "audio":
                info["audio_codec"] = stream.get("codec_name", "")

        info["duration"] = float(probe.get("format", {}).get("duration", 0))
        info["size"] = int(probe.get("format", {}).get("size", 0))
        info["bitrate"] = int(probe.get("format", {}).get("bit_rate", 0))

        return info
    except Exception as e:
        logger.debug(f"Video info extraction failed for {filepath}: {e}")
        return None


def generate_video_thumbnail(filepath: str, timestamp: float = 1.0, output_path: Optional[str] = None) -> Optional[str]:
    try:
        import cv2
        cap = cv2.VideoCapture(filepath)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        if output_path is None:
            tmp_dir = tempfile.mkdtemp(prefix="pixelvault_thumb_")
            output_path = os.path.join(tmp_dir, "thumb.jpg")

        cv2.imwrite(output_path, frame)
        return output_path
    except Exception as e:
        logger.error(f"Video thumbnail failed for {filepath}: {e}")
        return None


def compute_video_phash(filepath: str, sample_count: int = 5) -> Optional[str]:
    try:
        import cv2
        from pixelvault.core.hasher import compute_phash

        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            return None

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(total_frames // sample_count, 1)

        hashes = []
        for i in range(sample_count):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i * step)
            ret, frame = cap.read()
            if ret:
                h = compute_phash(frame)
                if h:
                    hashes.append(h)

        cap.release()

        if not hashes:
            return None

        combined = "".join(hashes)
        return combined
    except Exception as e:
        logger.error(f"Video pHash failed for {filepath}: {e}")
        return None
