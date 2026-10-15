# SimpleLog — project rules

## Changelog (mandatory, without being asked)

The changelog exists in 5 languages: `CHANGELOG.md` (en), `CHANGELOG.fr.md`,
`CHANGELOG.de.md`, `CHANGELOG.es.md`, `CHANGELOG.zh.md`. They are shown in the app
(Help → What's New) and in the update dialog, so they are written for end users.

- **Every user-visible change** (new feature, bug fix, behaviour change) must add an
  entry to the unreleased section at the top of **all 5 files**, in the same commit
  as the change. Unreleased section headings: `[Unreleased]`, `[Non publié]`,
  `[Unveröffentlicht]`, `[Sin publicar]`, `[未发布]`.
- Group entries under the localized subheadings already used in each file
  (Added / Fixed / Changed, etc.).
- Describe the benefit for the user, not the implementation. Purely internal changes
  (refactoring, tests, CI) do not get an entry.

## Releasing

When asked to release:
1. Rename the unreleased section to `[X.Y.Z] - YYYY-MM-DD` in all 5 changelog files,
   and add a new empty unreleased section above it.
2. Bump `__version__` in `simplelog/version.py` and `version` in `pyproject.toml`.
3. Run lint and tests, commit `chore: bump version to X.Y.Z`, tag `vX.Y.Z`, push
   master then the tag.

The release workflow fails if `CHANGELOG.md` has no section for the tag, and the
tests fail if `simplelog/version.py` is not documented or if the 5 files list different versions.
