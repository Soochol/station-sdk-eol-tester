"""
Configuration Validator for standalone EOL Tester sequence.
Validates test and hardware configurations before execution.
"""

from typing import Any, Dict, List

from loguru import logger

from ..domain.value_objects import TestConfiguration, HardwareConfig
from ..domain.exceptions import ConfigurationValidationError


class ConfigurationValidator:
    """
    Configuration validation service for sequences.
    Ensures configurations are valid before test execution.
    """

    def __init__(self) -> None:
        """Initialize the configuration validator."""
        pass

    async def validate_test_configuration(self, config: TestConfiguration) -> None:
        """
        Validate test configuration.

        Args:
            config: TestConfiguration to validate

        Raises:
            ConfigurationValidationError: If validation fails
        """
        errors: List[str] = []

        # Validate power settings
        if config.voltage <= 0:
            errors.append(f"Voltage must be positive: {config.voltage}")
        if config.voltage > 50:  # Safety limit (matches default.yaml safety.max_voltage)
            errors.append(f"Voltage exceeds safety limit (50V): {config.voltage}")

        if config.current <= 0:
            errors.append(f"Current must be positive: {config.current}")
        if config.current > 50:  # Safety limit
            errors.append(f"Current exceeds safety limit (50A): {config.current}")

        # Validate temperature settings
        if not config.temperature_list:
            errors.append("Temperature list cannot be empty")
        else:
            for temp in config.temperature_list:
                if temp < 0 or temp > config.upper_temperature:
                    errors.append(
                        f"Temperature {temp}C out of range [0, {config.upper_temperature}]"
                    )

        if config.standby_temperature >= config.activation_temperature:
            errors.append(
                f"Standby temperature ({config.standby_temperature}C) must be less than "
                f"activation temperature ({config.activation_temperature}C)"
            )

        # Validate position settings
        if not config.stroke_positions:
            errors.append("Stroke positions list cannot be empty")
        else:
            for pos in config.stroke_positions:
                if pos < 0:
                    errors.append(f"Position must be non-negative: {pos}")
                if pos < config.initial_position:
                    errors.append(
                        f"Position {pos} is less than initial position {config.initial_position}"
                    )

        # Validate motion settings
        if config.velocity <= 0:
            errors.append(f"Velocity must be positive: {config.velocity}")

        if config.acceleration <= 0:
            errors.append(f"Acceleration must be positive: {config.acceleration}")

        if config.deceleration <= 0:
            errors.append(f"Deceleration must be positive: {config.deceleration}")

        # Validate timing settings
        if config.timeout_seconds <= 0:
            errors.append(f"Timeout must be positive: {config.timeout_seconds}")

        if config.repeat_count < 1:
            errors.append(f"Repeat count must be at least 1: {config.repeat_count}")

        # Validate pass criteria
        if config.pass_criteria.force_limit_min >= config.pass_criteria.force_limit_max:
            errors.append(
                f"Force limit min ({config.pass_criteria.force_limit_min}) must be less than "
                f"max ({config.pass_criteria.force_limit_max})"
            )

        if errors:
            logger.error(f"Test configuration validation failed with {len(errors)} errors")
            for error in errors:
                logger.error(f"  - {error}")
            raise ConfigurationValidationError(
                message="Test configuration validation failed",
                errors=errors,
            )

        logger.info("Test configuration validation passed")

    async def validate_hardware_configuration(self, config: HardwareConfig) -> None:
        """
        Validate hardware configuration.

        Args:
            config: HardwareConfig to validate

        Raises:
            ConfigurationValidationError: If validation fails
        """
        errors: List[str] = []

        # Validate robot config
        if config.robot.axis_id < 0:
            errors.append(f"Robot axis ID must be non-negative: {config.robot.axis_id}")

        # Validate MCU config
        if config.mcu.baudrate <= 0:
            errors.append(f"MCU baudrate must be positive: {config.mcu.baudrate}")

        # Validate power config
        if config.power.port <= 0:
            errors.append(f"Power port must be positive: {config.power.port}")

        # Validate loadcell config
        if config.loadcell.baudrate <= 0:
            errors.append(f"LoadCell baudrate must be positive: {config.loadcell.baudrate}")

        if errors:
            logger.error(f"Hardware configuration validation failed with {len(errors)} errors")
            for error in errors:
                logger.error(f"  - {error}")
            raise ConfigurationValidationError(
                message="Hardware configuration validation failed",
                errors=errors,
            )

        logger.info("Hardware configuration validation passed")

    async def validate_all_configurations(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
    ) -> None:
        """
        Validate all configurations.

        Args:
            test_config: TestConfiguration to validate
            hardware_config: HardwareConfig to validate

        Raises:
            ConfigurationValidationError: If any validation fails
        """
        logger.info("Starting comprehensive configuration validation...")

        # Validate test configuration
        await self.validate_test_configuration(test_config)

        # Validate hardware configuration
        await self.validate_hardware_configuration(hardware_config)

        # Cross-validation
        await self._validate_configuration_compatibility(test_config, hardware_config)

        logger.info("All configuration validations passed")

    async def _validate_configuration_compatibility(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
    ) -> None:
        """
        Validate compatibility between test and hardware configurations.

        Args:
            test_config: TestConfiguration
            hardware_config: HardwareConfig

        Raises:
            ConfigurationValidationError: If compatibility validation fails
        """
        errors: List[str] = []

        # Check if max stroke position is reasonable for robot
        max_stroke = max(test_config.stroke_positions) if test_config.stroke_positions else 0
        if max_stroke > 500000:  # 500mm safety limit
            errors.append(f"Max stroke position {max_stroke}um exceeds safety limit (500000um)")

        # Check operating position
        if test_config.operating_position > 500000:
            errors.append(
                f"Operating position {test_config.operating_position}um exceeds safety limit"
            )

        if errors:
            logger.error(f"Configuration compatibility check failed with {len(errors)} errors")
            for error in errors:
                logger.error(f"  - {error}")
            raise ConfigurationValidationError(
                message="Configuration compatibility validation failed",
                errors=errors,
            )

        logger.debug("Configuration compatibility validation passed")

    async def get_configuration_summary(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
    ) -> Dict[str, Any]:
        """
        Generate configuration summary for logging.

        Args:
            test_config: TestConfiguration
            hardware_config: HardwareConfig

        Returns:
            Dictionary containing configuration summary
        """
        return {
            "test_configuration": {
                "voltage": test_config.voltage,
                "current": test_config.current,
                "temperature_count": len(test_config.temperature_list),
                "temperature_range": (
                    [min(test_config.temperature_list), max(test_config.temperature_list)]
                    if test_config.temperature_list
                    else [0, 0]
                ),
                "position_count": len(test_config.stroke_positions),
                "stroke_range": (
                    [min(test_config.stroke_positions), max(test_config.stroke_positions)]
                    if test_config.stroke_positions
                    else [0, 0]
                ),
                "repeat_count": test_config.repeat_count,
                "estimated_duration": test_config.estimate_test_duration_seconds(),
            },
            "hardware_configuration": {
                "robot_model": hardware_config.robot.model,
                "mcu_model": hardware_config.mcu.model,
                "power_model": hardware_config.power.model,
                "loadcell_model": hardware_config.loadcell.model,
                "digital_io_model": hardware_config.digital_io.model,
                "is_mock_mode": hardware_config.is_mock_mode(),
            },
        }
