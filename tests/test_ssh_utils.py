"""Unit tests for ssh_utils.py - paramiko is mocked."""
from unittest.mock import MagicMock, patch

import paramiko
import pytest

import ssh_utils

# -- make_client ---------------------------------------------------------------

def _patch_sshclient():
    instance = MagicMock()
    cls_patch = patch("ssh_utils.paramiko.SSHClient", return_value=instance)
    return cls_patch, instance


def test_make_client_success_with_key():
    cls_patch, instance = _patch_sshclient()
    with cls_patch:
        result = ssh_utils.make_client("host", "user", port=2222, key_path="/k.pem")
    assert result is instance
    instance.load_system_host_keys.assert_called_once()
    instance.set_missing_host_key_policy.assert_called_once()
    kwargs = instance.connect.call_args.kwargs
    assert kwargs["hostname"] == "host"
    assert kwargs["port"] == 2222
    assert kwargs["username"] == "user"
    assert kwargs["key_filename"] == "/k.pem"
    assert kwargs["password"] is None


def test_make_client_success_with_password():
    cls_patch, instance = _patch_sshclient()
    with cls_patch:
        ssh_utils.make_client("h", "u", password="pw")
    assert instance.connect.call_args.kwargs["password"] == "pw"
    assert instance.connect.call_args.kwargs["key_filename"] is None


def test_make_client_defaults():
    cls_patch, instance = _patch_sshclient()
    with cls_patch:
        ssh_utils.make_client("h", "u")
    kwargs = instance.connect.call_args.kwargs
    assert kwargs["port"] == 22
    assert kwargs["timeout"] == 10.0
    assert kwargs["look_for_keys"] is True
    assert kwargs["allow_agent"] is True


def test_make_client_auth_failure():
    cls_patch, instance = _patch_sshclient()
    instance.connect.side_effect = paramiko.AuthenticationException("bad")
    with cls_patch, pytest.raises(RuntimeError, match="Authentication failed"):
        ssh_utils.make_client("h", "u")


def test_make_client_ssh_error():
    cls_patch, instance = _patch_sshclient()
    instance.connect.side_effect = paramiko.SSHException("proto")
    with cls_patch, pytest.raises(RuntimeError, match="SSH error"):
        ssh_utils.make_client("h", "u")


def test_make_client_os_error():
    cls_patch, instance = _patch_sshclient()
    instance.connect.side_effect = OSError("no route")
    with cls_patch, pytest.raises(RuntimeError, match="Connection failed"):
        ssh_utils.make_client("h", "u")


# -- list_remote_dir -----------------------------------------------------------

def _make_attrs(names_with_mode):
    out = []
    for name, mode in names_with_mode:
        a = MagicMock()
        a.filename = name
        a.st_mode = mode
        out.append(a)
    return out


def test_list_remote_dir_sorts_filenames():
    client = MagicMock()
    sftp = client.open_sftp.return_value
    sftp.listdir_attr.return_value = _make_attrs([("b", 0), ("a", 0), ("c", 0)])
    assert ssh_utils.list_remote_dir(client, "/x") == ["a", "b", "c"]
    sftp.close.assert_called_once()


def test_list_remote_dir_closes_on_failure():
    client = MagicMock()
    sftp = client.open_sftp.return_value
    sftp.listdir_attr.side_effect = OSError("denied")
    with pytest.raises(RuntimeError, match="Cannot list /x"):
        ssh_utils.list_remote_dir(client, "/x")
    sftp.close.assert_called_once()


def test_list_remote_dir_raises_when_open_sftp_fails():
    client = MagicMock()
    client.open_sftp.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="Cannot list"):
        ssh_utils.list_remote_dir(client, "/x")


# -- list_remote_dir_full ------------------------------------------------------

def test_list_remote_dir_full_marks_dirs():
    import stat as _stat
    client = MagicMock()
    sftp = client.open_sftp.return_value
    sftp.listdir_attr.return_value = _make_attrs([
        ("file.txt", _stat.S_IFREG | 0o644),
        ("subdir", _stat.S_IFDIR | 0o755),
        ("zlast", 0),
    ])
    result = ssh_utils.list_remote_dir_full(client, "/p")
    assert result == [("file.txt", False), ("subdir", True), ("zlast", False)]


def test_list_remote_dir_full_handles_error():
    client = MagicMock()
    sftp = client.open_sftp.return_value
    sftp.listdir_attr.side_effect = OSError("denied")
    with pytest.raises(RuntimeError, match="Cannot list /p"):
        ssh_utils.list_remote_dir_full(client, "/p")
    sftp.close.assert_called_once()


# -- test_file_readable --------------------------------------------------------

def _mk_client_cmd(stdout_bytes: bytes):
    client = MagicMock()
    stdout = MagicMock()
    stdout.read.return_value = stdout_bytes
    client.exec_command.return_value = (MagicMock(), stdout, MagicMock())
    return client


def test_test_file_readable_true():
    client = _mk_client_cmd(b"yes\n")
    assert ssh_utils.test_file_readable(client, "/etc/hosts") is True
    cmd = client.exec_command.call_args.args[0]
    assert "/etc/hosts" in cmd
    assert "test -f" in cmd


def test_test_file_readable_false():
    client = _mk_client_cmd(b"no\n")
    assert ssh_utils.test_file_readable(client, "/missing") is False


def test_test_file_readable_quotes_path():
    client = _mk_client_cmd(b"yes")
    ssh_utils.test_file_readable(client, "/tmp/has space.log")
    cmd = client.exec_command.call_args.args[0]
    assert "'/tmp/has space.log'" in cmd
