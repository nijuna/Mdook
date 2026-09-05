"""Domain-specific exceptions the pipeline raises intentionally — Batch 19.

Everywhere else in the pipeline, a failure degrades gracefully (a missing
`tesseract` binary, a corrupt embedded image, an unreadable table just
skip that one piece and keep going — see `mdook.core.stages.extraction`).
These two cases are different: the PDF cannot be converted *at all*, so
raising a clear, specific error is more honest than limping forward with
an empty manifest. `mdook.gui.worker.ConversionWorker` already catches any
`Exception` broadly and surfaces `str(exc)` to the GUI, so no special
handling is needed at the call site — just a message worth reading.
"""

from __future__ import annotations


class MdookError(Exception):
    """Base class for errors Mdook's pipeline raises intentionally."""


class EncryptedPDFError(MdookError):
    """The PDF requires a password Mdook was never given."""


class CorruptPDFError(MdookError):
    """The PDF's structure is too damaged to open or read at all."""
