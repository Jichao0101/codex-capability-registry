---
name: karpathy-guidelines
description: Use when writing, reviewing, or refactoring code and you want explicit guardrails against common LLM coding mistakes such as silent assumptions, overengineering, broad refactors, or weak verification plans. This skill is especially useful for non-trivial implementation or review work where simplicity, surgical edits, and verifiable success criteria matter. Do not use for purely mechanical edits, trivial one-line changes, or tasks where stronger repo-specific instructions already define a stricter workflow.
source: https://raw.githubusercontent.com/forrestchang/andrej-karpathy-skills/main/skills/karpathy-guidelines/SKILL.md
license: MIT
---

# Karpathy Guidelines

Behavioral guidelines to reduce common LLM coding mistakes, adapted from the upstream skill and Andrej Karpathy's observations on LLM coding pitfalls.

Tradeoff: these guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

- State assumptions explicitly.
- If multiple interpretations exist, present them instead of silently picking one.
- If a simpler approach exists, say so.
- Push back when warranted.
- If something is unclear, stop and name the confusion before proceeding.

## 2. Simplicity First

Write the minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No flexibility or configurability that was not requested.
- No defensive handling for impossible scenarios.
- If the solution is much larger than necessary, rewrite it more simply.

Check yourself: would a strong senior engineer call this overcomplicated? If yes, simplify.

## 3. Surgical Changes

Touch only what you must. Clean up your own mess, including code your change makes obsolete.

When editing existing code:

- Don't improve adjacent code, comments, or formatting unless required.
- Don't refactor code that is not part of the task.
- Match the surrounding style, even if you would structure it differently.
- If you notice unrelated dead code or issues, mention them instead of silently changing them.

When your own edits create leftovers:

- Surgical change includes deleting code made obsolete by the change.
- Remove imports, variables, and functions made unused by your change.
- Remove or merge old branches, helpers, comments, and test fixtures that are replaced, bypassed, downgraded, duplicated, or stripped of their only responsibility by your change.
- Default to deletion for code made stale by your diff; keeping it requires a concrete reason such as compatibility, an active call path, or a still-valid test contract.
- Do not remove pre-existing dead code unless asked.

Test: every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

Define success criteria, then loop until verified.

Translate vague requests into verifiable goals:

- "Add validation" -> write tests for invalid inputs, then make them pass.
- "Fix the bug" -> reproduce it with a test or concrete check, then make it pass.
- "Refactor X" -> ensure behavior stays intact before and after.

For multi-step tasks, use a short plan in this form:

```text
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria support independent execution. Weak criteria like "make it work" usually require clarification.
