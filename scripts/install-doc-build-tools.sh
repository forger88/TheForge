#!/usr/bin/env bash
set -euo pipefail

# The pinned pandoc is a Debian package and both archives are amd64, so fail fast elsewhere.
[[ "$(uname -m)" == "x86_64" ]] && command -v dpkg-deb >/dev/null || {
  echo "This installer needs Linux x86_64 with dpkg-deb; install the pinned pandoc and d2 by hand." >&2
  exit 1
}

PANDOC_VERSION="3.11"
PANDOC_ARCHIVE="pandoc-${PANDOC_VERSION}-1-amd64.deb"
PANDOC_SHA256="89d4c9d97818c62a97157f0072844e4602c6cee795bf84abd1aee7273abcda99"
D2_VERSION="v0.9.0"
D2_ARCHIVE="d2-${D2_VERSION}-linux-amd64.tar.gz"
D2_SHA256="5669ddc46b99e942cc96078f4a4e36d5e62103348f4c05179ede27802fdd87a9"

manifest_versions="$({ python3 - <<'PY'
import json
from pathlib import Path

toolchain = json.loads(Path("docs/tools/document-build.json").read_text(encoding="utf-8"))["toolchain"]
print(toolchain["pandoc"]["version"])
print(toolchain["d2"]["version"])
PY
})" || {
  echo "Could not read toolchain versions from docs/tools/document-build.json; run from the repository root with python3." >&2
  exit 1
}
manifest_pandoc_version="$(printf '%s\n' "$manifest_versions" | sed -n '1p')"
manifest_d2_version="v$(printf '%s\n' "$manifest_versions" | sed -n '2p')"
if [[ "$PANDOC_VERSION" != "$manifest_pandoc_version" || "$D2_VERSION" != "$manifest_d2_version" ]]; then
  echo "Installer pandoc/d2 versions do not match docs/tools/document-build.json; update the versions and checksums together." >&2
  exit 1
fi

install_dir="${DOC_TOOLS_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$install_dir"

# A tool already at the pinned version in install_dir is skipped.
pandoc_is_current() {
  [[ -x "$install_dir/pandoc" ]] || return 1
  case "$("$install_dir/pandoc" --version)" in
    "pandoc ${PANDOC_VERSION}"$'\n'*|"pandoc ${PANDOC_VERSION}") return 0 ;;
    *) return 1 ;;
  esac
}
d2_is_current() {
  [[ -x "$install_dir/d2" ]] || return 1
  case "$("$install_dir/d2" version)" in
    *"${D2_VERSION}"*) return 0 ;;
    *) return 1 ;;
  esac
}

if ! pandoc_is_current || ! d2_is_current; then
  work_dir="$(mktemp -d)"
  trap 'rm -rf "$work_dir"' EXIT
fi

if ! pandoc_is_current; then
  curl --fail --location --retry 3 \
    "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/${PANDOC_ARCHIVE}" \
    --output "$work_dir/$PANDOC_ARCHIVE"
  echo "$PANDOC_SHA256  $work_dir/$PANDOC_ARCHIVE" | sha256sum --check --strict
  pandoc_root="$work_dir/pandoc"
  dpkg-deb --extract "$work_dir/$PANDOC_ARCHIVE" "$pandoc_root"
  install -m 0755 "$pandoc_root/usr/bin/pandoc" "$install_dir/pandoc"
fi

if ! d2_is_current; then
  curl --fail --location --retry 3 \
    "https://github.com/terrastruct/d2/releases/download/${D2_VERSION}/${D2_ARCHIVE}" \
    --output "$work_dir/$D2_ARCHIVE"
  echo "$D2_SHA256  $work_dir/$D2_ARCHIVE" | sha256sum --check --strict
  tar --extract --gzip --file "$work_dir/$D2_ARCHIVE" --directory "$work_dir"
  d2_binary="$(find "$work_dir" -type f -path '*/bin/d2' -print -quit)"
  if [[ -z "$d2_binary" ]]; then
    echo "Verified D2 archive does not contain a bin/d2 executable." >&2
    exit 1
  fi
  install -m 0755 "$d2_binary" "$install_dir/d2"
fi

# The doc-build tools need this venv's bin directory first on PATH; the script prints that line at the end.
venv_dir="${DOC_TOOLS_VENV:-$HOME/.local/share/theforge-doc-build-venv}"
# The marker holds the sha256 of docs/tools/requirements.txt as last installed, so a pin bump
# reaches a venv that already imports the old versions.
venv_marker="$venv_dir/.requirements-installed"
requirements_hash="$(sha256sum docs/tools/requirements.txt | cut -d' ' -f1)"
[[ -x "$venv_dir/bin/python" ]] || python3 -m venv "$venv_dir"
if [[ "$(cat "$venv_marker" 2>/dev/null)" != "$requirements_hash" ]] \
  || ! "$venv_dir/bin/python" -c 'import vl_convert, weasyprint' >/dev/null 2>&1; then
  "$venv_dir/bin/python" -m pip install --quiet -r docs/tools/requirements.txt
  printf '%s\n' "$requirements_hash" > "$venv_marker"
fi

export PATH="$venv_dir/bin:$install_dir:$PATH"
pandoc --version | head -n 1
d2 version
weasyprint --version
python -c 'import vl_convert; print("vl-convert", vl_convert.__version__)'
echo "Doc tools ready. Run 'export PATH=\"$venv_dir/bin:$install_dir:\$PATH\"' in each new shell."
