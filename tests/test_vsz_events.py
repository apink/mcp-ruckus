"""Tests for vsz_events tools."""
from __future__ import annotations

import pytest
from tools.vsz_events import _alert_events

pytestmark = pytest.mark.asyncio


class TestAlertEvents:
    async def test_returns_all_events(self):
        result = await _alert_events()
        assert isinstance(result, dict)
        assert result["totalCount"] == 4
        assert len(result["events"]) == 4

    async def test_severity_filter(self):
        result = await _alert_events(severity="Critical")
        assert result["totalCount"] == 1
        assert result["events"][0]["severity"] == "Critical"

    async def test_category_filter(self):
        result = await _alert_events(category="Client")
        assert result["totalCount"] == 2

    async def test_text_search(self):
        result = await _alert_events(text_search="roamed")
        assert result["totalCount"] >= 1

    async def test_pagination(self):
        result = await _alert_events(limit=1, page=1)
        assert result["page"] == 1
        assert result["limit"] == 1
        assert isinstance(result["hasMore"], bool)

    async def test_combined_filters(self):
        result = await _alert_events(severity="Informational", category="Client", limit=10)
        assert result["totalCount"] >= 1

    async def test_event_fields(self):
        result = await _alert_events()
        event = result["events"][0]
        assert "id" in event
        assert "severity" in event
        assert "category" in event
        assert "event_type" in event
