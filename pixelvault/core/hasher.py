import hashlib
import logging
from typing import Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)


def compute_md5(filepath: str, chunk_size: int = 8192) -> str:
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    return md5.hexdigest()


def compute_sha256(filepath: str, chunk_size: int = 8192) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            sha.update(chunk)
    return sha.hexdigest()


def compute_phash(image: np.ndarray, hash_size: int = 8) -> str:
    try:
        import cv2
        if image is None or image.size == 0:
            return ""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        resized = cv2.resize(gray, (hash_size * 4, hash_size * 4), interpolation=cv2.INTER_AREA)
        dct = cv2.dct(np.float32(resized))
        dct_low = dct[:hash_size, :hash_size]
        median = np.median(dct_low)
        bits = (dct_low > median).flatten()
        return _bits_to_hex(bits)
    except Exception as e:
        logger.warning(f"pHash computation failed: {e}")
        return ""


def compute_dhash(image: np.ndarray, hash_size: int = 8) -> str:
    try:
        import cv2
        if image is None or image.size == 0:
            return ""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        bits = diff.flatten()
        return _bits_to_hex(bits)
    except Exception as e:
        logger.warning(f"dHash computation failed: {e}")
        return ""


def hamming_distance(hash1: str, hash2: str) -> int:
    if len(hash1) != len(hash2):
        return -1
    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    xor = val1 ^ val2
    return bin(xor).count("1")


def phash_similarity(hash1: str, hash2: str) -> float:
    dist = hamming_distance(hash1, hash2)
    if dist < 0:
        return 0.0
    total_bits = len(hash1) * 4
    return 1.0 - (dist / total_bits)


def _bits_to_hex(bits: np.ndarray) -> str:
    result = 0
    for bit in bits:
        result = (result << 1) | int(bit)
    hex_str = format(result, "0" + str(len(bits) // 4) + "x")
    return hex_str
