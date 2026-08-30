# Branch workflow

`main` is the demo-ready branch. Do not push commits to it directly.

## Flow

1. Create a feature branch from `main`
2. Implement and test locally
3. Open a pull request into `main`
4. Wait for CI (backend tests + frontend build)
5. Merge the PR

```bash
git checkout main
git pull
git checkout -b feature/short-name

# ... make changes, commit ...

git push -u origin HEAD
gh pr create --title "..." --body "..."
```

After CI is green, merge on GitHub (or `gh pr merge`).

## Why

A broken change stays on the feature branch. `main` stays the version you demo and share.
