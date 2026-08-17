"""
Custom exception classes for the backend.
Keeps error handling centralized and consistent.
"""


class SatelliteBackendError(Exception):
    """Base exception for all backend errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class TLEValidationError(SatelliteBackendError):
    """Raised when TLE data fails validation."""

    def __init__(self, message: str = "Invalid TLE data"):
        super().__init__(message=message, status_code=400)


class TLEFetchError(SatelliteBackendError):
    """Raised when TLE data cannot be fetched from external source."""

    def __init__(self, message: str = "Failed to fetch TLE data from CelesTrak"):
        super().__init__(message=message, status_code=503)


class OrbitalCalculationError(SatelliteBackendError):
    """Raised when orbital calculations fail."""

    def __init__(self, message: str = "Orbital calculation failed"):
        super().__init__(message=message, status_code=500)


class FeatureEngineeringError(SatelliteBackendError):
    """Raised when feature engineering produces invalid results."""

    def __init__(self, message: str = "Feature engineering failed"):
        super().__init__(message=message, status_code=500)


class ModelNotLoadedError(SatelliteBackendError):
    """Raised when ML models are not available."""

    def __init__(self, message: str = "ML models are not loaded"):
        super().__init__(message=message, status_code=503)


class ModelPredictionError(SatelliteBackendError):
    """Raised when ML prediction fails."""

    def __init__(self, message: str = "Model prediction failed"):
        super().__init__(message=message, status_code=500)


class SatelliteNotFoundError(SatelliteBackendError):
    """Raised when a satellite is not found in the database."""

    def __init__(self, norad_id: str = ""):
        msg = f"Satellite not found: {norad_id}" if norad_id else "Satellite not found"
        super().__init__(message=msg, status_code=404)


class AssessmentNotFoundError(SatelliteBackendError):
    """Raised when a conjunction assessment is not found."""

    def __init__(self, assessment_id: str = ""):
        msg = f"Assessment not found: {assessment_id}" if assessment_id else "Assessment not found"
        super().__init__(message=msg, status_code=404)


class DatabaseError(SatelliteBackendError):
    """Raised when a database operation fails."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message=message, status_code=503)
