"""ssh_utils.py — SSH connection helpers for SimpleLog."""
from __future__ import annotations

import base64
import hashlib
import shlex
import stat
from pathlib import Path

import paramiko

_KNOWN_HOSTS = Path.home() / ".config" / "simplelog" / "known_hosts"


class UnknownHostKeyError(RuntimeError):
    """Raised when the server's host key is not yet trusted."""

    def __init__(self, host: str, key_type: str, fingerprint: str) -> None:
        super().__init__(f"Unknown host key for {host}: {key_type} {fingerprint}")
        self.host = host
        self.key_type = key_type
        self.fingerprint = fingerprint


def _fingerprint(key) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


class _TrustPolicy(paramiko.MissingHostKeyPolicy):
    """Refuse unknown host keys, or remember them when *trust_new* is set."""

    def __init__(self, trust_new: bool) -> None:
        self._trust_new = trust_new

    def missing_host_key(self, client, hostname, key):
        if not self._trust_new:
            raise UnknownHostKeyError(hostname, key.get_name(), _fingerprint(key))
        client.get_host_keys().add(hostname, key.get_name(), key)
        line = paramiko.hostkeys.HostKeyEntry([hostname], key).to_line()
        _KNOWN_HOSTS.parent.mkdir(parents=True, exist_ok=True)
        with open(_KNOWN_HOSTS, "a", encoding="utf-8") as f:
            f.write(line)


def make_client(
    host: str,
    user: str,
    port: int = 22,
    key_path: str | None = None,
    password: str | None = None,
    timeout: float = 10.0,
    trust_new_host: bool = False,
) -> paramiko.SSHClient:
    """Open and return an authenticated SSHClient.

    Tries key_path first (if given), then SSH agent / ~/.ssh/id_*, then password.
    Unknown host keys raise UnknownHostKeyError unless *trust_new_host* is True,
    in which case the key is saved to SimpleLog's known_hosts file.
    Raises RuntimeError with a human-readable message on any failure.
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if _KNOWN_HOSTS.exists():
        client.load_host_keys(str(_KNOWN_HOSTS))
    client.set_missing_host_key_policy(_TrustPolicy(trust_new_host))
    try:
        client.connect(
            hostname=host,
            port=port,
            username=user,
            key_filename=key_path or None,
            password=password or None,
            timeout=timeout,
            look_for_keys=True,
            allow_agent=True,
        )
    except UnknownHostKeyError:
        client.close()
        raise
    except paramiko.BadHostKeyException as e:
        raise RuntimeError(f"Host key mismatch (possible attack): {e}") from e
    except paramiko.AuthenticationException as e:
        raise RuntimeError(f"Authentication failed: {e}") from e
    except paramiko.SSHException as e:
        raise RuntimeError(f"SSH error: {e}") from e
    except OSError as e:
        raise RuntimeError(f"Connection failed: {e}") from e
    return client


def list_remote_dir(client: paramiko.SSHClient, path: str) -> list[str]:
    """Return sorted filenames in *path* on the remote host via SFTP.

    Raises RuntimeError if the path cannot be listed.
    """
    try:
        sftp = client.open_sftp()
        try:
            attrs = sftp.listdir_attr(path)
        finally:
            sftp.close()
    except Exception as e:
        raise RuntimeError(f"Cannot list {path}: {e}") from e
    return sorted(a.filename for a in attrs)


def list_remote_dir_full(client: paramiko.SSHClient, path: str) -> list[tuple[str, bool]]:
    """Return list of (name, is_dir) sorted by name for *path* on the remote host.

    Raises RuntimeError if the path cannot be listed.
    """
    try:
        sftp = client.open_sftp()
        try:
            attrs = sftp.listdir_attr(path)
        finally:
            sftp.close()
    except Exception as e:
        raise RuntimeError(f"Cannot list {path}: {e}") from e
    result = []
    for a in sorted(attrs, key=lambda x: x.filename):
        is_dir = stat.S_ISDIR(a.st_mode) if a.st_mode else False
        result.append((a.filename, is_dir))
    return result


def test_file_readable(client: paramiko.SSHClient, path: str) -> bool:
    """Return True if *path* exists and is a regular file on the remote host."""
    _, stdout, _ = client.exec_command(f"test -f {shlex.quote(path)} && echo yes || echo no")
    return stdout.read().strip() == b"yes"
