#!/usr/bin/env bash
# Publish universal macOS DMG to GitHub Releases and update Homebrew tap
# Usage: ./build/publish_universal_dmg.sh <version> <universal_dmg_path>
set -euo pipefail

VERSION="${1:?Usage: $0 <version> <universal_dmg_path>  e.g. $0 1.4.3 dist/SimpleLog-macOS-universal.dmg}"
DMG_PATH="${2:?Missing DMG path}"
OWNER="simple-log-app"
REPO="simplelog"
TAP_REPO="homebrew-tap"

log() { echo "▶ $*"; }
ok()  { echo "✓ $*"; }

[ -f "$DMG_PATH" ] || { echo "✗ DMG not found: $DMG_PATH"; exit 1; }

log "Computing sha256…"
if command -v sha256sum &>/dev/null; then
    SHA256=$(sha256sum "$DMG_PATH" | awk '{print $1}')
else
    SHA256=$(shasum -a 256 "$DMG_PATH" | awk '{print $1}')
fi
ok "sha256: ${SHA256}"

log "Cloning Homebrew tap…"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

git clone --quiet "https://github.com/${OWNER}/${TAP_REPO}.git" "$TMPDIR" || {
    echo "✗ Failed to clone tap repo"
    exit 1
}

CASK="$TMPDIR/Casks/simplelog.rb"

log "Updating cask with universal DMG info…"
sed -i.bak "s|version \".*\"|version \"${VERSION}\"|" "$CASK"
sed -i.bak "s|sha256 .*|sha256 \"${SHA256}\"|" "$CASK"
sed -i.bak "s|url .*|url \"https://github.com/${OWNER}/${REPO}/releases/download/v#{version}/SimpleLog-macOS-universal.dmg\"|" "$CASK"
rm -f "${CASK}.bak"

git -C "$TMPDIR" config user.name  "Universal Build"
git -C "$TMPDIR" config user.email "build@github.com"
git -C "$TMPDIR" add Casks/simplelog.rb
git -C "$TMPDIR" commit -m "chore: update SimpleLog cask to v${VERSION} (universal macOS)"

log "Pushing to tap repository…"
git -C "$TMPDIR" push origin master 2>&1 | grep -v "^remote:" || true

ok "Tap updated with universal DMG → v${VERSION}"
ok "URL: https://github.com/${OWNER}/${TAP_REPO}/blob/master/Casks/simplelog.rb"
