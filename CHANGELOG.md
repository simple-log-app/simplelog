# Changelog

All notable changes to SimpleLog are documented in this file.

## [Unreleased]

### Added
- Changelog, available in 5 languages and in the app (Help → What's New).
- When a new version is available, the update dialog now lists what changed since your version.

### Changed
- SSH: the server's key fingerprint is now shown for confirmation the first time you connect to a host, and a changed key is refused.
- Saved credentials and profiles are now readable only by your user account.

## [1.0.8] - 2026-09-30

### Added
- Reopening a saved connection now reconnects automatically and restores the selected target (log group, project, service, pod, worker…) and options, for every provider. You only need to click Open.

### Fixed
- AWS CloudWatch: saved credentials are now prefilled when reopening a connection.

## [1.0.7] - 2026-08-19

### Fixed
- macOS: release builds work again (they had been failing since 1.0.4).
- Links and update checks now point to the new simple-log-app GitHub organization.

## [1.0.6] - 2026-07-29

### Fixed
- The mouse wheel no longer changes drop-down values by accident while scrolling.

## [1.0.5] - 2026-07-29

### Added
- Right-click menu to copy the selected log lines.

## [1.0.4] - 2026-07-29

### Fixed
- Several log lines can now be selected at once in the log viewer.

## [1.0.3] - 2026-05-25

### Fixed
- macOS: fixed a crash on launch.

## [1.0.2] - 2026-05-25

### Fixed
- macOS: fixed a crash on launch.

## [1.0.1] - 2026-05-21

### Changed
- Internal cleanup and better test coverage.

## [1.0.0] - 2026-05-20

### Added
- First release: log viewer for local files, piped stdin, AWS CloudWatch, SSH, Docker, Kubernetes, Vercel, Google Cloud, Azure, Loki, Datadog, Elasticsearch, Railway, Fly.io and Cloudflare Workers.
