"""Tests for vSZ UUID validation helper."""
from __future__ import annotations

import pytest

from adapters.vsz import _validate_uuid


class TestUuidValidation:
    def test_accepts_valid_uuid(self):
        assert _validate_uuid("f214c803-c88f-40f8-83d5-a6e37a9840de") == \
            "f214c803-c88f-40f8-83d5-a6e37a9840de"

    def test_rejects_injection(self):
        with pytest.raises(ValueError):
            _validate_uuid("f214c803'; rm -rf /")

    def test_rejects_plain_text(self):
        with pytest.raises(ValueError):
            _validate_uuid("not-a-uuid")
