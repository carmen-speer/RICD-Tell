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

## Waiting on workflow runs (hard rule)

Never sit waiting on a running workflow, in any form: no polling loop, no
`sleep`, no timer, no command that waits for a run to finish. Each of these
blocks the conversation and spends the maintainer's usage on nothing.

When the maintainer says a run has started:

1. State the expected duration as a range (earliest and latest finish).
2. Schedule exactly two checks, one at the earliest and one at the latest
   expected finish (a scheduled check, such as `send_later`; or, if a
   session is already doing other work at that moment, one instant API
   call then). Say the two times in one line.
3. Then either continue with the next piece of work or hand the
   conversation back. Nothing runs in between.
4. Each check is a single instant look at the run's status. If the run is
   done at the first check, leave the second to fire and answer it in one
   line (deleting a scheduled check needs the maintainer's approval, which
   interrupts a low-contact day). If it is still running at the second,
   say so and schedule one later window; never keep checking.

The maintainer saying "done" after a commit means the files are committed,
not that the run has finished.

## How to report the tracker's results (hard rule)

Never present the size-and-sector comparison as the tracker's headline
result or as a failure, in the README, a report, a summary, or a reply.

Why: size and sector predict four-year closures as well as they do
because they stand in for anchoring (states, systems and endowments hold
up the colleges those two variables describe). The tracker was never
expected to beat them outright without near-perfect accuracy, so not
beating them is an expected result, not a failure. Putting it first made
outside AI reviewers (November 20, 2026) describe a tracker that passed
its pre-registered test as one that "failed," which misreports the work.

The headline is what the tracker does: it passed its pre-registered test
(v3: 32 of 56 closures caught, J 0.49), it beats the baseline trackers
(critical slowing down, the flag-every-for-profit rule), its anchor
sensor clears false flags on supported colleges, and it catches the
edge cases size and sector miss. The size-and-sector comparison is still
reported, honestly and with its numbers, inside the results and with
the anchoring explanation beside it, never as its own heading or as a
stand-alone limitation.
