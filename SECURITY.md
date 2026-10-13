# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x (latest) | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in SimpleLog, please **do not open a public issue**.

Instead, report it privately by emailing:

**r.sik@hotmail.fr**

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

You can expect an acknowledgement within **72 hours** and a resolution or status update within **7 days**.

## Scope

SimpleLog is a desktop log viewer. The main attack surfaces to consider are:

- **Local file parsing** — maliciously crafted log files could trigger unexpected behavior in the parser or UI renderer
- **Saved connections** — when you save a connection, its credentials (API tokens, keys, passwords) are stored in clear text in `~/.config/simplelog/profiles_*.json`, readable only by your user account (0600). Do not save connections on shared machines
- **AWS credentials** — profiles are read from `~/.aws/credentials` or environment variables; access keys typed in the form are only stored if you save the connection
- **Workspace files** — saved connections in `~/.config/simplelog/` contain hostnames and the credentials described above

## Out of Scope

- Vulnerabilities in third-party dependencies (report those directly to the upstream project)
- Issues requiring physical access to the machine
