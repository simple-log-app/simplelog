"""Tests for main.py (CLI entry-point helpers).

Heavy GUI bits like main() / _setup_ipc_server live behind Qt — only the
pure helpers are unit-tested here.
"""
import os
import stat
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import main

# -- _parse_args ---------------------------------------------------------------

def test_parse_args_defaults():
    with patch.object(sys, "argv", ["simplelog"]):
        args = main._parse_args()
    assert args.split == "tab"
    assert args.tail == 100
    assert args.files == []


def test_parse_args_files_and_options():
    with patch.object(sys, "argv", ["simplelog", "--split", "vertical", "--tail", "200", "a.log", "b.log"]):
        args = main._parse_args()
    assert args.split == "vertical"
    assert args.tail == 200
    assert args.files == ["a.log", "b.log"]


def test_parse_args_invalid_split():
    with patch.object(sys, "argv", ["simplelog", "--split", "diagonal"]):
        with pytest.raises(SystemExit):
            main._parse_args()


def test_parse_args_unknown_flag_is_ignored():
    # parse_known_args is used, so unknown flags do not error.
    with patch.object(sys, "argv", ["simplelog", "--unknown", "x", "f.log"]):
        args = main._parse_args()
    assert "f.log" in args.files


# -- _stdin_is_piped -----------------------------------------------------------

def test_stdin_is_piped_true_for_fifo():
    fake_stat = MagicMock()
    fake_stat.st_mode = stat.S_IFIFO | 0o600
    with patch("main.os.fstat", return_value=fake_stat), \
         patch("main.sys.stdin", MagicMock(fileno=lambda: 0)):
        assert main._stdin_is_piped() is True


def test_stdin_is_piped_false_for_tty():
    fake_stat = MagicMock()
    fake_stat.st_mode = stat.S_IFCHR | 0o600  # character device (tty)
    with patch("main.os.fstat", return_value=fake_stat), \
         patch("main.sys.stdin", MagicMock(fileno=lambda: 0)):
        assert main._stdin_is_piped() is False


def test_stdin_is_piped_swallows_exceptions():
    with patch("main.sys.stdin", MagicMock(fileno=MagicMock(side_effect=OSError("no fd")))):
        assert main._stdin_is_piped() is False


# -- _try_forward_to_existing --------------------------------------------------

def test_try_forward_returns_false_when_stdin_is_piped():
    fake_args = MagicMock(files=["a.log"], split="tab", tail=100)
    with patch("main._stdin_is_piped", return_value=True):
        assert main._try_forward_to_existing(fake_args) is False


def test_try_forward_returns_false_when_no_server():
    fake_args = MagicMock(files=["a.log"], split="tab", tail=100)
    fake_sock = MagicMock()
    fake_sock.waitForConnected.return_value = False
    with patch("main._stdin_is_piped", return_value=False), \
         patch("main.QLocalSocket", return_value=fake_sock):
        assert main._try_forward_to_existing(fake_args) is False


def test_try_forward_writes_payload_when_connected():
    fake_args = MagicMock(files=["x.log"], split="vertical", tail=50)
    fake_sock = MagicMock()
    fake_sock.waitForConnected.return_value = True
    with patch("main._stdin_is_piped", return_value=False), \
         patch("main.QLocalSocket", return_value=fake_sock):
        result = main._try_forward_to_existing(fake_args)
    assert result is True
    fake_sock.write.assert_called_once()
    raw_payload = fake_sock.write.call_args.args[0]
    import json
    data = json.loads(raw_payload.rstrip(b"\n"))
    assert data == {"files": ["x.log"], "split": "vertical", "tail": 50}
    fake_sock.disconnectFromServer.assert_called_once()


# -- module-level: socket name ------------------------------------------------

def test_socket_name_uses_dev_when_env_set(monkeypatch):
    # The value is computed at import time so we just check the actual value
    # matches whatever env state was in effect.
    if os.environ.get("SIMPLELOG_DEV"):
        assert main._SOCKET_NAME == "simplelog-ipc-dev"
    else:
        assert main._SOCKET_NAME == "simplelog-ipc-v1"
