"""
Standalone exceptions for EOL Tester sequence.
"""

from typing import Any, Optional


class ValidationException(Exception):
    """Exception raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        message: str,
    ):
        self.field_name = field_name
        self.value = value
        self.message = message
        super().__init__(f"{field_name}: {message} (got: {value})")


class HardwareException(Exception):
    """Base exception for hardware-related errors."""

    def __init__(
        self,
        message: str,
        device: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.device = device
        self.details = details or {}
        super().__init__(message)


class HardwareConnectionException(HardwareException):
    """Exception raised when hardware connection fails."""


class HardwareOperationException(HardwareException):
    """Exception raised when hardware operation fails."""


class HardwareOperationError(Exception):
    """Hardware operation error with detailed context (compatible with src)."""

    def __init__(self, device: str, operation: str, reason: str):
        self.device = device
        self.operation = operation
        self.reason = reason
        super().__init__(f"{device} {operation} failed: {reason}")


class ConfigurationValidationError(Exception):
    """Exception raised when configuration validation fails."""

    def __init__(
        self,
        message: str,
        errors: Optional[list] = None,
        config_type: Optional[str] = None,
    ):
        self.errors = errors or []
        self.config_type = config_type
        super().__init__(message)
