"""Pure-Python conversion core: models, pipeline, stages, rules.

No Qt (or any GUI toolkit) dependency belongs anywhere under `mdook.core`.
The GUI layer drives this package exclusively through the `on_progress`
callback accepted by `mdook.core.pipeline.convert`.
"""
