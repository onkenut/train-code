import json
import logging
from typing import Optional, Tuple, List
from datetime import datetime

from pixelvault.database.dao import AssetDAO, MetadataDAO
from pixelvault.database.models import Asset, Metadata

logger = logging.getLogger(__name__)


class MetadataExtractor:
    def __init__(self):
        self.asset_dao = AssetDAO()
        self.metadata_dao = MetadataDAO()

    def extract_exif(self, filepath: str) -> dict:
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            exif_data = {}
            with Image.open(filepath) as img:
                raw_exif = img._getexif()
                if raw_exif:
                    for tag_id, value in raw_exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8", errors="replace")
                            except Exception:
                                value = str(value)
                        exif_data[tag] = value

                    if "GPSInfo" in exif_data:
                        gps_info = {}
                        for key in exif_data["GPSInfo"].keys():
                            decode = GPSTAGS.get(key, key)
                            gps_info[decode] = exif_data["GPSInfo"][key]
                        exif_data["GPSInfo"] = gps_info

            return exif_data
        except Exception as e:
            logger.debug(f"EXIF extraction failed for {filepath}: {e}")
            return {}

    def extract_gps(self, exif_data: dict) -> Tuple[Optional[float], Optional[float]]:
        gps_info = exif_data.get("GPSInfo", {})
        if not gps_info:
            return None, None

        try:
            def _convert_to_degrees(value):
                d, m, s = value
                return float(d) + float(m) / 60.0 + float(s) / 3600.0

            lat = _convert_to_degrees(gps_info.get("GPSLatitude", (0, 0, 0)))
            lat_ref = gps_info.get("GPSLatitudeRef", "N")
            if lat_ref == "S":
                lat = -lat

            lon = _convert_to_degrees(gps_info.get("GPSLongitude", (0, 0, 0)))
            lon_ref = gps_info.get("GPSLongitudeRef", "E")
            if lon_ref == "W":
                lon = -lon

            return lon, lat
        except Exception:
            return None, None

    def extract_video_metadata(self, filepath: str) -> dict:
        try:
            import ffmpeg
            probe = ffmpeg.probe(filepath)
            video_info = {}
            for stream in probe.get("streams", []):
                if stream["codec_type"] == "video":
                    video_info["width"] = int(stream.get("width", 0))
                    video_info["height"] = int(stream.get("height", 0))
                    video_info["codec"] = stream.get("codec_name", "")
                    video_info["fps"] = stream.get("r_frame_rate", "")
                elif stream["codec_type"] == "audio":
                    video_info["audio_codec"] = stream.get("codec_name", "")
                    video_info["audio_sample_rate"] = stream.get("sample_rate", "")

            duration = float(probe.get("format", {}).get("duration", 0))
            video_info["duration"] = duration
            return video_info
        except Exception as e:
            logger.debug(f"Video metadata extraction failed for {filepath}: {e}")
            return {}

    def process_asset(self, asset: Asset) -> Optional[Metadata]:
        filepath = asset.absolute_path
        exif_json = None
        gps_lon = None
        gps_lat = None

        if asset.media_type == "image":
            exif_data = self.extract_exif(filepath)
            gps_lon, gps_lat = self.extract_gps(exif_data)
            exif_json = json.dumps(exif_data, default=str, ensure_ascii=False)

            try:
                from PIL import Image
                with Image.open(filepath) as img:
                    w, h = img.size
                    self.asset_dao.update_dimensions(asset.id, w, h)
            except Exception:
                pass

        elif asset.media_type == "video":
            video_meta = self.extract_video_metadata(filepath)
            exif_json = json.dumps(video_meta, default=str, ensure_ascii=False)

            if "duration" in video_meta:
                self.asset_dao.update_duration(asset.id, video_meta["duration"])
            if "width" in video_meta and "height" in video_meta:
                self.asset_dao.update_dimensions(asset.id, video_meta["width"], video_meta["height"])

        meta = Metadata(
            asset_id=asset.id,
            exif_json=exif_json,
            gps_longitude=gps_lon,
            gps_latitude=gps_lat,
        )
        self.metadata_dao.insert(meta)
        return meta

    def process_batch(self, assets: List[Asset]) -> List[Metadata]:
        results = []
        for asset in assets:
            try:
                self.asset_dao.update_status(asset.id, "processing")
                meta = self.process_asset(asset)
                if meta:
                    results.append(meta)
                self.asset_dao.update_status(asset.id, "indexed")
            except Exception as e:
                logger.error(f"Failed to process asset {asset.id}: {e}")
                self.asset_dao.update_status(asset.id, "corrupt")
        return results
