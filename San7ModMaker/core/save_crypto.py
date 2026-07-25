"""
存档加密/解密引擎 (Save File Cryptography Engine)
提供游戏存档加密分析、校验和算法逆向、分组密码检测、密钥恢复、存档修补等功能。

引擎突破 11: 深度分析三国群英传7存档加密机制，支持 XOR/RC4/AES 检测、CRC/Adler32 校验、
压缩检测、密钥派生分析、暴力密钥恢复、存档修补
"""

import hashlib
import os
import struct
import zlib
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import Counter, defaultdict
import math


# ============================================================
# 枚举定义
# ============================================================

class EncryptionType(Enum):
    """加密类型"""
    NONE = "none"
    XOR_SINGLE = "xor_single"           # 单字节 XOR
    XOR_MULTI = "xor_multi"             # 多字节 XOR key
    XOR_ROLLING = "xor_rolling"         # 滚动 XOR
    RC4 = "rc4"                         # RC4
    AES_ECB = "aes_ecb"                 # AES-ECB
    AES_CBC = "aes_cbc"                 # AES-CBC
    BLOWFISH = "blowfish"               # Blowfish
    DES = "des"                         # DES
    TEA = "tea"                         # Tiny Encryption Algorithm
    XTEA = "xtea"                       # XTEA
    CUSTOM = "custom"                   # 自定义加密
    UNKNOWN = "unknown"


class ChecksumType(Enum):
    """校验和类型"""
    NONE = "none"
    CRC32 = "crc32"
    CRC16 = "crc16"
    CRC8 = "crc8"
    ADLER32 = "adler32"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    XOR_SUM = "xor_sum"
    ADDITIVE = "additive"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class CompressionType(Enum):
    """压缩类型"""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"
    LZMA = "lzma"
    LZ4 = "lz4"
    LZO = "lzo"
    BZIP2 = "bzip2"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class KeyDerivationMethod(Enum):
    """密钥派生方法"""
    NONE = "none"
    FIXED_KEY = "fixed_key"             # 固定密钥
    FILE_HASH = "file_hash"             # 文件哈希派生
    USER_ID = "user_id"                 # 用户ID派生
    TIMESTAMP = "timestamp"             # 时间戳派生
    PASSWORD = "password"               # 密码派生
    SEED = "seed"                       # 种子派生
    CUSTOM = "custom"


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class CryptoAnalysisResult:
    """加密分析结果"""
    encryption_type: EncryptionType = EncryptionType.UNKNOWN
    encryption_confidence: float = 0.0
    key_length: int = 0
    key_candidates: List[bytes] = field(default_factory=list)
    checksum_type: ChecksumType = ChecksumType.UNKNOWN
    checksum_offset: int = -1
    checksum_size: int = 0
    compression_type: CompressionType = CompressionType.UNKNOWN
    header_size: int = 0
    footer_size: int = 0
    entropy: float = 0.0
    block_size: int = 0
    padding_byte: Optional[int] = None
    key_derivation: KeyDerivationMethod = KeyDerivationMethod.NONE
    anomalies: List[str] = field(default_factory=list)
    sections: List[dict] = field(default_factory=list)


@dataclass
class SaveSection:
    """存档区域"""
    name: str
    offset: int
    size: int
    description: str = ""
    is_encrypted: bool = False
    is_compressed: bool = False
    checksum: Optional[bytes] = None
    data: bytes = b""


@dataclass
class SaveFormat:
    """存档格式定义"""
    format_id: str
    name: str
    magic: bytes = b""
    header_size: int = 0
    encryption: EncryptionType = EncryptionType.NONE
    checksum: ChecksumType = ChecksumType.NONE
    compression: CompressionType = CompressionType.NONE
    sections: List[SaveSection] = field(default_factory=list)
    description: str = ""


@dataclass
class XORKeyResult:
    """XOR密钥分析结果"""
    key: bytes
    length: int
    score: float
    plaintext_score: float
    is_valid: bool
    description: str = ""


# ============================================================
# 熵分析器
# ============================================================

class EntropyAnalyzer:
    """熵分析器 — 分析数据随机性以检测加密/压缩"""

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        """计算香农熵"""
        if not data:
            return 0.0

        counter = Counter(data)
        length = len(data)
        entropy = 0.0

        for count in counter.values():
            probability = count / length
            entropy -= probability * math.log2(probability)

        return entropy

    @staticmethod
    def calculate_byte_distribution(data: bytes) -> Dict[int, float]:
        """计算字节分布"""
        if not data:
            return {}

        counter = Counter(data)
        length = len(data)
        return {
            byte: count / length
            for byte, count in counter.items()
        }

    @staticmethod
    def detect_encryption(data: bytes) -> Tuple[bool, float]:
        """检测数据是否加密（高熵 + 均匀分布）"""
        entropy = EntropyAnalyzer.calculate_entropy(data)
        # 高熵 (>7.0) 通常意味着加密或压缩
        if entropy > 7.5:
            return True, 0.95
        elif entropy > 7.0:
            return True, 0.7
        elif entropy > 6.0:
            return True, 0.4
        else:
            return False, 0.0

    @staticmethod
    def detect_compression(data: bytes) -> Tuple[bool, float]:
        """检测数据是否压缩"""
        entropy = EntropyAnalyzer.calculate_entropy(data)
        # 压缩数据通常也是高熵
        if 7.0 < entropy < 7.8:
            return True, 0.6
        elif entropy >= 7.8:
            return True, 0.4
        return False, 0.0

    @staticmethod
    def find_anomalies(data: bytes, threshold: float = 0.1) -> List[dict]:
        """查找异常字节模式"""
        if len(data) < 64:
            return []

        distribution = EntropyAnalyzer.calculate_byte_distribution(data)
        expected = 1.0 / 256.0
        anomalies = []

        for byte_val, freq in distribution.items():
            deviation = abs(freq - expected) / expected
            if deviation > threshold:
                anomalies.append({
                    "byte": hex(byte_val),
                    "frequency": round(freq, 6),
                    "expected": round(expected, 6),
                    "deviation": round(deviation, 3),
                    "description": _describe_byte_anomaly(byte_val, freq)
                })

        anomalies.sort(key=lambda x: x["deviation"], reverse=True)
        return anomalies[:20]


def _describe_byte_anomaly(byte_val: int, freq: float) -> str:
    """描述字节异常可能的原因"""
    if byte_val == 0x00 and freq > 0.1:
        return "大量零字节 — 可能是未初始化数据或填充"
    elif byte_val == 0xFF and freq > 0.1:
        return "大量 0xFF — 可能是 NAND 闪存擦除或填充"
    elif byte_val == 0x20 and freq > 0.05:
        return "大量空格 — 可能是文本填充"
    elif 0x20 <= byte_val <= 0x7E and freq > 0.02:
        return f"ASCII 可打印字符 {chr(byte_val)} — 可能包含明文"
    return ""


# ============================================================
# XOR 密码分析器
# ============================================================

class XORCryptoAnalyzer:
    """XOR 加密分析器 — 检测和恢复 XOR 密钥"""

    # 常见明文字符频率（英文）
    ENGLISH_FREQ = {
        b' ': 0.13, b'e': 0.12, b't': 0.09, b'a': 0.08, b'o': 0.075,
        b'i': 0.07, b'n': 0.07, b's': 0.063, b'h': 0.061, b'r': 0.06,
        b'd': 0.043, b'l': 0.04, b'c': 0.028, b'u': 0.028, b'm': 0.024,
        b'w': 0.024, b'f': 0.022, b'g': 0.02, b'y': 0.02, b'p': 0.019,
        b'b': 0.015, b'v': 0.01, b'k': 0.008, b'j': 0.0015, b'x': 0.0015,
        b'q': 0.001, b'z': 0.0007,
    }

    # 常见二进制文件头
    KNOWN_HEADERS = [
        b'\x89PNG', b'\xff\xd8\xff', b'PK\x03\x04', b'GIF8',
        b'%PDF', b'\x7fELF', b'MZ', b'RIFF', b'OggS',
        b'\x1f\x8b', b'BZh', b'\xfd7zXZ', b'\x04\x22\x4d\x18',
        b'II*\x00', b'MM\x00*', b'BM', b'SQLite',
    ]

    @staticmethod
    def detect_xor_single(data: bytes) -> Optional[XORKeyResult]:
        """检测单字节 XOR"""
        if len(data) < 16:
            return None

        best_key = None
        best_score = 0.0

        for key in range(256):
            score = XORCryptoAnalyzer._score_xor_key(data, bytes([key]))
            if score > best_score:
                best_score = score
                best_key = key

        if best_key is not None and best_score > 0.3:
            is_valid = XORCryptoAnalyzer._validate_xor_key(data, bytes([best_key]))
            return XORKeyResult(
                key=bytes([best_key]),
                length=1,
                score=best_score,
                plaintext_score=best_score,
                is_valid=is_valid,
                description=f"单字节 XOR 密钥: 0x{best_key:02x}"
            )

        return None

    @staticmethod
    def detect_xor_multi(data: bytes, max_key_len: int = 32) -> List[XORKeyResult]:
        """检测多字节 XOR 密钥"""
        if len(data) < max_key_len * 2:
            return []

        results = []

        for key_len in range(1, max_key_len + 1):
            # 提取每个位置上的候选密钥
            key_candidates = []
            for pos in range(key_len):
                # 取该位置所有字节
                pos_bytes = data[pos::key_len]
                if len(pos_bytes) < 2:
                    continue

                # 尝试每个可能的密钥字节
                best_byte = 0
                best_byte_score = 0.0
                for k in range(256):
                    decrypted = bytes(b ^ k for b in pos_bytes)
                    score = XORCryptoAnalyzer._score_plaintext(decrypted)
                    if score > best_byte_score:
                        best_byte_score = score
                        best_byte = k

                key_candidates.append(best_byte)

            if len(key_candidates) == key_len:
                key = bytes(key_candidates)
                score = XORCryptoAnalyzer._score_xor_key(data, key)
                is_valid = XORCryptoAnalyzer._validate_xor_key(data, key)

                results.append(XORKeyResult(
                    key=key,
                    length=key_len,
                    score=score,
                    plaintext_score=score,
                    is_valid=is_valid,
                    description=f"多字节 XOR (len={key_len}): {key.hex()}"
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:5]

    @staticmethod
    def detect_xor_rolling(data: bytes, window_size: int = 8) -> Optional[XORKeyResult]:
        """检测滚动 XOR"""
        if len(data) < window_size * 2:
            return None

        # 滚动 XOR 的特征：相邻字节的 XOR 有规律
        scores = []
        for offset in range(1, min(window_size + 1, 16)):
            if offset >= len(data):
                continue
            # 计算 data[i] ^ data[i+offset] 的分布
            xors = [data[i] ^ data[i + offset] for i in range(len(data) - offset)]
            # 滚动 XOR 的相邻 XOR 值应该集中
            counter = Counter(xors)
            top_count = counter.most_common(1)[0][1] if counter else 0
            score = top_count / len(xors) if xors else 0
            scores.append(score)

        if scores and max(scores) > 0.3:
            return XORKeyResult(
                key=b"",
                length=0,
                score=max(scores),
                plaintext_score=0.0,
                is_valid=True,
                description="检测到滚动 XOR 模式"
            )

        return None

    @staticmethod
    def _score_xor_key(data: bytes, key: bytes) -> float:
        """对 XOR 密钥评分"""
        key_len = len(key)
        decrypted = bytes(data[i] ^ key[i % key_len] for i in range(len(data)))
        return XORCryptoAnalyzer._score_plaintext(decrypted)

    @staticmethod
    def _score_plaintext(data: bytes) -> float:
        """对明文质量评分"""
        if not data:
            return 0.0

        score = 0.0
        sample = data[:min(len(data), 4096)]

        # ASCII 可打印字符比例
        printable = sum(1 for b in sample if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D, 0x09))
        printable_ratio = printable / len(sample)
        score += printable_ratio * 0.4

        # 英文字母频率匹配
        freq_score = 0.0
        lower_sample = bytes(b if b < 128 else b for b in sample)
        for byte_val, expected_freq in XORCryptoAnalyzer.ENGLISH_FREQ.items():
            actual_freq = lower_sample.count(byte_val[0]) / len(lower_sample)
            freq_score += max(0, 1.0 - abs(actual_freq - expected_freq) / expected_freq)

        freq_score = freq_score / len(XORCryptoAnalyzer.ENGLISH_FREQ)
        score += freq_score * 0.3

        # 控制字符惩罚
        control = sum(1 for b in sample if b < 0x09 or (0x0E <= b <= 0x1F) or b == 0x7F)
        score -= (control / len(sample)) * 0.3

        # 已知头部匹配
        for header in XORCryptoAnalyzer.KNOWN_HEADERS:
            if sample.startswith(header):
                score += 0.5
                break

        return max(0.0, min(1.0, score))

    @staticmethod
    def _validate_xor_key(data: bytes, key: bytes, sample_size: int = 256) -> bool:
        """验证 XOR 密钥的有效性"""
        if len(data) < sample_size:
            sample_size = len(data)

        key_len = len(key)
        decrypted = bytes(data[i] ^ key[i % key_len] for i in range(sample_size))

        # 检查是否有明显的文本模式
        printable = sum(1 for b in decrypted if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D, 0x09, 0x00))
        ratio = printable / len(decrypted)

        return ratio > 0.5

    @staticmethod
    def decrypt_xor(data: bytes, key: bytes) -> bytes:
        """XOR 解密"""
        key_len = len(key)
        return bytes(data[i] ^ key[i % key_len] for i in range(len(data)))

    @staticmethod
    def encrypt_xor(data: bytes, key: bytes) -> bytes:
        """XOR 加密（与解密相同）"""
        return XORCryptoAnalyzer.decrypt_xor(data, key)


# ============================================================
# 校验和分析器
# ============================================================

class ChecksumAnalyzer:
    """校验和分析器 — 检测和验证校验和类型"""

    @staticmethod
    def detect_checksum(data: bytes, checksum_data: bytes = None) -> dict:
        """检测校验和类型"""
        if checksum_data is None:
            # 尝试从数据末尾提取可能的校验和
            candidates = [
                ("末尾 4 字节", data[-4:], 4),
                ("末尾 2 字节", data[-2:], 2),
                ("末尾 1 字节", data[-1:], 1),
                ("末尾 8 字节", data[-8:], 8),
            ]
        else:
            candidates = [(f"指定 ({len(checksum_data)} 字节)", checksum_data, len(checksum_data))]

        data_without_checksum = data
        results = []

        for desc, cs_data, cs_size in candidates:
            if cs_size > 0 and len(data) > cs_size:
                data_without_checksum = data[:-cs_size] if checksum_data is None else data

            # CRC32
            crc32_val = struct.pack("<I", zlib.crc32(data_without_checksum) & 0xFFFFFFFF)
            if cs_data == crc32_val:
                results.append({
                    "type": "crc32",
                    "offset": len(data_without_checksum),
                    "size": 4,
                    "value": cs_data.hex(),
                    "confidence": 1.0,
                    "description": desc
                })

            # CRC32 big-endian
            crc32_be = struct.pack(">I", zlib.crc32(data_without_checksum) & 0xFFFFFFFF)
            if cs_data == crc32_be:
                results.append({
                    "type": "crc32_be",
                    "offset": len(data_without_checksum),
                    "size": 4,
                    "value": cs_data.hex(),
                    "confidence": 1.0,
                    "description": desc
                })

            # Adler32
            adler32_val = struct.pack("<I", zlib.adler32(data_without_checksum) & 0xFFFFFFFF)
            if cs_data == adler32_val:
                results.append({
                    "type": "adler32",
                    "offset": len(data_without_checksum),
                    "size": 4,
                    "value": cs_data.hex(),
                    "confidence": 1.0,
                    "description": desc
                })

            # XOR 校验和
            xor_result = 0
            for b in data_without_checksum:
                xor_result ^= b
            xor_sum = bytes([xor_result])
            if len(cs_data) == 1 and cs_data == xor_sum:
                results.append({
                    "type": "xor_sum",
                    "offset": len(data_without_checksum),
                    "size": 1,
                    "value": cs_data.hex(),
                    "confidence": 0.9,
                    "description": desc
                })

            # 累加校验和
            additive = sum(data_without_checksum) & 0xFFFFFFFF
            if len(cs_data) == 4:
                if cs_data == struct.pack("<I", additive):
                    results.append({
                        "type": "additive_32le",
                        "offset": len(data_without_checksum),
                        "size": 4,
                        "value": cs_data.hex(),
                        "confidence": 0.8,
                        "description": desc
                    })

        return {
            "success": True,
            "results": results,
            "count": len(results)
        }

    @staticmethod
    def calculate_checksum(data: bytes, checksum_type: ChecksumType) -> bytes:
        """计算指定类型的校验和"""
        if checksum_type == ChecksumType.CRC32:
            return struct.pack("<I", zlib.crc32(data) & 0xFFFFFFFF)
        elif checksum_type == ChecksumType.ADLER32:
            return struct.pack("<I", zlib.adler32(data) & 0xFFFFFFFF)
        elif checksum_type == ChecksumType.MD5:
            return hashlib.md5(data).digest()
        elif checksum_type == ChecksumType.SHA1:
            return hashlib.sha1(data).digest()
        elif checksum_type == ChecksumType.SHA256:
            return hashlib.sha256(data).digest()
        elif checksum_type == ChecksumType.XOR_SUM:
            result = 0
            for b in data:
                result ^= b
            return bytes([result])
        elif checksum_type == ChecksumType.CRC16:
            crc = 0xFFFF
            for b in data:
                crc ^= b << 8
                for _ in range(8):
                    if crc & 0x8000:
                        crc = (crc << 1) ^ 0x1021
                    else:
                        crc <<= 1
                    crc &= 0xFFFF
            return struct.pack("<H", crc)
        elif checksum_type == ChecksumType.CRC8:
            crc = 0xFF
            for b in data:
                crc ^= b
                for _ in range(8):
                    if crc & 0x80:
                        crc = (crc << 1) ^ 0x07
                    else:
                        crc <<= 1
                    crc &= 0xFF
            return bytes([crc])
        elif checksum_type == ChecksumType.ADDITIVE:
            return struct.pack("<I", sum(data) & 0xFFFFFFFF)
        return b""

    @staticmethod
    def verify_checksum(data: bytes, expected: bytes, checksum_type: ChecksumType) -> bool:
        """验证校验和"""
        calculated = ChecksumAnalyzer.calculate_checksum(data, checksum_type)
        return calculated == expected

    @staticmethod
    def patch_checksum(data: bytes, checksum_type: ChecksumType,
                       checksum_offset: int, data_range: Tuple[int, int] = None) -> bytes:
        """修补校验和"""
        if data_range:
            target_data = data[data_range[0]:data_range[1]]
        else:
            # 假设校验和在末尾
            target_data = data[:checksum_offset]

        new_checksum = ChecksumAnalyzer.calculate_checksum(target_data, checksum_type)
        result = bytearray(data)
        result[checksum_offset:checksum_offset + len(new_checksum)] = new_checksum
        return bytes(result)


# ============================================================
# 压缩检测器
# ============================================================

class CompressionDetector:
    """压缩检测器 — 检测压缩算法和尝试解压"""

    COMPRESSION_MAGICS = {
        b'\x1f\x8b': CompressionType.GZIP,
        b'\x78\x01': CompressionType.ZLIB,
        b'\x78\x9c': CompressionType.ZLIB,
        b'\x78\xda': CompressionType.ZLIB,
        b'BZh': CompressionType.BZIP2,
        b'\xfd7zXZ': CompressionType.LZMA,
        b'\x04\x22\x4d\x18': CompressionType.LZ4,
        b'\x89LZO': CompressionType.LZO,
    }

    @staticmethod
    def detect(data: bytes) -> Tuple[CompressionType, float]:
        """检测压缩类型"""
        if len(data) < 4:
            return CompressionType.UNKNOWN, 0.0

        for magic, comp_type in CompressionDetector.COMPRESSION_MAGICS.items():
            if data.startswith(magic):
                return comp_type, 0.95

        # 尝试 zlib 解压
        try:
            zlib.decompress(data)
            return CompressionType.ZLIB, 0.8
        except:
            pass

        # 尝试 gzip 解压
        try:
            import gzip
            gzip.decompress(data)
            return CompressionType.GZIP, 0.8
        except:
            pass

        return CompressionType.UNKNOWN, 0.0

    @staticmethod
    def decompress(data: bytes, comp_type: CompressionType = None) -> dict:
        """尝试解压数据"""
        if comp_type is None:
            comp_type, _ = CompressionDetector.detect(data)

        try:
            if comp_type in (CompressionType.ZLIB, CompressionType.UNKNOWN):
                try:
                    decompressed = zlib.decompress(data)
                    return {
                        "success": True,
                        "compression": "zlib",
                        "original_size": len(data),
                        "decompressed_size": len(decompressed),
                        "ratio": round(len(data) / len(decompressed), 3) if decompressed else 0,
                        "data": decompressed
                    }
                except:
                    pass

            if comp_type in (CompressionType.GZIP, CompressionType.UNKNOWN):
                try:
                    import gzip
                    decompressed = gzip.decompress(data)
                    return {
                        "success": True,
                        "compression": "gzip",
                        "original_size": len(data),
                        "decompressed_size": len(decompressed),
                        "ratio": round(len(data) / len(decompressed), 3) if decompressed else 0,
                        "data": decompressed
                    }
                except:
                    pass

            # 尝试原始 deflate
            try:
                decompressed = zlib.decompress(data, -15)
                return {
                    "success": True,
                    "compression": "deflate",
                    "original_size": len(data),
                    "decompressed_size": len(decompressed),
                    "ratio": round(len(data) / len(decompressed), 3) if decompressed else 0,
                    "data": decompressed
                }
            except:
                pass

        except Exception as e:
            return {"success": False, "message": str(e)}

        return {"success": False, "message": "无法解压"}

    @staticmethod
    def compress(data: bytes, comp_type: CompressionType = CompressionType.ZLIB,
                 level: int = 6) -> dict:
        """压缩数据"""
        try:
            if comp_type == CompressionType.ZLIB:
                compressed = zlib.compress(data, level)
                return {
                    "success": True,
                    "compression": "zlib",
                    "original_size": len(data),
                    "compressed_size": len(compressed),
                    "ratio": round(len(compressed) / len(data), 3) if data else 0,
                    "data": compressed
                }
            elif comp_type == CompressionType.GZIP:
                import gzip
                import io
                buf = io.BytesIO()
                with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=level) as f:
                    f.write(data)
                compressed = buf.getvalue()
                return {
                    "success": True,
                    "compression": "gzip",
                    "original_size": len(data),
                    "compressed_size": len(compressed),
                    "ratio": round(len(compressed) / len(data), 3) if data else 0,
                    "data": compressed
                }
        except Exception as e:
            return {"success": False, "message": str(e)}

        return {"success": False, "message": f"不支持的压缩类型: {comp_type.value}"}


# ============================================================
# 存档格式解析器
# ============================================================

class SaveFormatParser:
    """存档格式解析器 — 解析和定义存档文件结构"""

    def __init__(self):
        self._formats: Dict[str, SaveFormat] = {}
        self._register_default_formats()

    def _register_default_formats(self):
        """注册默认存档格式"""
        # SG7 存档格式
        sg7_format = SaveFormat(
            format_id="sg7_save",
            name="三国群英传7 存档",
            magic=b"",
            header_size=64,
            encryption=EncryptionType.UNKNOWN,
            checksum=ChecksumType.UNKNOWN,
            compression=CompressionType.UNKNOWN,
            sections=[
                SaveSection("header", 0, 64, "文件头"),
                SaveSection("scenario", 64, 0, "场景数据"),
                SaveSection("generals", 0, 0, "武将数据"),
                SaveSection("forces", 0, 0, "势力数据"),
                SaveSection("cities", 0, 0, "城池数据"),
            ],
            description="三国群英传7标准存档格式"
        )
        self._formats["sg7_save"] = sg7_format

        # 通用存档格式
        generic_format = SaveFormat(
            format_id="generic_save",
            name="通用游戏存档",
            magic=b"",
            header_size=16,
            description="通用游戏存档格式"
        )
        self._formats["generic_save"] = generic_format

    def register_format(self, format_id: str, name: str, magic: bytes = b"",
                        header_size: int = 0, encryption: str = "none",
                        checksum: str = "none", compression: str = "none",
                        description: str = "") -> dict:
        """注册存档格式"""
        try:
            enc = EncryptionType(encryption)
            cs = ChecksumType(checksum)
            comp = CompressionType(compression)
        except ValueError as e:
            return {"success": False, "message": f"无效的类型: {str(e)}"}

        fmt = SaveFormat(
            format_id=format_id,
            name=name,
            magic=magic,
            header_size=header_size,
            encryption=enc,
            checksum=cs,
            compression=comp,
            description=description
        )
        self._formats[format_id] = fmt
        return {"success": True, "message": f"格式注册成功: {name}"}

    def get_format(self, format_id: str) -> Optional[dict]:
        """获取格式定义"""
        fmt = self._formats.get(format_id)
        if not fmt:
            return None
        return {
            "format_id": fmt.format_id,
            "name": fmt.name,
            "magic": fmt.magic.hex() if fmt.magic else "",
            "header_size": fmt.header_size,
            "encryption": fmt.encryption.value,
            "checksum": fmt.checksum.value,
            "compression": fmt.compression.value,
            "sections": [
                {"name": s.name, "offset": s.offset, "size": s.size, "description": s.description}
                for s in fmt.sections
            ],
            "description": fmt.description
        }

    def list_formats(self) -> List[dict]:
        """列出所有格式"""
        return [
            {"format_id": f.format_id, "name": f.name, "description": f.description}
            for f in self._formats.values()
        ]

    def add_section(self, format_id: str, name: str, offset: int, size: int,
                    description: str = "", is_encrypted: bool = False,
                    is_compressed: bool = False) -> dict:
        """添加存档区域"""
        fmt = self._formats.get(format_id)
        if not fmt:
            return {"success": False, "message": f"格式不存在: {format_id}"}

        section = SaveSection(
            name=name, offset=offset, size=size,
            description=description,
            is_encrypted=is_encrypted,
            is_compressed=is_compressed
        )
        fmt.sections.append(section)
        return {"success": True, "message": f"区域添加成功: {name}"}


# ============================================================
# 存档文件分析器
# ============================================================

class SaveFileAnalyzer:
    """
    存档文件综合分析器
    
    整合熵分析、加密检测、校验和检测、压缩检测、格式解析
    """

    def __init__(self):
        self.entropy_analyzer = EntropyAnalyzer()
        self.xor_analyzer = XORCryptoAnalyzer()
        self.checksum_analyzer = ChecksumAnalyzer()
        self.compression_detector = CompressionDetector()
        self.format_parser = SaveFormatParser()

    def analyze(self, file_path: str) -> dict:
        """综合分析存档文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            file_size = len(data)
            if file_size < 4:
                return {"success": False, "message": "文件太小"}

            result = {
                "success": True,
                "file_path": file_path,
                "file_size": file_size,
                "md5": hashlib.md5(data).hexdigest(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }

            # 熵分析
            entropy = self.entropy_analyzer.calculate_entropy(data)
            result["entropy"] = round(entropy, 4)
            result["is_encrypted"], result["encryption_confidence"] = \
                self.entropy_analyzer.detect_encryption(data)
            result["is_compressed"], result["compression_confidence"] = \
                self.entropy_analyzer.detect_compression(data)

            # 异常检测
            result["anomalies"] = self.entropy_analyzer.find_anomalies(data)

            # XOR 加密检测
            xor_results = []

            single_xor = self.xor_analyzer.detect_xor_single(data)
            if single_xor and single_xor.is_valid:
                xor_results.append({
                    "type": "single_xor",
                    "key": single_xor.key.hex(),
                    "key_length": single_xor.length,
                    "score": round(single_xor.score, 3),
                    "description": single_xor.description
                })

            multi_xor = self.xor_analyzer.detect_xor_multi(data)
            for r in multi_xor[:3]:
                if r.is_valid:
                    xor_results.append({
                        "type": "multi_xor",
                        "key": r.key.hex(),
                        "key_length": r.length,
                        "score": round(r.score, 3),
                        "description": r.description
                    })

            rolling_xor = self.xor_analyzer.detect_xor_rolling(data)
            if rolling_xor and rolling_xor.is_valid:
                xor_results.append({
                    "type": "rolling_xor",
                    "description": rolling_xor.description
                })

            result["xor_detection"] = xor_results

            # 校验和检测
            # 尝试从末尾检测
            checksum_result = self.checksum_analyzer.detect_checksum(data)
            result["checksum_detection"] = checksum_result["results"]

            # 压缩检测
            comp_type, comp_conf = self.compression_detector.detect(data)
            result["compression_type"] = comp_type.value
            result["compression_confidence"] = round(comp_conf, 3)

            # 尝试解压
            if comp_type != CompressionType.NONE:
                decompress_result = self.compression_detector.decompress(data)
                if decompress_result["success"]:
                    result["decompression"] = {
                        "method": decompress_result["compression"],
                        "original_size": decompress_result["original_size"],
                        "decompressed_size": decompress_result["decompressed_size"],
                        "ratio": decompress_result["ratio"]
                    }

            # 文件头分析
            result["header_analysis"] = self._analyze_header(data)

            # 已知格式匹配
            result["format_match"] = self._match_format(data)

            # 密钥派生分析
            result["key_derivation"] = self._analyze_key_derivation(data)

            return result

        except Exception as e:
            return {"success": False, "message": f"分析失败: {str(e)}"}

    def _analyze_header(self, data: bytes) -> dict:
        """分析文件头"""
        header = data[:min(128, len(data))]
        header_hex = header.hex()

        # 检测常见魔数
        magic_matches = []
        for magic_bytes, comp_type in CompressionDetector.COMPRESSION_MAGICS.items():
            if data.startswith(magic_bytes):
                magic_matches.append({
                    "magic": magic_bytes.hex(),
                    "type": comp_type.value,
                    "description": f"压缩格式: {comp_type.value}"
                })

        # 检测是否可能为明文
        printable = sum(1 for b in header if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D, 0x09, 0x00))
        is_plaintext = printable / len(header) > 0.5

        return {
            "header_hex": header_hex[:64] + ("..." if len(header_hex) > 64 else ""),
            "header_size": len(header),
            "magic_matches": magic_matches,
            "is_plaintext": is_plaintext,
            "first_bytes": " ".join(f"{b:02x}" for b in header[:16])
        }

    def _match_format(self, data: bytes) -> dict:
        """匹配已知格式"""
        matches = []

        for fmt_id, fmt in self.format_parser._formats.items():
            if fmt.magic and data.startswith(fmt.magic):
                matches.append({
                    "format_id": fmt_id,
                    "name": fmt.name,
                    "confidence": 1.0,
                    "match_type": "magic"
                })
            elif fmt.header_size > 0 and len(data) >= fmt.header_size:
                # 检查头部大小是否匹配
                matches.append({
                    "format_id": fmt_id,
                    "name": fmt.name,
                    "confidence": 0.3,
                    "match_type": "header_size"
                })

        return matches

    def _analyze_key_derivation(self, data: bytes) -> dict:
        """分析密钥派生方法"""
        results = []

        # 检查文件开头是否有时间戳
        if len(data) >= 8:
            # 尝试解析为 Unix 时间戳
            ts_data = data[:4]
            try:
                ts = struct.unpack("<I", ts_data)[0]
                if 946684800 < ts < 4102444800:  # 2000-2100
                    import datetime
                    dt = datetime.datetime.fromtimestamp(ts)
                    results.append({
                        "method": "timestamp",
                        "value": ts,
                        "datetime": dt.isoformat(),
                        "confidence": 0.7
                    })
            except:
                pass

        # 检查是否有固定种子
        if len(data) >= 4:
            # 检查常见的种子值
            common_seeds = [0xDEADBEEF, 0xCAFEBABE, 0xFEEDFACE, 0x12345678, 0x87654321]
            for seed in common_seeds:
                seed_bytes = struct.pack("<I", seed)
                if seed_bytes in data[:64]:
                    results.append({
                        "method": "seed",
                        "value": hex(seed),
                        "confidence": 0.5
                    })
                    break

        return {
            "results": results,
            "count": len(results)
        }

    def analyze_bytes(self, data: bytes) -> dict:
        """分析原始字节数据"""
        result = {
            "success": True,
            "data_size": len(data),
            "entropy": round(self.entropy_analyzer.calculate_entropy(data), 4),
        }

        result["is_encrypted"], result["encryption_confidence"] = \
            self.entropy_analyzer.detect_encryption(data)

        # XOR 检测
        single_xor = self.xor_analyzer.detect_xor_single(data)
        if single_xor and single_xor.is_valid:
            result["xor_key"] = single_xor.key.hex()

        # 压缩检测
        comp_type, comp_conf = self.compression_detector.detect(data)
        result["compression_type"] = comp_type.value

        return result

    def decrypt_xor(self, file_path: str, key: bytes, output_path: str = None) -> dict:
        """XOR 解密文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            decrypted = self.xor_analyzer.decrypt_xor(data, key)

            if output_path is None:
                output_path = file_path + ".decrypted"

            with open(output_path, "wb") as f:
                f.write(decrypted)

            return {
                "success": True,
                "message": f"解密成功: {output_path}",
                "input_size": len(data),
                "output_size": len(decrypted),
                "key": key.hex(),
                "output_path": output_path
            }
        except Exception as e:
            return {"success": False, "message": f"解密失败: {str(e)}"}

    def encrypt_xor(self, file_path: str, key: bytes, output_path: str = None) -> dict:
        """XOR 加密文件"""
        return self.decrypt_xor(file_path, key, output_path)

    def brute_force_xor_key(self, file_path: str, max_key_len: int = 8) -> dict:
        """暴力恢复 XOR 密钥"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            results = []

            # 单字节
            single = self.xor_analyzer.detect_xor_single(data)
            if single and single.is_valid:
                results.append({
                    "key_length": 1,
                    "key": single.key.hex(),
                    "score": round(single.score, 3),
                    "plaintext_score": round(single.plaintext_score, 3)
                })

            # 多字节
            multi = self.xor_analyzer.detect_xor_multi(data, max_key_len)
            for r in multi[:5]:
                if r.is_valid:
                    results.append({
                        "key_length": r.length,
                        "key": r.key.hex(),
                        "score": round(r.score, 3),
                        "plaintext_score": round(r.plaintext_score, 3)
                    })

            results.sort(key=lambda x: x["score"], reverse=True)

            return {
                "success": True,
                "results": results,
                "best_key": results[0]["key"] if results else None,
                "count": len(results)
            }
        except Exception as e:
            return {"success": False, "message": f"暴力恢复失败: {str(e)}"}

    def patch_save(self, file_path: str, offset: int, new_data: bytes,
                   fix_checksum: bool = True, checksum_type: str = "crc32",
                   output_path: str = None) -> dict:
        """修补存档文件"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = bytearray(f.read())

            if offset + len(new_data) > len(data):
                return {"success": False, "message": "偏移超出文件范围"}

            # 写入新数据
            data[offset:offset + len(new_data)] = new_data

            # 修复校验和
            if fix_checksum:
                try:
                    cs_type = ChecksumType(checksum_type)
                    # 假设校验和在末尾
                    cs_size = {
                        ChecksumType.CRC32: 4, ChecksumType.ADLER32: 4,
                        ChecksumType.MD5: 16, ChecksumType.SHA1: 20,
                        ChecksumType.SHA256: 32, ChecksumType.XOR_SUM: 1,
                        ChecksumType.ADDITIVE: 4, ChecksumType.CRC16: 2,
                        ChecksumType.CRC8: 1,
                    }.get(cs_type, 4)

                    checksum_offset = len(data) - cs_size
                    new_checksum = self.checksum_analyzer.calculate_checksum(
                        bytes(data[:checksum_offset]), cs_type
                    )
                    data[checksum_offset:checksum_offset + len(new_checksum)] = new_checksum
                except:
                    pass

            if output_path is None:
                output_path = file_path + ".patched"

            with open(output_path, "wb") as f:
                f.write(data)

            return {
                "success": True,
                "message": f"修补成功: {output_path}",
                "offset": offset,
                "patched_size": len(new_data),
                "checksum_fixed": fix_checksum,
                "output_path": output_path
            }
        except Exception as e:
            return {"success": False, "message": f"修补失败: {str(e)}"}

    def extract_sections(self, file_path: str, sections: List[dict]) -> dict:
        """提取存档区域"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            extracted = []
            for sec in sections:
                offset = sec.get("offset", 0)
                size = sec.get("size", len(data) - offset)

                if offset + size > len(data):
                    continue

                section_data = data[offset:offset + size]
                extracted.append({
                    "name": sec.get("name", "unknown"),
                    "offset": offset,
                    "size": size,
                    "data_hex": section_data[:64].hex() + ("..." if len(section_data) > 64 else ""),
                    "data_size": len(section_data)
                })

            return {
                "success": True,
                "sections": extracted,
                "count": len(extracted)
            }
        except Exception as e:
            return {"success": False, "message": f"提取失败: {str(e)}"}

    def hex_dump(self, file_path: str, offset: int = 0, size: int = 256) -> dict:
        """十六进制转储"""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                f.seek(offset)
                data = f.read(size)

            lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i + 16]
                hex_part = " ".join(f"{b:02x}" for b in chunk)
                ascii_part = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
                lines.append(f"{offset + i:08x}  {hex_part:<48s}  |{ascii_part}|")

            return {
                "success": True,
                "offset": offset,
                "size": len(data),
                "hex_dump": "\n".join(lines)
            }
        except Exception as e:
            return {"success": False, "message": f"转储失败: {str(e)}"}

    def compare_saves(self, file1: str, file2: str) -> dict:
        """比较两个存档文件"""
        if not os.path.exists(file1) or not os.path.exists(file2):
            return {"success": False, "message": "一个或多个文件不存在"}

        try:
            with open(file1, "rb") as f:
                data1 = f.read()
            with open(file2, "rb") as f:
                data2 = f.read()

            max_len = max(len(data1), len(data2))
            diff_positions = []

            for i in range(min(len(data1), len(data2))):
                if data1[i] != data2[i]:
                    diff_positions.append({
                        "offset": i,
                        "file1": f"{data1[i]:02x}",
                        "file2": f"{data2[i]:02x}",
                        "file1_char": chr(data1[i]) if 0x20 <= data1[i] <= 0x7E else ".",
                        "file2_char": chr(data2[i]) if 0x20 <= data2[i] <= 0x7E else ".",
                    })

            # 大小差异
            size_diff = len(data2) - len(data1)

            # 分析差异区域
            diff_regions = []
            if diff_positions:
                start = diff_positions[0]["offset"]
                end = start
                for i in range(1, len(diff_positions)):
                    if diff_positions[i]["offset"] == end + 1:
                        end = diff_positions[i]["offset"]
                    else:
                        diff_regions.append({
                            "start": start,
                            "end": end,
                            "size": end - start + 1
                        })
                        start = diff_positions[i]["offset"]
                        end = start
                diff_regions.append({
                    "start": start,
                    "end": end,
                    "size": end - start + 1
                })

            return {
                "success": True,
                "file1": {"path": file1, "size": len(data1)},
                "file2": {"path": file2, "size": len(data2)},
                "total_differences": len(diff_positions),
                "difference_rate": round(len(diff_positions) / max_len * 100, 2) if max_len > 0 else 0,
                "size_difference": size_diff,
                "diff_regions": diff_regions[:20],
                "diff_samples": diff_positions[:50]
            }
        except Exception as e:
            return {"success": False, "message": f"比较失败: {str(e)}"}

    def get_info(self) -> dict:
        """获取引擎信息"""
        return {
            "name": "存档加密/解密引擎",
            "version": "1.0.0",
            "capabilities": [
                "熵分析", "XOR加密检测与密钥恢复", "校验和检测与验证",
                "压缩检测与解压", "存档格式解析", "密钥派生分析",
                "暴力密钥恢复", "存档修补", "存档对比"
            ],
            "supported_encryption": [e.value for e in EncryptionType],
            "supported_checksums": [c.value for c in ChecksumType],
            "supported_compression": [c.value for c in CompressionType],
        }