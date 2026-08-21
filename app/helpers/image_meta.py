import zlib
from typing import Any

from app.helpers.image import format_of

_MAX_TEXT_BYTES = 8192
_SKIP_PNG_TEXT_KEYS = frozenset({"XML:com.adobe.xmp"})


def _png_size(image_bytes: bytes) -> tuple[int, int] | None:
    if len(image_bytes) < 24:
        return None
    width = int.from_bytes(image_bytes[16:20], "big")
    height = int.from_bytes(image_bytes[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return width, height


def _gif_size(image_bytes: bytes) -> tuple[int, int] | None:
    if len(image_bytes) < 10:
        return None
    width = int.from_bytes(image_bytes[6:8], "little")
    height = int.from_bytes(image_bytes[8:10], "little")
    if width <= 0 or height <= 0:
        return None
    return width, height


def _jpeg_size(image_bytes: bytes) -> tuple[int, int] | None:
    i = 2
    length = len(image_bytes)
    while i < length - 8:
        if image_bytes[i] != 0xFF:
            return None
        marker = image_bytes[i + 1]
        if marker in {0xC0, 0xC1, 0xC2}:
            height = int.from_bytes(image_bytes[i + 5 : i + 7], "big")
            width = int.from_bytes(image_bytes[i + 7 : i + 9], "big")
            if width <= 0 or height <= 0:
                return None
            return width, height
        if marker in {0xD8, 0xD9}:
            i += 2
            continue
        segment_length = int.from_bytes(image_bytes[i + 2 : i + 4], "big")
        if segment_length < 2:
            return None
        i += 2 + segment_length
    return None


def _inflate(data: bytes) -> bytes | None:
    decoder = zlib.decompressobj()
    try:
        return decoder.decompress(data, max_length=_MAX_TEXT_BYTES)
    except zlib.error:
        return None


def _put_text(tags: dict[str, Any], key: str, value: str) -> None:
    key = key.strip()
    value = value.strip()
    if not key or not value or key in _SKIP_PNG_TEXT_KEYS:
        return
    if len(value) > _MAX_TEXT_BYTES:
        value = value[:_MAX_TEXT_BYTES]
    tags[key] = value


def _parse_itxt(payload: bytes) -> tuple[str, str] | None:
    split = payload.find(b"\x00")
    if split <= 0 or split + 2 >= len(payload):
        return None
    rest = payload[split + 1 :]
    flag, method = rest[0], rest[1]
    rest = rest[2:]
    lang_end = rest.find(b"\x00")
    if lang_end < 0:
        return None
    translated_end = rest.find(b"\x00", lang_end + 1)
    if translated_end < 0:
        return None
    text_bytes = rest[translated_end + 1 :]
    if flag == 1:
        if method != 0:
            return None
        inflated = _inflate(text_bytes)
        if inflated is None:
            return None
        text_bytes = inflated
    elif flag != 0:
        return None
    return payload[:split].decode("latin-1"), text_bytes.decode("utf-8", errors="replace")


def _png_text_tags(image_bytes: bytes) -> dict[str, Any]:
    tags: dict[str, Any] = {}
    i = 8
    length = len(image_bytes)
    while i + 12 <= length:
        chunk_len = int.from_bytes(image_bytes[i : i + 4], "big")
        if chunk_len < 0 or i + 12 + chunk_len > length:
            break
        chunk_type = image_bytes[i + 4 : i + 8]
        payload = image_bytes[i + 8 : i + 8 + chunk_len]
        if chunk_type == b"IEND":
            break
        if chunk_type == b"tIME" and chunk_len == 7:
            year = int.from_bytes(payload[0:2], "big")
            month, day, hour, minute, second = payload[2:7]
            if 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59 and second <= 60:
                tags["tIME"] = (
                    f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
                )
        elif chunk_type == b"tEXt":
            split = payload.find(b"\x00")
            if split > 0:
                _put_text(
                    tags,
                    payload[:split].decode("latin-1"),
                    payload[split + 1 :].decode("latin-1"),
                )
        elif chunk_type == b"zTXt":
            split = payload.find(b"\x00")
            if split > 0 and split + 2 <= len(payload) and payload[split + 1] == 0:
                inflated = _inflate(payload[split + 2 :])
                if inflated is not None:
                    _put_text(
                        tags,
                        payload[:split].decode("latin-1"),
                        inflated.decode("latin-1"),
                    )
        elif chunk_type == b"iTXt":
            parsed = _parse_itxt(payload)
            if parsed:
                _put_text(tags, parsed[0], parsed[1])
        i += 12 + chunk_len
    return tags


def _jpeg_comment(image_bytes: bytes) -> str | None:
    comments: list[str] = []
    i = 2
    length = len(image_bytes)
    while i < length - 4:
        if image_bytes[i] != 0xFF:
            break
        marker = image_bytes[i + 1]
        if marker == 0xDA:
            break
        if marker in {0xD8, 0xD9}:
            i += 2
            continue
        segment_length = int.from_bytes(image_bytes[i + 2 : i + 4], "big")
        if segment_length < 2:
            break
        if marker == 0xFE:
            payload = image_bytes[i + 4 : i + 2 + segment_length]
            text = payload.decode("utf-8", errors="replace").strip("\x00").strip()
            if text:
                comments.append(text)
        i += 2 + segment_length
    if not comments:
        return None
    if len(comments) == 1:
        return comments[0]
    return "\n".join(comments)


def extract_image_metadata(image_bytes: bytes) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    image_format = format_of(image_bytes)
    if not image_format:
        return metadata

    metadata["format"] = image_format
    size = None
    if image_format == "png":
        size = _png_size(image_bytes)
        metadata.update(_png_text_tags(image_bytes))
    elif image_format == "gif":
        size = _gif_size(image_bytes)
    elif image_format == "jpeg":
        size = _jpeg_size(image_bytes)
        comment = _jpeg_comment(image_bytes)
        if comment:
            metadata["Comment"] = comment
    if size:
        metadata["width"] = size[0]
        metadata["height"] = size[1]
    return metadata
