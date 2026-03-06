# Upgrade TODO

One-time setup actions required after merging the `modernize` branch.
Delete this file once complete.

## 1. PyPI Trusted Publisher Setup

Go to https://pypi.org/manage/project/chert/settings/publishing/ and add a new trusted publisher:

- **Owner**: `mahmoud`
- **Repository**: `chert`
- **Workflow name**: `publish.yml`
- **Environment**: `pypi`

## 2. GitHub Environment

Create a `pypi` environment in GitHub repo settings:

1. Settings > Environments > New environment
2. Name it `pypi`
3. Optionally restrict to `master` branch only (recommended)

## 3. Codecov (Optional)

If coverage reporting to Codecov is desired, add `CODECOV_TOKEN` secret to GitHub repo settings. The tox config already generates coverage XML files.
