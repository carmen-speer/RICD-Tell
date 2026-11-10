# Instructions for any Claude session working on this repository

Read this before touching any file in this repository, whether you're a
chat session the maintainer is talking to directly or the `@claude` GitHub Action
responding to a mention on an issue or PR.

## origin/main is the only ground truth

No Claude chat session working on this repository from Anthropic's cloud
sandbox has push access to GitHub. The only way a change reaches this
repository is either (a) the maintainer pasting file content into GitHub's own
web editor, or (b) the `@claude` GitHub Action, which runs
directly against the live repository and can commit for real.

A chat session's local working copy of this repo is a snapshot from
whenever it was cloned or last synced. It goes stale the moment the maintainer
pastes anything directly into GitHub, or a workflow run commits anything
(the scheduled `rescore.yml` run, a diagnostic workflow, a manual edit) --
and both happen independently of any given chat, on the maintainer's own
schedule, without that chat knowing. So a local working copy can only
ever be *behind* `origin/main`, never ahead of it in any way that matters.

**Before claiming any file needs to be created, fixed, or pasted into
GitHub, run:**

```
git fetch origin
git diff origin/main -- <path>
```

If the file is already identical (or origin's version is newer/more
complete than the local copy), say so plainly and don't ask the maintainer to do
anything. Never say a file "still needs to be pasted" without having
just run this check. Getting this wrong wastes the maintainer's time and usage
limit re-doing work that's already done.

## Formatting file content for chat pasting

When giving the maintainer a file's full content to paste into GitHub's web
editor, check whether the file itself contains fenced code blocks
(sequences of 3+ backticks) before wrapping the whole thing in a fence of
your own. If it does, your wrapping fence needs *more* backticks than the
longest run inside the file, or the file's own internal fence will close
your wrapper early and the message will render as broken, mixed
plain-text/code-block garbage. When in doubt, check first:

```
grep -c '```' <file>
```

## Working conventions for changes to this repository

- Explain each step plainly and completely; don't assume familiarity with
  any particular git or GitHub term or button.
- For any file that needs to change: give the exact target URL and the
  complete file content in the chat, never a snippet or a single line to
  edit by hand.
- Changes are committed quickly, via GitHub's one-click "copy all." When
  asking for several files to be committed and separately for a specific
  workflow to be run, state the file count and name the workflow by its
  literal filename, as two distinct, unambiguous instructions -- never
  phrased so it reads like all of them are workflows to run.
- Before executing a concrete, consequential edit to shared/public-facing
  material (this README, the live dashboard, anything already public),
  confirm the specific plan with the maintainer first, even under general
  standing direction to keep working. Routine continuation of
  already-agreed work doesn't need to stall on this.
