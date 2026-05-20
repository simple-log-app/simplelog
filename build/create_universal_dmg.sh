#!/usr/bin/env bash
# Create a universal macOS DMG (x86_64 + ARM64) from separate architectures
# Usage: ./build/create_universal_dmg.sh <version> <x86_64_dmg> <arm64_dmg>
set -euo pipefail

VERSION="${1:?Usage: $0 <version> <x86_64_dmg> <arm64_dmg>}"
X86_64_DMG="${2:?Missing x86_64 DMG path}"
ARM64_DMG="${3:?Missing ARM64 DMG path}"

log() { echo "▶ $*"; }
ok()  { echo "✓ $*"; }

# Verify inputs
[ -f "$X86_64_DMG" ] || { echo "✗ x86_64 DMG not found: $X86_64_DMG"; exit 1; }
[ -f "$ARM64_DMG" ] || { echo "✗ ARM64 DMG not found: $ARM64_DMG"; exit 1; }

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

log "Extracting x86_64 binary…"
hdiutil attach -readonly "$X86_64_DMG" -mountpoint "$TMPDIR/x86_64" -nobrowse
X86_64_BIN="$TMPDIR/x86_64/SimpleLog.app/Contents/MacOS/simplelog"
cp "$X86_64_BIN" "$TMPDIR/simplelog.x86_64"
hdiutil detach "$TMPDIR/x86_64"
ok "x86_64 binary extracted"

log "Extracting ARM64 binary…"
hdiutil attach -readonly "$ARM64_DMG" -mountpoint "$TMPDIR/arm64" -nobrowse
ARM64_BIN="$TMPDIR/arm64/SimpleLog.app/Contents/MacOS/simplelog"
cp "$ARM64_BIN" "$TMPDIR/simplelog.arm64"
hdiutil detach "$TMPDIR/arm64"
ok "ARM64 binary extracted"

log "Creating universal binary with lipo…"
lipo -create "$TMPDIR/simplelog.x86_64" "$TMPDIR/simplelog.arm64" \
    -output "$TMPDIR/simplelog.universal"
ok "Universal binary created"

log "Extracting base app structure…"
hdiutil attach -readonly "$ARM64_DMG" -mountpoint "$TMPDIR/base_app" -nobrowse
cp -r "$TMPDIR/base_app/SimpleLog.app" "$TMPDIR/SimpleLog.app"
hdiutil detach "$TMPDIR/base_app"

log "Replacing binary with universal version…"
cp "$TMPDIR/simplelog.universal" "$TMPDIR/SimpleLog.app/Contents/MacOS/simplelog"
ok "Binary replaced"

log "Verifying universal binary…"
file "$TMPDIR/SimpleLog.app/Contents/MacOS/simplelog"
lipo -info "$TMPDIR/SimpleLog.app/Contents/MacOS/simplelog"

log "Creating universal DMG…"
DMG_STAGING="$TMPDIR/dmg_staging"
mkdir -p "$DMG_STAGING"
cp -r "$TMPDIR/SimpleLog.app" "$DMG_STAGING/"
ln -sf /Applications "$DMG_STAGING/Applications"

DMG_NAME="dist/SimpleLog-macOS-universal.dmg"
hdiutil create \
    -volname "SimpleLog $VERSION" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$DMG_NAME"

ok "Universal DMG created: $DMG_NAME"
ls -lh "$DMG_NAME"
