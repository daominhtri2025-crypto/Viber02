"""Kiểm tra ảnh đính kèm bằng chữ ký tệp (magic bytes), không tin vào phần mở rộng hay Content-Type."""


class UploadInvalid(Exception):
    pass


def detect_image(data: bytes) -> tuple[str, str]:
    """Trả về (mime, ext) nếu là JPEG hoặc PNG thật; ngược lại ném UploadInvalid."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    raise UploadInvalid("Chỉ chấp nhận ảnh JPG hoặc PNG hợp lệ")
