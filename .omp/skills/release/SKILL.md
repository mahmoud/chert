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

### 3. Commit the release

```bash
git commit -am "chert version 24.0.1"
```

Use the exact format `chert version X.Y.Z` for the commit message.

### 4. Tag the release

```bash
git tag -a 24.0.1 -m "24.0.1"
```

Tags are bare CalVer. No `v` prefix.

### 5. Bump to next dev version

Increment the micro version and add `dev` suffix:

```python
__version__ = '24.0.2dev'
```

### 6. Commit the dev bump

```bash
git commit -am "bump version to 24.0.2dev"
```

### 7. Push

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

- **Wrong version tagged**: `git tag -d X.Y.Z && git push origin :refs/tags/X.Y.Z`
  then fix and re-tag.
- **Publish workflow failed**: Check the GitHub Actions log. Common causes:
  version mismatch, dev suffix present, PyPI trusted publisher not configured.
- **Tests fail after publish**: The package is already on PyPI. File an issue,
  fix forward with a patch release.
