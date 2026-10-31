import pytest

from app.services.normalize import (
    NormalizationError,
    normalize_account,
    normalize_auto,
    normalize_phone,
    normalize_url,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0123 456 789", "0123456789"),
        ("1234-5678-9012", "123456789012"),
        ("12.345.678", "12345678"),
    ],
)
def test_account_strips_separators(raw, expected):
    assert normalize_account(raw) == expected


@pytest.mark.parametrize("raw", ["12345", "abcdef12", "", "1" * 20])
def test_account_rejects_invalid(raw):
    with pytest.raises(NormalizationError):
        normalize_account(raw)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0901234567", "0901234567"),
        ("+84 901 234 567", "0901234567"),
        ("84901234567", "0901234567"),
        ("(090) 123-4567", "0901234567"),
    ],
)
def test_phone_normalizes_to_national_format(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["123", "0001234567", "+1 555 123 4567"])
def test_phone_rejects_invalid(raw):
    with pytest.raises(NormalizationError):
        normalize_phone(raw)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://www.Example-Scam.com/path?x=1#frag", "example-scam.com"),
        ("http://sub.phishing.vn:8080/login", "sub.phishing.vn"),
        ("example.com", "example.com"),
        ("WWW.SHOP.VN", "shop.vn"),
    ],
)
def test_url_reduces_to_registrable_host(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw", ["localhost", "not a url", "https://", "-.bad"])
def test_url_rejects_invalid(raw):
    with pytest.raises(NormalizationError):
        normalize_url(raw)


def test_auto_detects_type():
    assert normalize_auto("https://bank-fake.xyz/a").type == "url"
    assert normalize_auto("+84 901 234 567").type == "phone"
    assert normalize_auto("0901234567").type == "phone"
    assert normalize_auto("1234567890").type == "account"


def test_auto_rejects_empty():
    with pytest.raises(NormalizationError):
        normalize_auto("   ")
