#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_PLUGINS_DIR="${CODEX_PLUGINS_DIR:-/home/jichao/.codex/plugins}"
AGENTS_SKILLS_DIR="${AGENTS_SKILLS_DIR:-/home/jichao/.agents/skills}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

manifest_commit() {
  local name="$1"
  awk -v n="$name" '
    $0 ~ "name: " n "$" { in_item=1 }
    in_item && /commit:/ { print $2; exit }
    in_item && /^  - name:/ && $0 !~ "name: " n "$" { in_item=0 }
  ' "$REPO_ROOT/manifests/plugins.yaml"
}

check_plugin() {
  local name="$1"
  local expected
  local actual
  local target
  expected="$(manifest_commit "$name")"
  [ -n "$expected" ] || fail "manifest commit not found for plugin $name"
  [ -d "$REPO_ROOT/sources/submodules/$name/.git" ] || [ -f "$REPO_ROOT/sources/submodules/$name/.git" ] || fail "missing submodule checkout: $name"
  actual="$(git -C "$REPO_ROOT/sources/submodules/$name" rev-parse HEAD)"
  [ "$actual" = "$expected" ] || fail "$name submodule commit mismatch: expected $expected got $actual"
  [ -f "$REPO_ROOT/sources/submodules/$name/.codex-plugin/plugin.json" ] || fail "$name plugin manifest missing"
  [ -L "$CODEX_PLUGINS_DIR/$name" ] || fail "$CODEX_PLUGINS_DIR/$name is not a symlink"
  target="$(readlink "$CODEX_PLUGINS_DIR/$name")"
  [ "$target" = "$REPO_ROOT/sources/submodules/$name" ] || fail "$name runtime link target mismatch: $target"
}

check_first_party_skill() {
  local name="$1"
  [ -f "$REPO_ROOT/skills/$name/SKILL.md" ] || fail "missing embedded skill: $name"
  [ -L "$AGENTS_SKILLS_DIR/$name" ] || fail "$AGENTS_SKILLS_DIR/$name is not a symlink"
  [ "$(readlink "$AGENTS_SKILLS_DIR/$name")" = "$REPO_ROOT/skills/$name" ] || fail "$name skill link target mismatch"
}

check_external_skill() {
  local name="$1"
  [ -f "$AGENTS_SKILLS_DIR/$name/SKILL.md" ] || fail "missing external skill runtime dir: $name"
  [ ! -L "$AGENTS_SKILLS_DIR/$name" ] || fail "external skill must not be linked into registry: $name"
  [ ! -e "$REPO_ROOT/skills/$name" ] || fail "external skill pollutes registry source tree: $name"
}

check_plugin cutepower
check_plugin subpower
check_first_party_skill karpathy-guidelines
check_first_party_skill lark-doc-to-obsidian
check_first_party_skill module-comment-and-naming-governance

for skill in \
  lark-shared lark-openapi-explorer lark-calendar lark-im lark-skill-maker \
  lark-whiteboard lark-contact lark-doc lark-base lark-drive lark-minutes \
  lark-vc lark-sheets lark-wiki lark-event lark-task \
  lark-workflow-meeting-summary lark-mail lark-workflow-standup-report \
  profile_model_pipeline_and_compare_baseline; do
  check_external_skill "$skill"
done

echo "runtime verification passed"
