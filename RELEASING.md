# Releasing chert

chert uses [CalVer](https://calver.org/) (`YY.MINOR.MICRO`, e.g. `26.0.0`).

## Version Lifecycle

During development, `chert/__init__.py` carries a `dev` suffix:

```python
__version__ = '26.0.0dev'
```

At release time, the `dev` suffix is removed, the release is tagged, and the
suffix is bumped for the next development cycle. The publish workflow validates
that the version does **not** contain `dev` before uploading to PyPI.

## Prerequisites

One-time setup of PyPI Trusted Publisher / GitHub `pypi` environment (OIDC, no tokens).

## Automated Release

An OMP skill automates the full release flow. Run:

```
/skill:release
```

This walks through all the steps below with pre-flight checks and
post-publish verification.

## Manual Release Steps

1. **Ensure tests pass:**

   ```bash
   tox -p auto
   ```

2. **Remove the dev suffix** in `chert/__init__.py`:

   ```python
   # Before
   __version__ = '26.0.0dev'
   # After
   __version__ = '26.0.0'
   ```

3. **Commit the release version:**

   ```bash
   git commit -am "chert version 26.0.0"
   ```

4. **Tag the release:**

   ```bash
   git tag -a 26.0.0 -m "26.0.0"
   ```

5. **Bump to next dev version** in `chert/__init__.py`:

   ```python
   __version__ = '26.0.1dev'
   ```

6. **Commit the dev bump:**

   ```bash
   git commit -am "bump version to 26.0.1dev"
   ```

7. **Push everything:**

   ```bash
   git push origin master --tags
   ```

## What Happens Next

- The `Tests` workflow runs on the push to master.
- The `Publish to PyPI` workflow triggers on the `26.0.0` tag:
  - **Validates** that `__version__` matches the tag and has no `dev` suffix.
  - **Builds** with flit and publishes via PyPI Trusted Publishers (OIDC).
  - **Verifies** the published package: installs from PyPI, checks the
    version matches, and runs the test suite.
- Verify at https://pypi.org/project/chert/

## Safety Checks

The publish workflow will **refuse to publish** if:

- `__version__` contains `dev` (or any dev/pre-release suffix)
- `__version__` does not match the tag (e.g., tag `26.0.0` but version is `25.0.0`)

After publishing, a verification job installs the package from PyPI and runs
the test suite. If verification fails, the workflow reports the error (the
package is already published at that point; fix forward with a patch release).