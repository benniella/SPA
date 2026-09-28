# Experiments

Config-driven pipeline runs with recorded parameters and results.

The point of this directory is **comparability**. "The new detector seems better"
is not a decision; "detection recall rose from 0.81 to 0.88 across 12 of our
matches, at 2.3× the inference cost" is.

## Structure

'''
experiments/
├── configs/        committed  — one YAML/TOML per experiment definition
│   └── example.yaml
└── runs/           git-ignored — outputs, one directory per run
    └── <timestamp>-<slug>/
        ├── params.json      the fully resolved configuration
        ├── metrics.json     measured results
        └── notes.md         what was expected and what actually happened
'''

## Rules

1. **Configs are committed, run outputs are not.** A run directory is large and
   machine-specific; the config plus the recorded metrics are what reproduce it.
2. **'params.json' is the *resolved* configuration**, including anything defaulted
   implicitly. A run whose parameters cannot be reconstructed is not evidence.
3. **Metrics are recorded per match, not as a single average.** A method that is
   better on average but fails on one camera angle is a different proposition
   from one that is uniformly better, and averaging hides that.
4. **Negative results are recorded.** An experiment that shows a model does not
   work on SPA's footage is a result worth keeping; without it, someone repeats it
   in six months.

## Empty in Phase 0

There is nothing to experiment on yet. 'configs/example.yaml' documents the
intended shape of a configuration without pretending an experiment has been run.