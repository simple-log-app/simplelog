"""Tests for changelog.py and the bundled CHANGELOG files."""
import pytest

import changelog
from version import __version__

_TEXT = """# Changelog

## [Unreleased]
- next

## [1.1.0] - 2026-01-02
- b

## [1.0.0] - 2026-01-01
- a
"""


def test_sections_marks_unreleased_with_empty_version():
    assert [v for v, _ in changelog.sections(_TEXT)] == ["", "1.1.0", "1.0.0"]


def test_notes_between_excludes_current_and_unreleased():
    notes = changelog.notes_between(_TEXT, "1.0.0", "v1.1.0")
    assert notes == "## [1.1.0] - 2026-01-02\n- b"


def test_section_for_accepts_tag_prefix():
    assert changelog.section_for(_TEXT, "v1.0.0") == "## [1.0.0] - 2026-01-01\n- a"
    assert changelog.section_for(_TEXT, "v9.9.9") == ""


def test_filename_and_raw_url():
    assert changelog.filename("en") == "CHANGELOG.md"
    assert changelog.raw_url("v1.0.8", "fr").endswith("/v1.0.8/CHANGELOG.fr.md")


def test_local_text_falls_back_to_english(tmp_path, monkeypatch):
    (tmp_path / "CHANGELOG.md").write_text("english", encoding="utf-8")
    monkeypatch.setattr(changelog, "_BASE", tmp_path)
    assert changelog.local_text("zh") == "english"
    (tmp_path / "CHANGELOG.md").unlink()
    assert changelog.local_text("zh") == ""


def _versions(locale: str) -> list[str]:
    return [v for v, _ in changelog.sections(changelog.local_text(locale))]


@pytest.mark.parametrize("locale", changelog.LOCALES)
def test_every_locale_has_its_own_changelog_file(locale):
    assert (changelog._BASE / changelog.filename(locale)).exists()


@pytest.mark.parametrize("locale", changelog.LOCALES)
def test_every_locale_lists_the_same_versions(locale):
    assert _versions(locale) == _versions("en")


def test_current_version_is_documented():
    assert __version__ in _versions("en")
