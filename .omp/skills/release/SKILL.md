---
name: release
description: |
  Release chert to PyPI. Handles version bumping (CalVer YY.MINOR.MICRO),
  tagging, pushing, and post-publish verification. Use when asked to
  "release chert", "cut a release", "publish to PyPI", or "bump version".
---

# Release chert

chert uses CalVer: `YY.MINOR.MICRO` (e.g. `24.0.1`). The version lives in
`chert/__init__.py` as a `__version__` literal string. During development it
carries a `dev` suffix (e.g. `24.0.1dev`). Flit reads this at build time.

Tags are bare CalVer (e.g. `24.0.1`, NOT `v24.0.1`). The publish workflow
triggers on tags matching `[0-9]*.[0-9]*.[0-9]*`.

## Pre-flight checks

Before starting, verify ALL of these:

1. Working tree is clean (`git status` shows nothing dirty/staged)
2. You are on `master` branch
3. `chert/__init__.py` has a `dev` suffix on `__version__`
4. All tests pass: `tox -p auto` (or at minimum `pytest tests/ -v`)
5. Check what is actually published on PyPI: https://pypi.org/project/chert/
   **PyPI is canonical.** If the intended version already exists on PyPI, it
   cannot be re-released -- bump to the next version instead. If a local/GitHub
   tag exists for a version that is NOT on PyPI, the prior release failed and
   should be retried (see "Failed release" under Error recovery).

If any check fails, stop and report. Do not proceed with a dirty tree or
failing tests.

## Release steps

### 1. Determine the release version

Read `__version__` from `chert/__init__.py`. Strip the `dev` suffix.
Example: `24.0.1dev` becomes `24.0.1`.

Ask the user to confirm the version. If they want a different version
(e.g. bumping minor instead of micro), use that instead.

### 2. Update version for release

Edit `chert/__init__.py`: remove the `dev` suffix from `__version__`.

```python
# Before
__version__ = '24.0.1dev'
# After
__version__ = '24.0.1'
```

### 3. Update CHANGELOG.md

Add a new section at the top of `CHANGELOG.md` (below the `# chert Changelog`
heading) for the release version. Use this format:

```markdown
## 24.0.1

_(Month Day, Year)_

- First change description
- Second change description
```

To determine what changed, review the commits since the last tag:

```bash
git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:'%s' --no-merges
```

Summarize the user-facing changes as concise bullet points. Omit version bump
commits and other release-mechanical commits. Ask the user to confirm or adjust
the changelog entry.

### 4. Commit the release

```bash
git commit -am "chert version 24.0.1"
```

Use the exact format `chert version X.Y.Z` for the commit message.

### 5. Tag the release

```bash
git tag -a 24.0.1 -m "short summary of key changes in this release"
```

Tags are bare CalVer. No `v` prefix. The tag message should be a short,
lowercase, descriptive summary of the release (not just the version number).
Examples:

- `"migrate to uv, expand test coverage, add CI"`
- `"python 3.10-3.13 support, windows fixes"`
- `"py3.7-3.9 support, safe yaml loading, dependency bumps"`

### 6. Bump to next dev version

Increment the micro version and add `dev` suffix:

```python
__version__ = '24.0.2dev'
```

### 7. Commit the dev bump

```bash
git commit -am "bump version to 24.0.2dev"
```

### 8. Push

```bash
git push origin master --tags
```

This triggers two GitHub Actions workflows:
- `Tests` (on the push to master)
- `Publish to PyPI` (on the tag)

The publish workflow validates that `__version__` on the tagged commit does
not contain `dev` and matches the tag. If either check fails, publishing
is blocked.

## Post-publish verification

After pushing, wait ~2 minutes for PyPI propagation, then verify:

```bash
pip install chert==24.0.1 --index-url https://pypi.org/simple/ --force-reinstall
python -c "import chert; print(chert.__version__)"
# Should print: 24.0.1
```

If `--index-url` fails with 404, wait another minute and retry. PyPI CDN
propagation can take 1-5 minutes.

Then run the test suite against the installed package:

```bash
pytest tests/ -v
```

Report the results to the user.

## Error recovery

- **Failed release** (tag exists locally/on GitHub but not on PyPI): PyPI is
  the source of truth. Delete the stale tag locally and on the remote:
  ```bash
  git tag -d X.Y.Z
  git push origin :refs/tags/X.Y.Z  # if it was pushed
  ```
  Then check `__version__` in `chert/__init__.py`. If it was already bumped
  past the failed release (e.g. `X.Y.(Z+1)dev`), reset it to `X.Y.Zdev` so
  the release flow strips the suffix to the correct version. Amend or revert
  the bump commit as needed, then restart the release from step 1.
- **Wrong version tagged**: `git tag -d X.Y.Z && git push origin :refs/tags/X.Y.Z`
  then fix and re-tag.
- **Publish workflow failed**: Check the GitHub Actions log. Common causes:
  version mismatch, dev suffix present, PyPI trusted publisher not configured.
- **Tests fail after publish**: The package is already on PyPI. File an issue,
  fix forward with a patch release.