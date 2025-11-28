"""Centralized error handling utilities.

Provides consistent error responses for both HTML (flash messages) and API (JSON) routes.
"""

from flask import flash, jsonify


# =============================================================================
# Custom Exceptions
# =============================================================================

class AppError(Exception):
    """Base application error with flash category support."""
    def __init__(self, message, category='error'):
        self.message = message
        self.category = category
        super().__init__(message)


class ValidationError(AppError):
    """Raised when user input fails validation."""
    def __init__(self, message):
        super().__init__(message, 'error')


class RegistrationClosedError(AppError):
    """Raised when registration window is not open."""
    def __init__(self, message):
        super().__init__(message, 'info')


class PaymentError(AppError):
    """Raised when a payment operation fails."""
    def __init__(self, message):
        super().__init__(message, 'error')


# =============================================================================
# Flash Message Helpers (for HTML routes)
# =============================================================================

def flash_error(message):
    """Flash an error message."""
    flash(message, 'error')


def flash_success(message):
    """Flash a success message."""
    flash(message, 'success')


def flash_info(message):
    """Flash an informational message."""
    flash(message, 'info')


# =============================================================================
# JSON Response Helpers (for API routes)
# =============================================================================

def json_error(message, status_code=400):
    """Return a standardized JSON error response.

    Args:
        message: Error message string
        status_code: HTTP status code (default 400)

    Returns:
        Tuple of (response, status_code)
    """
    return jsonify({'error': message}), status_code


def json_success(data=None):
    """Return a standardized JSON success response.

    Args:
        data: Optional dict of additional response data

    Returns:
        JSON response with status='success' plus any additional data
    """
    response = {'status': 'success'}
    if data:
        response.update(data)
    return jsonify(response)
