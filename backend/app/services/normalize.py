"""Chuẩn hóa giá trị tra cứu: số tài khoản, số điện thoại, URL (FR-01).

Các hàm thuần (pure), không phụ thuộc DB, để kiểm thử đơn vị đầy đủ.
"""

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

AlertType = Literal["account", "phone", "url"]

# Số di động/cố định Việt Nam sau khi đưa về dạng 0xxxxxxxxx (10 chữ số, đầu 0).
_VN_PHONE = re.compile(r"^0[1-9]\d{8}$")
_ACCOUNT_DIGITS = re.compile(r"^\d{6,19}$")
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOST = re.compile(rf"^(?=.{{1,253}}$)({_LABEL}\.)+[a-z]{{2,63}}$")


class NormalizationError(ValueError):
    """Giá trị đầu vào không thuộc dạng STK, SĐT hay URL hợp lệ."""


@dataclass(frozen=True)
class Normalized:
    type: AlertType
    value_norm: str


def normalize_account(raw: str) -> str:
    digits = re.sub(r"[\s\-.]", "", raw)
    if not _ACCOUNT_DIGITS.match(digits):
        raise NormalizationError("Số tài khoản phải gồm 6–19 chữ số")
    return digits


def normalize_phone(raw: str) -> str:
    compact = re.sub(r"[\s\-.()]", "", raw)
    if compact.startswith("+84"):
        compact = "0" + compact[3:]
    elif compact.startswith("84") and len(compact) == 11:
        compact = "0" + compact[2:]
    if not _VN_PHONE.match(compact):
        raise NormalizationError("Số điện thoại không đúng định dạng Việt Nam")
    return compact


def normalize_url(raw: str) -> str:
    candidate = raw.strip()
    if "://" not in candidate:
        candidate = "http://" + candidate
    parts = urlsplit(candidate.lower())
    host = parts.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    if not _HOST.match(host):
        raise NormalizationError("Đường dẫn không có tên miền hợp lệ")
    # Chỉ giữ tên miền gốc: bỏ scheme, path, query, fragment, port (theo thiết kế Agent 2).
    return host


def normalize_auto(raw: str) -> Normalized:
    """Tự nhận dạng loại giá trị. Ưu tiên: URL (có dấu chấm + chữ/://), SĐT, STK."""
    value = raw.strip()
    if not value:
        raise NormalizationError("Vui lòng nhập giá trị cần tra cứu")
    if "://" in value or ("." in value and re.search(r"[a-zA-Z]", value)):
        return Normalized("url", normalize_url(value))
    compact = re.sub(r"[\s\-.()]", "", value)
    if compact.startswith("+84") or _VN_PHONE.match(compact):
        return Normalized("phone", normalize_phone(value))
    return Normalized("account", normalize_account(value))
