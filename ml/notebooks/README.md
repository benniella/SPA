# Notebooks

Exploration and analysis. **Not a deployment path.**

A notebook is the right tool for answering a question ("does this detector hold
up on our wide-angle footage?") and the wrong place for anything the pipeline
depends on. Code graduates from here into 'detection/', 'tracking/' or
'analysis/' with tests, and the notebook keeps the reasoning that led to it.

## Conventions

* One notebook per question, named for the question:
  '001_detector_recall_on_wide_angle.ipynb'.
* Commit notebooks **with outputs cleared** ('.ipynb_checkpoints/' is ignored).
  Committed outputs go stale, bloat diffs, and are frequently wrong.
* Any number that matters is recorded in 'experiments/', not left in a notebook
  cell. A notebook that has been re-run out of order is not evidence.
* Sample footage lives outside the repository and is referenced by path or by an
  object-storage key. Match video must never be committed: it is large, and it
  frequently carries personal data about identifiable people.

## Empty in Phase 0

No notebooks are included. A repository full of empty example notebooks implies
work that has not been done. The first notebook arrives with the first real
question, in Phase 1.