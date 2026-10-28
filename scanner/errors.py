"""Custom exceptions for Resume Scanner & Ranker.

All exceptions subclass ScannerError so the pipeline can catch them
per-file without crashing the whole scan.
"""


class ScannerError(Exception):
    """Base exception for all scanner errors."""


class UnsupportedFormatError(ScannerError):
    """Raised when a file's extension is not supported."""


class FileTooLargeError(ScannerError):
    """Raised when a file exceeds MAX_FILE_MB."""


class ExtractionError(ScannerError):
    """Raised when a file cannot be read (corrupt, password-protected, etc.)."""


class EmptyTextError(ScannerError):
    """Raised when a file has no readable text (scanned or image-only)."""


class InvalidJobDescriptionError(ScannerError):
    """Raised when the JD has no meaningful keywords."""


class ScanCancelled(ScannerError):
    """Raised when the user cancels a running scan."""
