# SimpleLog

A fast log viewer for **local files**, **piped stdin** and **20 remote sources** (cloud, containers, servers, observability tools) — built with PyQt6. Available in English, French, German, Spanish and Chinese.

---

## Features

- **Many log sources** — local files, piped stdin, and remote providers: AWS CloudWatch, Google Cloud, Azure Monitor, SSH, Docker, Kubernetes, systemd journal, Vercel, Heroku, Render, Railway, Fly.io, Cloudflare, Grafana Loki, Datadog, Elasticsearch, Splunk, Better Stack, Sentry
- **Saved connections** — remote connections are saved and reopened in one click, restoring the selected target and options; remote tabs show their connection state and reconnect by themselves when the stream drops
- **Tabs + split panes** — open logs side-by-side (vertical) or stacked (horizontal) inside the active tab
- **Merged view** — show several open logs together in one tab, in time order, each line tagged with its source
- **Live tailing** — files and remote streams are followed continuously; configurable tail for large files (default: 100 lines)
- **Search** — incremental search with hit count, `F3` / `Shift+F3` navigation, match case and regular expression options, recent terms suggested
- **Filter** — live filter with AND / OR logic, level chips (ERROR, WARN, INFO, DEBUG, TRACE) and `key=value` filters on JSON logs
- **Highlight rules** — colour the words you care about in every log (Edit menu)
- **Bookmarks** — mark lines (`Ctrl+B`) and jump between them (`F2` / `Shift+F2`)
- **Export** — save the displayed (filtered) or selected lines to a file (`Ctrl+Shift+E`)
- **Syntax highlighting** — colour-coded levels, timestamps and JSON, with collapsible JSON rows
- **Day / Night / Auto theme** — follows your system or set manually (`Ctrl+Shift+L`)
- **Languages** — EN / FR / DE / ES / ZH via the Language menu, persisted across restarts
- **Changelog and updates** — Help → What's New, and an in-app update check

---

## Requirements

- Python 3.11+
- PyQt6 >= 6.6, < 6.11 (6.11+ has a macOS dylib symbol mismatch bug)
- Credentials for the remote sources you use (for example `~/.aws/credentials` for CloudWatch); they are entered when you add a connection

---

## Installation

### One-liner (all platforms)

Detects your OS and installs the right package automatically:

```bash
curl -sSL https://raw.githubusercontent.com/simple-log-app/simplelog/master/install.sh | bash
```

---

### macOS

**Via Homebrew (recommended):**

```bash
brew tap simple-log-app/tap
brew install --cask simplelog
```

**Via .dmg:**

Download [SimpleLog-macOS-universal.dmg](https://github.com/simple-log-app/simplelog/releases/latest/download/SimpleLog-macOS-universal.dmg) and drag the app to `/Applications`.

> If macOS blocks the app: right-click → **Open** → **Open**

Requires macOS 12 Monterey or later. Apple Silicon and Intel both supported.

---

### Debian / Ubuntu

**One-liner:**

```bash
curl -sSL https://raw.githubusercontent.com/simple-log-app/simplelog/master/install.sh | bash
```

**Manual .deb install:**

```bash
curl -LO https://github.com/simple-log-app/simplelog/releases/latest/download/simplelog_amd64.deb
sudo dpkg -i simplelog_amd64.deb
```

Requires Ubuntu 22.04+ or Debian 12+, x86-64.

---

### Other Linux (Fedora, Arch, openSUSE…)

**One-liner:**

```bash
curl -sSL https://raw.githubusercontent.com/simple-log-app/simplelog/master/install.sh | bash
```

**AppImage:**

```bash
curl -LO https://github.com/simple-log-app/simplelog/releases/latest/download/simplelog-x86_64.AppImage
chmod +x simplelog-x86_64.AppImage
./simplelog-x86_64.AppImage
```

---

### From source

```bash
git clone https://github.com/simple-log-app/simplelog.git
cd simplelog
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## Usage

### GUI mode

```bash
python main.py
```

### Open one or more log files

```bash
python main.py /var/log/syslog /var/log/auth.log
```

### Pipe stdin

```bash
journalctl -f | python main.py
kubectl logs -f my-pod | python main.py
```

---

## CLI Reference

```
simplelog [--split MODE] [--tail N] [FILE ...]
command | simplelog [--split MODE]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `FILE ...` | — | One or more log file paths. Glob patterns are not expanded — use your shell: `simplelog logs/*.log`. |
| `--split MODE` | `tab` | How to lay out files on startup. See values below. |
| `--tail N` | `100` | Lines to load from the **end** of each file. Prevents freezing on large files. |

### `--split` values

| Value | Layout | Description |
|---|---|---|
| `tab` | *(default)* | Each file opens as a new tab. |
| `vertical` | `│` divider | Files open as panes split side-by-side inside the same tab. |
| `horizontal` | `─` divider | Files open as panes split top/bottom inside the same tab. |

> The split mode selected via `--split` is also reflected in the sidebar radio buttons inside the app.

### Examples

```bash
# Launch the app (no arguments)
simplelog

# Tail a single file
simplelog /var/log/syslog

# Load the last 500 lines of a large file
simplelog --tail 500 /var/log/nginx/access.log

# Open multiple files as tabs
simplelog app.log worker.log scheduler.log

# Open two files side-by-side (vertical split)
simplelog --split vertical app.log error.log

# Open two files stacked (horizontal split)
simplelog --split horizontal service-a.log service-b.log

# Split + custom tail
simplelog --split vertical --tail 1000 app.log error.log

# Pipe any command's output
journalctl -f | simplelog
kubectl logs -f my-pod | simplelog
docker logs -f my-container | simplelog

# Pipe with filtering
tail -f /var/log/syslog | grep -i error | simplelog
```

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` | Open a file |
| `Ctrl+W` | Close the current tab |
| `Ctrl+Shift+W` | Close all open logs |
| `Ctrl+F` | Open / focus sidebar search |
| `F3` / `Shift+F3` | Next / previous match |
| `Ctrl+Shift+F` | Toggle the search sidebar |
| `Ctrl+\` | Toggle the sources sidebar |
| `Ctrl+B` | Toggle a bookmark on the line |
| `F2` / `Shift+F2` | Next / previous bookmark |
| `Ctrl+Shift+B` | Remove all bookmarks |
| `Ctrl+Shift+E` | Export lines to a file |
| `Ctrl+Shift+L` | Switch Day / Night theme |
| `Ctrl+C` | Copy the selected lines |
| `Ctrl+Q` | Quit |

---

## Split panes

Each tab can contain multiple panes arranged in a splitter. The "Open as" choice, shown when adding a connection, decides where a log opens:

- **New tab** — opens in a new tab (default)
- **Split ↔ side by side** — adds a pane to the right inside the current tab
- **Split ↕ top / bottom** — adds a pane below inside the current tab

The split choices are greyed out while no log is open. Closing the last pane in a tab closes the tab automatically. Panes can be resized by dragging the splitter handle, and closed individually with the ✕ button in their toolbar. For a combined, time-ordered view of several logs, use **Merged view** (Edit menu or right-click menu).

---

## Sidebar

The search sidebar (toggle: `Ctrl+Shift+F`) has three panels:

### Search
Incremental full-text search across visible log lines, with hit count and ▲ / ▼ (or `F3` / `Shift+F3`) navigation. Options: match case, regular expression.

### Filter
Live filter that hides non-matching lines. Multiple terms can be combined with **AND** or **OR** logic, and level chips show or hide ERROR, WARN, INFO, DEBUG and TRACE lines. Enable **Live** to also filter incoming lines as they arrive.

### JSON Keys
When log lines contain JSON, detected keys are listed automatically. Click a key to add it as a filter term.

The left sidebar (toggle: `Ctrl+\`) lists your saved remote connections.

---

## Remote sources

Click **Add** (or **+ New connection** under a provider) and pick a source in the filterable list. Fill in the connection form, choose the target (log group, project, service, pod, container…), set the options, then choose how to open it (tab or split) and click **Open**. Connections are saved under `~/.config/simplelog/` (readable only by your user); reopening one reconnects automatically and restores the selected target and options.

Supported sources: AWS CloudWatch, Google Cloud, Azure Monitor, SSH (with SFTP file browser), Docker, Kubernetes, systemd journal, Vercel, Heroku, Render, Railway, Fly.io, Cloudflare, Grafana Loki, Datadog, Elasticsearch, Splunk, Better Stack and Sentry. See [`docs/provider-testing-guide.md`](docs/provider-testing-guide.md) for how each one is tested.

---

## Project layout

```
simplelog/
├── main.py                 # Launcher (python main.py, PyInstaller entry point)
├── simplelog/              # The application package
│   ├── main.py             # CLI argument parsing, single-instance IPC, startup
│   ├── version.py          # Single source of truth for the app version
│   ├── core/               # No-UI logic: i18n, config and saved connections,
│   │                       #   log model, highlight rules, changelog, HTTP helpers
│   ├── sources/            # Log sources: provider registry, background workers,
│   │                       #   one API client per provider (docker_utils, loki_utils, ...)
│   └── ui/                 # PyQt6 interface: main window, log view, sidebar, theme,
│       └── panels/         #   dialogs; one connection form per provider in panels/
├── locales/                # Translations (en, fr, de, es, zh)
├── assets/providers/       # Provider logos
├── packaging/, build/      # Linux / macOS packaging and build scripts
├── html/                   # Project website
├── simplelog.spec          # PyInstaller spec
└── tests/
```

---

## Development

### Install dev dependencies

```bash
pip install -r requirements-dev.txt
```

### Run tests

```bash
pytest -v
```

### Run tests with coverage

```bash
pytest -v --cov=. --cov-report=term-missing
```

### Lint

```bash
ruff check .
```

---

## Uninstall

### macOS (.dmg)

```bash
rm -rf /Applications/SimpleLog.app
```

### Linux — Debian / Ubuntu (.deb)

```bash
sudo apt remove simplelog
# or, if installed directly with dpkg:
sudo dpkg -r simplelog
```

### Linux — AppImage

```bash
rm -f ~/.local/bin/simplelog
```

---

## License

MIT
