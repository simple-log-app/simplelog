"""Tests for the macOS in-place update helpers (the script deletes the path it is given)."""
import os
import shutil
import subprocess

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from main_window import macos_app_bundle, macos_update_script  # noqa: E402

EXE = "/Applications/SimpleLog.app/Contents/MacOS/simplelog"


def test_bundle_is_the_app_not_its_parent_folder():
    assert macos_app_bundle(EXE) == "/Applications/SimpleLog.app"


def test_bundle_works_for_apps_outside_applications():
    assert macos_app_bundle("/Users/me/Apps/SimpleLog.app/Contents/MacOS/simplelog") \
        == "/Users/me/Apps/SimpleLog.app"


@pytest.mark.parametrize("exe", [
    "/usr/bin/python3",
    "/Applications/simplelog",
    "/opt/simplelog/simplelog",
    "/home/me/dist/simplelog/simplelog",
    "/Applications/SimpleLog.app/Contents/Frameworks/simplelog",
])
def test_bundle_is_none_outside_an_app_bundle(exe):
    assert macos_app_bundle(exe) is None


def test_script_never_targets_the_parent_folder():
    script = macos_update_script(42, "/tmp/x.dmg", "/Applications/SimpleLog.app")
    assert "rm -rf /Applications\n" not in script
    assert "rm -rf '/Applications'" not in script
    assert "mv /Applications/SimpleLog.app /Applications/.SimpleLog.old.app" in script


def test_script_quotes_paths_with_spaces():
    script = macos_update_script(1, "/tmp/My Dir/x.dmg", "/Users/a b/SimpleLog.app")
    assert "'/tmp/My Dir/x.dmg'" in script
    assert "'/Users/a b/SimpleLog.app'" in script


def test_script_is_valid_shell():
    script = macos_update_script(1, "/tmp/x.dmg", "/Applications/SimpleLog.app")
    subprocess.run(["sh", "-n"], input=script.encode(), check=True)


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_failed_copy_keeps_the_old_app(tmp_path):
    """Simulate the swap with a fake `hdiutil` whose mounted volume has no app."""
    apps = tmp_path / "Apps"
    bundle = apps / "SimpleLog.app"
    (bundle / "Contents").mkdir(parents=True)
    (bundle / "Contents" / "marker").write_text("old")
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    (fakebin / "hdiutil").write_text("#!/bin/sh\nexit 0\n")      # attach/detach: no-ops
    (fakebin / "open").write_text("#!/bin/sh\nexit 0\n")
    for f in fakebin.iterdir():
        f.chmod(0o755)
    dmg = tmp_path / "x.dmg"
    dmg.write_text("")
    script = macos_update_script(2 ** 22 + 1, str(dmg), str(bundle))   # pid that doesn't exist
    path = tmp_path / "update.sh"
    path.write_text(script)
    subprocess.run(["sh", str(path)], env={**os.environ, "PATH": f"{fakebin}:{os.environ['PATH']}"},
                   check=False, timeout=30)
    assert (bundle / "Contents" / "marker").read_text() == "old"
    assert not (apps / ".SimpleLog.new.app").exists()
    assert not (apps / ".SimpleLog.old.app").exists()
