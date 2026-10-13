# Changelog

All notable changes to SimpleLog are documented in this file.

## [Unreleased]

### Added
- Changelog, available in 5 languages and in the app (Help → What's New).
- When a new version is available, the update dialog now lists what changed since your version.

### Changed
- SSH: the server's key fingerprint is now shown for confirmation the first time you connect to a host, and a changed key is refused.
- Saved credentials and profiles are now readable only by your user account.
- Much faster with busy log streams (SSH, Docker, Kubernetes, stdin, files): lines are added in groups, and long logs stay smooth while following, resizing or switching tabs.
- Ctrl+W now closes the current tab; closing all logs is Ctrl+Shift+W.
- Timestamps in the log view are now shown in your local time instead of UTC.

### Fixed
- macOS: the in-app update could delete the whole Applications folder instead of replacing only SimpleLog. It now replaces only the SimpleLog app, and keeps the old one if anything goes wrong. Because the update runs from the version you already have, 1.0.8 and earlier can no longer self-update on macOS: download the new version once from the website or with Homebrew.
- Kubernetes: logs now appear right away instead of only after 200 lines.
- Loki, GCP, Datadog and Fly.io: the same log lines no longer appear again and again while following a source.
- Loki, Datadog and Elasticsearch: the initial load now shows the most recent logs instead of the oldest ones of the period. GCP no longer skips entries during bursts.
- A short network problem no longer stops following a source and pops up an error: SimpleLog retries, and only reports an error after several failures in a row.
- Pressing Enter in a text field (search, filter, forms) no longer inserts a separator line in the current log.
- Opening a log in a split pane when the tab already has 9 panes now shows a message instead of silently starting a log that is never displayed.
- Opening many saved connections no longer makes the app slower over time: their dialogs, timers and SSH connections are released when closed.
- Local files: following a file now keeps working after it is rotated or emptied, lines written in two parts are no longer split, and accented characters are no longer garbled.
- Search: matches are highlighted in translucent yellow, at the right place on wrapped lines; AND / OR between search terms is respected; JSON rows with a match are highlighted; and the view no longer jumps back to the first result while following a log.
- Right-clicking or selecting with the mouse on a JSON line no longer expands or collapses it; only a plain click does.
- Opening a file with `simplelog file.log` from another folder while SimpleLog is running now opens it.
- Closing a tab or quitting no longer freezes the app for several seconds.
- Turning timestamps on or off now resizes wrapped lines correctly.
- Saved connections and credentials can no longer be lost if the app crashes while saving.
- Elasticsearch 8 and later: following logs works again (it relied on a sort that newer versions reject).
- Updates: an incomplete download is detected, and installing a .deb update no longer freezes the window.
- CloudWatch, Docker and SSH: listing log groups, streams and containers, and opening an SSH log, no longer freeze the app while waiting for the network.

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
