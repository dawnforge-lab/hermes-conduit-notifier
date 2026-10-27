# Contributing to talaria-plugin

This repo is the Talaria plugin for Hermes (`talaria_push`). The iPhone app is
[hermes-talaria](https://github.com/kaishi00/hermes-talaria).

## Connected features

Most features here have siblings in the app: a tool here and the voice modes
that call it there, a route here and the screen that reads it there. They are
listed in hermes-talaria's
[docs/FEATURE_MAP.md](https://github.com/kaishi00/hermes-talaria/blob/main/docs/FEATURE_MAP.md).
Nobody tends the map separately: each PR that changes a feature keeps its
entry current.

- Before changing a feature, find its entry there and put every sibling on
  your plan, the app's included, before writing code.
- Follow the entry's rulings. Changing a ruling is the maintainer's call;
  record their decision in the entry.
- In the PR, fill in Siblings: name the entry, or the hermes-talaria PR that
  adds or updates it, then for each sibling say done, not needed (and why),
  or a gap left open. "No mapped feature" is only for a change with no
  siblings in the app.
- When the change alters an entry, update it in hermes-talaria. A feature
  with siblings in the app and no entry gets one there, and a fix that brings
  a sibling in line with an earlier change it missed adds that sibling to the
  entry.
- Text that describes a behavior is one of its siblings: tool descriptions and
  results the models read, README.md, and the app's briefings and Settings text.

## Plugin version

A version bump changes five files together: `plugin.yaml`, `events.py`,
`dashboard/manifest.json`, `tests/test_clarify_loop.py`, and a new entry on
top of `CHANGELOG.md` (Talaria shows it as the update notice). Parallel PRs
often pick the same next number, so take the next free version on main right
before merging. CI fails a PR whose version main already has.

## Tests

CI (`.github/workflows/tests.yml`) runs the plugin suite on every PR and every
push to main. To run them locally:

    pip install -r tests/requirements.txt
    python -m pytest --rootdir=tests tests
