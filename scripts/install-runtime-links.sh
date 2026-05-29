#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_PLUGINS_DIR="${CODEX_PLUGINS_DIR:-/home/jichao/.codex/plugins}"
AGENTS_SKILLS_DIR="${AGENTS_SKILLS_DIR:-/home/jichao/.agents/skills}"
RESTORE_THIRD_PARTY=0

if [ "${1:-}" = "--restore-third-party" ]; then
  RESTORE_THIRD_PARTY=1
elif [ "${1:-}" != "" ]; then
  echo "usage: $0 [--restore-third-party]" >&2
  exit 1
fi

FIRST_PARTY_PLUGINS=(cutepower subpower)

skill_names_by_ownership() {
  local ownership="$1"
  awk -v ownership="$ownership" '
    /^  - name:/ { name=$3 }
    $1 == "ownership:" && $2 == ownership { print name }
  ' "$REPO_ROOT/manifests/skills.yaml"
}

skill_source_value() {
  local name="$1"
  local key="$2"
  awk -v name="$name" -v key="$key" '
    BEGIN { needle = key ":" }
    /^  - name:/ { in_item=($3 == name) }
    in_item && $1 == needle { print $2; exit }
  ' "$REPO_ROOT/manifests/skills.yaml"
}

backup_dir() {
  local base="$1"
  local stamp
  stamp="$(date +%Y%m%d%H%M%S)"
  echo "${base}-${stamp}"
}

replace_with_symlink() {
  local src="$1"
  local dst="$2"
  local backup_base="$3"
  if [ ! -e "$src" ]; then
    echo "missing source: $src" >&2
    exit 1
  fi
  if [ -L "$dst" ]; then
    rm "$dst"
  elif [ -e "$dst" ]; then
    local backup
    backup="$(backup_dir "$backup_base")"
    mkdir -p "$(dirname "$backup")"
    mv "$dst" "$backup"
    echo "backed up $dst to $backup"
  fi
  ln -s "$src" "$dst"
}

restore_external_skill() {
  local name="$1"
  local dst="${AGENTS_SKILLS_DIR}/${name}"
  local backup
  backup="$(skill_source_value "$name" "restore_from")"
  if [ -L "$dst" ]; then
    rm "$dst"
  elif [ -e "$dst" ]; then
    return
  fi
  if [ -d "$backup" ]; then
    cp -a "$backup" "$dst"
    echo "restored external skill $name from $backup"
  else
    echo "external skill $name has no runtime dir and no backup at $backup" >&2
    exit 1
  fi
}

mkdir -p "$CODEX_PLUGINS_DIR" "$AGENTS_SKILLS_DIR"

for plugin in "${FIRST_PARTY_PLUGINS[@]}"; do
  replace_with_symlink \
    "${REPO_ROOT}/sources/submodules/${plugin}" \
    "${CODEX_PLUGINS_DIR}/${plugin}" \
    "${CODEX_PLUGINS_DIR}-backup/${plugin}"
done

while IFS= read -r skill; do
  replace_with_symlink \
    "${REPO_ROOT}/skills/${skill}" \
    "${AGENTS_SKILLS_DIR}/${skill}" \
    "${AGENTS_SKILLS_DIR}-backup/${skill}"
done < <(skill_names_by_ownership first_party_embedded)

if [ "$RESTORE_THIRD_PARTY" -eq 1 ]; then
  while IFS= read -r skill; do
    restore_external_skill "$skill"
  done < <(skill_names_by_ownership third_party_external)
else
  while IFS= read -r skill; do
    if [ ! -e "${AGENTS_SKILLS_DIR}/${skill}" ]; then
      echo "third-party skill not installed: ${skill}"
    fi
  done < <(skill_names_by_ownership third_party_external)
fi

echo "runtime links installed"
