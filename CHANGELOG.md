# Changelog

All notable changes to SimpleLog are documented in this file.

## [Unreleased]

### Added
- The theme can now follow your system's light / dark setting: pick “Auto” from the arrow next to the Day / Night button.
- Filter by level: show or hide ERROR, WARN, INFO, DEBUG and TRACE lines with the chips in the Filter tab.
- Search and filter: new “match case” and “regular expression” options, and your recent terms are suggested as you type (press ↓ in an empty field to list them).
- Highlight rules (Edit menu): colour the words you care about in every log, with optional case matching and regular expressions.
- Bookmarks: mark lines with Ctrl+B (or the right-click menu) and jump between them with F2 / Shift+F2, or remove them all at once (Ctrl+Shift+B).
- Export: save the lines currently shown (after your filters) or just the selected ones to a file, from the File menu (Ctrl+Shift+E) or the right-click menu.
- Merged view (Edit menu or right-click menu): show several open logs together in one tab, in time order, each line tagged with its source.
- Remote tabs show their connection state (a coloured dot on the logo) and reconnect by themselves when the stream drops, without duplicating lines; this can be turned off in the File menu.
- New log sources: the local systemd journal, Heroku, Render, Splunk, Better Stack and Sentry (error events).

### Changed
- Add connection: the “Split” choices of “Open as” are greyed out while no log is open, since there is nothing to split yet.

## [2.0.0] - 2026-10-14

### Added
- Search: F3 jumps to the next match and Shift+F3 to the previous one; the shortcuts are shown in the buttons' tooltips.
- Day / Night mode: switch the theme from the button at the right of the menu bar (or with Ctrl+Shift+L); your choice is remembered.

### Changed
- New look: refreshed dark colour palette with a lime accent, for better readability.
- Remote sources: the list now only shows providers you have saved connections for, with a quick “+ New connection” link and a two-step delete.
- Adding a connection: a filterable 4-column picker showing each service's official logo, and a cleaner connection form.
- Provider logos now appear on tabs, and the “Open as” choice is a compact single row.

### Fixed
- The AND / OR toggle between search and filter terms is now shown in your language.

## [1.0.9] - 2026-10-13

### Added
- Changelog, available in 5 languages and in the app (Help → What's New).
- When a new version is available, the update dialog now lists what changed since your version.
- New “Wrap” option in the log toolbar: turn it off to show each log on a single line (scroll sideways for long ones), which is faster on very large logs.

### Changed
- SSH: the server's key fingerprint is now shown for confirmation the first time you connect to a host, and a changed key is refused.
- Saved credentials and profiles are now readable only by your user account.
- Much faster with busy log streams (SSH, Docker, Kubernetes, stdin, files): lines are added in groups, and long logs stay smooth while following, resizing or switching tabs.
- Ctrl+W now closes the current tab; closing all logs is Ctrl+Shift+W.
- Timestamps in the log view are now shown in your local time instead of UTC.
- Faster startup, and opening a big file with a very large number of lines is now almost instant.
- The provider cards in “Add connection” now show a short description of each source when you hover them.
- Status messages, connection errors and tooltips that were always in English now follow the language you chose.
- Updates are now checked against the checksum published with the release, and a corrupted download is discarded.

### Fixed
- CloudWatch: a connection based on an AWS profile now uses the region set for that profile in `~/.aws/config`.
- The application no longer crashes when a connection fails right after you close its tab, or when your AWS configuration file has a duplicated profile.
- File → Open (Ctrl+O) no longer opens the file twice.
- Docker, Kubernetes, SSH and piped logs no longer stop silently on a line containing invalid characters.
- Loading a very large batch of lines (for example `cat big.log | simplelog`) no longer leaves ghost rows in the log view.
- Fly.io: an invalid token or an unknown app now shows an error instead of an endless empty log.
- Azure: the extra conditions of your query (for example on the severity) are now kept while following, and rows ingested late are no longer missed.
- Kubernetes: a pod that prints many warnings no longer blocks the log stream.
- Automatic update on Linux (AppImage) now works when the install path contains a quote.
- Updates are refused when the published checksums do not list the downloaded file.
- The “Error” title, “Prev/Next” and “+ key=val” buttons now follow the chosen language.
- Key=value filters are about twice as fast on JSON logs.
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
- The SFTP file browser, restored SSH / GCP / Azure sessions and the Kubernetes cluster list no longer freeze the app while waiting for the network.
- The source badge in the log toolbar showed an internal label such as “src_ssh”; it now shows the source name.
- Saved Google Cloud connections now show their project next to their name.
- Azure: live following now also works with queries written on a single line or with a row limit (`take`/`limit`) before the filter.
- CloudWatch: events that arrive a few seconds late are no longer missed while following.
- Railway: following a service no longer keeps every line in memory, and choosing several services in a row no longer opens extra connections.
- Azure: the initial load of a table or of a query that caps its rows now shows the most recent rows instead of the oldest ones.
- Railway: following a service only fetches new lines instead of downloading all its logs on every refresh.

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
