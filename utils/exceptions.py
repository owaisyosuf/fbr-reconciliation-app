"""Custom exceptions for user-friendly error handling throughout the app."""


class ReconciliationError(Exception):
    """Base class for all reconciliation app errors. Carries a user-friendly message."""

    def __init__(self, message: str, detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)


class InvalidFileError(ReconciliationError):
    """Raised when an uploaded file is not a valid/readable Excel file."""


class MissingColumnError(ReconciliationError):
    """Raised when the required 'Sales Tax / FED in ST Mode' column can't be found."""


class EmptySheetError(ReconciliationError):
    """Raised when a sheet has no data rows to process."""


class DuplicateRecordError(ReconciliationError):
    """Raised (as a warning-carrier) when duplicate records are detected."""


class CorruptDataError(ReconciliationError):
    """Raised when data is unexpected/corrupt and can't be safely processed."""
