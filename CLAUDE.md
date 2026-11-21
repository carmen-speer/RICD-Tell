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

In the README, reports and any summary of the tracker, good results come
first and at length; limitations come later, take little space, are put
in context, and are described as limitations, never as failures. The one
exception is a test that truly failed outright: then say so plainly.
Always open by saying what the repository is: the first empirical test of
an original theory (RICD), with Tell as the instrument built to test it.
Why: reviewers who are not told this evaluate the repository as a software
product and list the original theory and single authorship as "friction
points" (November 21, 2026), missing that testing the theory is the point.
Describe RICD concretely, as a formal model of feedback divergence,
resource debt and anchoring, with its equations, never with broad
phrases such as "domain-independent theory". Why: broad descriptors made
reviewers pattern-match it to a "grand theory of everything" and call the
mathematics overhead without reading it (November 21, 2026).
Do not give limitations a stand-alone section or heading of their own:
describe them as the tracker's scope and work in progress, each with its
context. Why: AI reviewers asked for an "overall impression" fill a
pros-and-cons template by lifting whatever the README itself labels a
limitation and presenting it as their own criticism (Gemini's own
explanation, November 21, 2026).

Never present the size-and-sector comparison as the tracker's headline
result or as a failure.

Why: outside AI reviewers (November 20 and 21, 2026) repeatedly read the
README as saying the theory failed, because a limitation was placed
first and given its own heading. That misreports a tracker that passed
its pre-registered test. Size and sector predict closures well because
they stand in for anchoring (large and public institutions are
anchored, and anchored institutions rarely close, which is part of what
Tell measures), so not beating them on overall ranking is expected.

The headline is what the tracker does: it passed its pre-registered test
(v3: 32 of 56 closures caught, J 0.49); it beats the baseline trackers
(critical slowing down, the flag-every-for-profit rule) and, at its
committed cut points, the size-and-sector model (J 0.49 against 0.38;
public and nonprofit 0.29 against 0.09); it catches edge cases the proxy
misses (9 closures caught that size and sector missed, against 1 the
other way; church-anchored seminaries the proxy wrongly flags; state-held
colleges the anchor sensor clears, none of them later closures); and it
quantifies the anchors and the strain they carry across the sector. The
size-and-sector comparison is still reported, with its numbers, inside
the results with the anchoring explanation beside it.
