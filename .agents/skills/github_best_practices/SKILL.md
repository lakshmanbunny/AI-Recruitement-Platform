---
name: github_best_practices
description: Enforces clean Git commit hygiene, branching strategies, pull request workflows, conflict resolution, and safe merge/rebase usage across this project.
---

# GitHub Best Practices Skill

This skill defines the Git standards for this project. Follow all rules below consistently whenever making commits, creating branches, resolving conflicts, or integrating code.

---

## 1. Crafting the Perfect Commit

### The Golden Rule
**Only combine changes from a single topic in a single commit.** Never cram unrelated local changes into one bloated commit.

### Staging Rules
- Use the staging area to select only the files relevant to the current topic.
- Use **`git add -p`** (patch-level staging) to go through every chunk of changes and choose precisely what to include. Answer `y` (yes) or `n` (no) per chunk.

### Commit Messages
- **Subject line**: Keep it under **80 characters**. Provide a brief summary of *what* happened. If you struggle to keep it short, you probably have mixed topics — split the commit.
- **Body**: Leave one blank line after the subject, then explain:
  - What is different now?
  - What is the reason for the change?
  - Is there anything to watch out for?

**Example:**
```
Fix candidate lookup to use fuzzy ID instead of @example.com

Previously, all metric endpoints assumed candidate IDs were email
prefixes with @example.com, breaking lookups for real Woxsen candidates.
Now resolves via DB ID, full email, roll number, or name fallback.
Watch out: roll number lookup hits the woxsen_candidates table.
```

---

## 2. Branching Strategy

### Long-Running Branches
- `main` — production-ready code only
- `develop` — active integration branch for features

**Rule:** Never commit directly to `main`. All changes arrive via PR/merge after review.

### Short-Lived Branches
- Create for: new features, bug fixes, experiments, refactors
- Name format: `feature/<short-description>`, `fix/<issue>`, `chore/<task>`
- **Always delete after merging.**

### Workflow (GitHub Flow — this project)
1. Branch off `main` (or `develop`)
2. Make focused commits on your branch
3. Open a Pull Request for review
4. Merge after approval → delete branch

---

## 3. Pull Requests

- PRs are **always based on branches**, never on individual commits.
- Before merging a feature branch into `main`, open a PR so teammates can review.
- For open source or repos you don't own: fork → clone → branch → push → PR.
- Provide a clear PR description: what changed, why, and any testing notes.

---

## 4. Handling Merge Conflicts

### Steps
1. Git will notify you of a conflict and **halt** the operation.
2. Run `git status` to see unresolved files.
3. If needed, safely abort: `git merge --abort` or `git rebase --abort`.
4. Open conflicting files — Git marks them with `<<<<<<<`, `=======`, `>>>>>>>`.
5. Edit the file to exactly what it should look like, removing all marker symbols.
6. Stage the resolved file and commit.

**Never leave conflict markers in committed code.**

---

## 5. Merge vs. Rebase

| | Merge | Rebase |
|---|---|---|
| History | Preserves branch history with a merge commit | Creates a clean, straight-line history |
| Use for | Integrating shared/remote branches | Cleaning up local, unshared commits |

### Rebase Golden Rule
**Never rebase commits that have already been pushed to a shared remote repository.**
Rewriting shared history disrupts all teammates who based work on those commits.

- ✅ Safe: `git rebase` on your own local branch before pushing
- ❌ Dangerous: `git rebase` after you've pushed to a shared remote branch

---

## Summary Checklist (apply before every commit)

- [ ] Does this commit cover **only one topic**?
- [ ] Is the subject line **under 80 characters**?
- [ ] Did I use `git add -p` to stage only relevant chunks?
- [ ] Is there a **body explaining why** the change was made?
- [ ] Am I on the correct **short-lived branch** (not committing to `main`)?
- [ ] Are there **no merge conflict markers** left in code?
