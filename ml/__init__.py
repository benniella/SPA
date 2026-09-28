"""SPA ML pipeline package root.

One package per processing stage: 'detection' turns frames into per-frame boxes,
'tracking' turns boxes into stable track ids, 'analysis' turns tracks into
movement, shape and workload metrics. They are separate top-level packages
because each has a different dependency footprint, so detection can later run on
a GPU host and analysis on a CPU worker.

'notebooks/' and 'experiments/' are excluded from the package.
"""
