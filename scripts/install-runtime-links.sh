#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_PLUGINS_DIR="${CODEX_PLUGINS_DIR:-/home/jichao/.codex/plugins}"
AGENTS_SKILLS_DIR="${AGENTS_SKILLS_DIR:-/home/jichao/.agents/skills}"
THIRD_PARTY_BACKUP_DIR="${THIRD_PARTY_BACKUP_DIR:-/home/jichao/.agents/skills-backup-20260528134913}"

FIRST_PARTY_PLUGINS=(cutepower subpower)
FIRST_PARTY_SKILLS=(karpathy-guidelines lark-doc-to-obsidian module-comment-and-naming-governance)
THIRD_PARTY_SKILLS=(
  lark-shared
  lark-openapi-explorer
  lark-calendar
  lark-im
  lark-skill-maker
  lark-whiteboard
  lark-contact
  lark-doc
  lark-base
  lark-drive
  lark-minutes
  lark-vc
  lark-sheets
  lark-wiki
  lark-event
  lark-task
  lark-workflow-meeting-summary
  lark-mail
  lark-workflow-standup-report
  profile_model_pipeline_and_compare_baseline
)

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
  local backup="${THIRD_PARTY_BACKUP_DIR}/${name}"
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

for skill in "${FIRST_PARTY_SKILLS[@]}"; do
  replace_with_symlink \
    "${REPO_ROOT}/skills/${skill}" \
    "${AGENTS_SKILLS_DIR}/${skill}" \
    "${AGENTS_SKILLS_DIR}-backup/${skill}"
done

for skill in "${THIRD_PARTY_SKILLS[@]}"; do
  restore_external_skill "$skill"
done

echo "runtime links installed"
