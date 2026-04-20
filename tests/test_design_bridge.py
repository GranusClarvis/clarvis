"""Tests for clarvis.context.design_bridge."""

import pytest
from clarvis.context.design_bridge import (
    decide,
    generate_pack,
    get_profile,
    list_projects,
)


def test_list_projects():
    projects = list_projects()
    assert "swo" in projects
    assert "clarvis" in projects


def test_get_profile_builtin():
    profile = get_profile("swo")
    assert profile["name"] == "Star World Order"
    assert "#ffd700" in profile["palette"]["gold"]


def test_get_profile_missing():
    assert get_profile("nonexistent") == {}


class TestDecide:
    def test_design_task(self):
        result = decide("explore layout options for the homepage redesign")
        assert result["recommendation"] == "claude_design"
        assert result["scores"]["design"] > result["scores"]["code"]

    def test_code_task(self):
        result = decide("fix the button alignment bug in the navbar")
        assert result["recommendation"] == "code_first"
        assert result["scores"]["code"] > result["scores"]["design"]

    def test_pixel_art_task(self):
        result = decide("create pixel art sprites for the frog character")
        assert result["recommendation"] == "pixel_art_tool"

    def test_ambiguous_defaults_to_design(self):
        result = decide("make the profile page look better")
        assert result["recommendation"] == "claude_design"


class TestGeneratePack:
    def test_swo_pack(self):
        pack = generate_pack("swo", "redesign sanctuary staking page")
        assert "Star World Order" in pack
        assert "#ffd700" in pack
        assert "Press Start 2P" in pack
        assert "redesign sanctuary staking page" in pack
        assert "handoff bundle" in pack.lower()

    def test_clarvis_pack(self):
        pack = generate_pack("clarvis", "new brain health dashboard")
        assert "Clarvis Dashboard" in pack
        assert "PixiJS" in pack
        assert "#58a6ff" in pack

    def test_missing_project(self):
        pack = generate_pack("nonexistent", "some task")
        assert "ERROR" in pack

    def test_pack_has_instructions(self):
        pack = generate_pack("swo", "test task")
        assert "Instructions for This Session" in pack
        assert "2-3 visual directions" in pack
