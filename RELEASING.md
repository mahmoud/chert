# Releasing chert

chert uses [CalVer](https://calver.org/) (`YY.MINOR.MICRO`, e.g. `24.0.1`).

## Version Lifecycle

During development, `chert/__init__.py` carries a `dev` suffix:

```python
__version__ = '24.0.1dev'
```

At release time, the `dev` suffix is removed, the release is tagged, and the
suffix is bumped for the next development cycle. The publish workflow validates
that the version does **not** contain `dev` before uploading to PyPI.

## Prerequisites

One-time setup of PyPI Trusted Publisher / GitHub `pypi` environment (OIDC, no tokens).

## Release Steps

1. **Ensure tests pass:**

   ```bash
   tox -p auto
   ```

2. **Remove the dev suffix** in `chert/__init__.py`:

   ```python
   # Before
   __version__ = '24.0.1dev'
   # After
   __version__ = '24.0.1'
   ```

3. **Commit the release version:**

   ```bash
   git commit -am "chert version 24.0.1"
   ```

4. **Tag the release:**

   ```bash
   git tag -a 24.0.1 -m "24.0.1"
   ```

5. **Bump to next dev version** in `chert/__init__.py`:

   ```python
   __version__ = '24.0.2dev'
   ```

6. **Commit the dev bump:**

   ```bash
   git commit -am "bump version to 24.0.2dev"
   ```

7. **Push everything:**

   ```bash
   git push origin master --tags
   ```

## What Happens Next

- The `Tests` workflow runs on the push to master.
- The `Publish to PyPI` workflow triggers on the `24.0.1` tag.
  - It validates that `__version__` on the tagged commit matches the tag
    and does not contain `dev`. If either check fails, the build aborts.
  - On success, it builds with flit and publishes via PyPI Trusted Publishers
    (OIDC, no API tokens needed).
- Verify at https://pypi.org/project/chert/

## Safety Checks

The publish workflow will **refuse to publish** if:

- `__version__` contains `dev` (or any dev/pre-release suffix)
- `__version__` does not match the tag (e.g., tag `24.0.1` but version is `24.0.0`)

This means accidentally tagging a dev commit is a no-op, not a bad release.
