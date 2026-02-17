"""Service layer exceptions."""


class ServiceError(Exception):
    """Base service layer error."""


class NotFoundError(ServiceError):
    """Resource not found."""


class ServiceUnavailableError(ServiceError):
    """External dependency unavailable."""
