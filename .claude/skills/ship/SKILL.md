---
name: ship
description: Full shipping workflow for Sentinel — stage files, commit with structured message (no Co-Authored-By), and open a PR. Use at end of session to wrap up work.
---

# /ship — Sentinel Shipping Workflow

Run the full end-of-session shipping flow: review what changed, stage, commit, push, open PR.

## Steps

### 1. Assess what changed

Run in parallel:
- `git status` — lists all modified/untracked files
- `git diff` — shows staged and unstaged changes
- `git log --oneline -5` — recent commit style reference

### 2. Stage

Add only files that belong to this change. Never stage:
- `.env` or any file containing secrets
- Large binaries or data files not part of the feature
- Files unrelated to the current task

Prefer `git add <specific-file>` over `git add -A`.

### 3. Commit

Write a concise commit message focused on **why**, not what. One line subject, optional short body.

**Rules for this project:**
- Do NOT add `Co-Authored-By` trailers — ever
- Do NOT amend existing commits — always create a new one
- Follow the style of recent commits (`git log --oneline -10`)

Pass the message via heredoc to preserve formatting:
```bash
git commit -m "$(cat <<'EOF'
feat: short description of what and why

Optional body with more context.
EOF
)"
```

### 4. Push and open PR

```bash
git push -u origin HEAD
gh pr create --title "..." --body "$(cat <<'EOF'
## Summary
- bullet 1
- bullet 2

## Test plan
- [ ] item

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

PR title: keep under 70 chars.
PR body: 2–4 bullet summary + test plan checklist.

### 5. Report

Print the PR URL so the user can open it directly.

## Notes

- If `gh auth` is not set up, warn the user and stop before push
- If there are no staged changes after step 2, report that and stop — do not create empty commits
- If pre-commit hooks fail, fix the issue and create a NEW commit (never `--amend`)
