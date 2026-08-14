"""Tests for vsz_domains tools."""
from __future__ import annotations

import pytest

from tools.vsz_domains import _domain_list

pytestmark = pytest.mark.asyncio


class TestDomainList:
    async def test_returns_domains(self):
        result = await _domain_list()
        assert isinstance(result, list)
        assert len(result) == 1

    async def test_domain_fields(self):
        result = await _domain_list()
        domain = result[0]
        assert domain["id"] == "domain-001"
        assert domain["name"] == "Default Domain"
        assert "description" in domain
        assert "status" in domain
