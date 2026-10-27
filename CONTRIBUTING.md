# Contributing to talaria-plugin

This repo is the Talaria plugin for Hermes (`talaria_push`). The app is
Talaria, for Android.

## Connected features

Most features here have siblings in the app: a tool here and the screen that
offers it there, a route here and the screen that reads it there.

- Before changing a feature, find its siblings in the app and put every one
  on your plan before writing code.
- In the PR, fill in Siblings: for each sibling say done (name the app PR),
  not needed (and why), or a gap left open. "No siblings" is only for a
  change the app doesn't see.
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
