"""Tool registry discovery tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestToolRegistry:
    def test_discover_registers_core_tools(self):
        from Core_structure.tool_manifest import discover_tools, get_all_tools
        from vivie_core.engines import intent_engine, planner, tool_router
        from vivie_core.registry import bootstrap

        discover_tools()
        bootstrap(intent_engine, planner)

        names = set(tool_router.list_tools())
        assert "create_file" in names
        assert "get_weather" in names
        assert "calculate" in names or "check_internet_speed" in names

        manifests = get_all_tools()
        assert len(manifests) >= 6

    def test_create_file_uses_requested_name(self, monkeypatch, tmp_path):
        from Features.create_file import create_file

        monkeypatch.chdir(tmp_path)

        created = create_file("named project_notes text file")

        assert created == "project_notes.txt"
        assert (tmp_path / "project_notes.txt").exists()
        assert not (tmp_path / "demo.txt").exists()
