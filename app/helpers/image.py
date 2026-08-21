MAX_IMAGE_BYTES = 10 * 1024 * 1024

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_GIF87A = b"GIF87a"
_GIF89A = b"GIF89a"

IMAGE_SIGNATURES = (_JPEG, _PNG, _GIF87A, _GIF89A)


def format_of(image_bytes: bytes) -> str | None:
    if image_bytes.startswith(_JPEG):
        return "jpeg"
    if image_bytes.startswith(_PNG):
        return "png"
    if image_bytes.startswith(_GIF87A) or image_bytes.startswith(_GIF89A):
        return "gif"
    return None


def is_supported_image(image_bytes: bytes) -> bool:
    return format_of(image_bytes) is not None
