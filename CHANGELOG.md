# chert Changelog

## 26.0.0

_(March 6, 2026)_

- Migrate build system to uv and pyproject.toml
- Add GitHub Actions CI and automated PyPI publishing on tag
- Fix Windows compatibility (add `__main__.py`, fix StreamEmitter stderr handling)
- Expand test coverage

## 24.0.0

_(December 31, 2024)_

- Add support for Python 3.10 through 3.13
- Fix Windows compatibility issues (remove symlinks, misc bugfixes)
- Bump html5lib dependency

## 21.0.0

_(October 24, 2021)_

- Add Python 3.7 through 3.9 support
- Update to face v20.1.1
- Use safe YAML loading
- Bump lithoxyl and other dependencies
- Improve error messages for post loading failures
