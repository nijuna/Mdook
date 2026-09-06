"""Format-specific ingestion modules for non-PDF book sources.

Translates structured document formats (EPUB3, DOCX) directly into
`mdook.core.models.DocumentTree` and `mdook.core.models.BookManifest`,
bypassing PDF-specific extraction heuristics.
"""
