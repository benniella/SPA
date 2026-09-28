# Features

One directory per **capability**, not per page and not per component type.

'''
features/<capability>/
├── components/ UI specific to this capability
├── hooks/ data + interaction hooks for this capability
├── services/ calls to the API for this capability
├── types.ts types specific to this capability
└── index.ts the capability's public surface
'''

## The rule that makes this work

**Feature code may not import from another feature's internals.** Cross-feature
reuse goes through 'index.ts' (the public surface) or, if the thing is genuinely
generic, it is promoted to 'components/' or 'lib/'.

Without that rule a 'features/' tree becomes a second, worse 'components/' tree:
'features/matches' imports a helper from 'features/videos', 'features/analysis'
imports both, and nothing can be changed in isolation. The boundary is what
delivers the benefit, not the directory names.

## Why feature-oriented rather than layer-oriented

The alternative — 'components/', 'containers/', 'services/', 'hooks/' at the top
level — organises code by _what it is_. This organises it by _what it does_. In
a product like SPA, where "the heatmap view" or "the match page" will be worked
on by one person at a time across several files, colocating by capability means a
change touches one directory instead of four.

## The features

| Feature    | Owns                                                     |
| ---------- | -------------------------------------------------------- |
| 'matches'  | Fixture list, match detail, attaching videos to a match  |
| 'players'  | Player profiles, squad membership over time              |
| 'teams'    | Squads, seasons, team-level views                        |
| 'videos'   | Upload flow, ingestion status, video detail              |
| 'analysis' | Analysis runs, progress polling, run history             |
| 'tracking' | Trajectory views, frame scrubbing over tracked positions |
| 'heatmaps' | Spatial density rendering and controls                   |
| 'reports'  | Report generation, preview, sharing                      |

## Status

Only 'analysis' contains code today, and only one component. Every other
directory is a boundary, and empty directories in Git are a smell, so the
remaining features carry no files until there is something real to put in them.
Building screens against no data would produce fake analytics, which this
repository deliberately does not do.

'components/charts', 'components/video' and 'components/sports' are likewise
reserved boundaries. Charts need a charting library and real data; the video
component needs a player and real footage; the sports primitives need a decision
about pitch geometry, which is a Phase 1 call.
