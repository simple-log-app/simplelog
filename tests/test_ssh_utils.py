"""Unit tests for ssh_utils.py - paramiko is mocked."""
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from simplelog.sources import ssh_utils

# -- make_client ---------------------------------------------------------------

def _patch_sshclient():
    instance = MagicMock()
    cls_patch = patch("simplelog.sources.ssh_utils.paramiko.SSHClient", return_value=instance)
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


def _make_attrs(names_with_mode):
    out = []
    for name, mode in names_with_mode:
        a = MagicMock()
        a.filename = name
        a.st_mode = mode
        out.append(a)
    return out


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


# -- host key verification -----------------------------------------------------

def test_unknown_host_key_is_refused_by_default():
    policy = ssh_utils._TrustPolicy(trust_new=False)
    key = MagicMock()
    key.get_name.return_value = "ssh-ed25519"
    key.asbytes.return_value = b"keybytes"
    with pytest.raises(ssh_utils.UnknownHostKeyError) as exc:
        policy.missing_host_key(MagicMock(), "h", key)
    assert exc.value.host == "h"
    assert exc.value.fingerprint.startswith("SHA256:")


def test_trusted_host_key_is_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(ssh_utils, "_KNOWN_HOSTS", tmp_path / "known_hosts")
    key = paramiko.RSAKey.generate(1024)
    ssh_utils._TrustPolicy(trust_new=True).missing_host_key(MagicMock(), "h", key)
    assert (tmp_path / "known_hosts").read_text().startswith("h ssh-rsa ")


def test_make_client_reraises_unknown_host():
    cls_patch, instance = _patch_sshclient()
    instance.connect.side_effect = ssh_utils.UnknownHostKeyError("h", "ssh-rsa", "SHA256:x")
    with cls_patch, pytest.raises(ssh_utils.UnknownHostKeyError):
        ssh_utils.make_client("h", "u")


def test_make_client_host_key_mismatch():
    cls_patch, instance = _patch_sshclient()
    instance.connect.side_effect = paramiko.BadHostKeyException("h", MagicMock(), MagicMock())
    with cls_patch, pytest.raises(RuntimeError, match="mismatch"):
        ssh_utils.make_client("h", "u")
