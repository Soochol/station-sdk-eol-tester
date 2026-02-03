"""
Hardware Adapter for Station Service SDK Integration

This adapter bridges the station-service-sdk interface with hardware infrastructure.
Self-contained standalone implementation supporting both mock and real hardware.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# Standalone imports (self-contained)
from .domain.value_objects import (
    HardwareConfig,
    TestConfiguration,
    TestMeasurements,
    CycleResult,
    DUTCommandInfo,
)
from .services.hardware_facade import HardwareServiceFacade
from .services.industrial_system_manager import IndustrialSystemManager
from .services.tower_lamp_service import SystemStatus
from .services.configuration_validator import ConfigurationValidator


class EOLHardwareAdapter:
    """
    Adapter class that wraps HardwareServiceFacade for station-service-sdk integration.

    This adapter provides a simplified interface for the EOL sequence to interact
    with the hardware services while maintaining compatibility with the SDK's
    expected hardware patterns.
    """

    def __init__(
        self,
        hardware_facade: "HardwareServiceFacade",
        test_config: "TestConfiguration",
        hardware_config: "HardwareConfig",
    ):
        """
        Initialize the hardware adapter.

        Args:
            hardware_facade: The existing hardware service facade
            test_config: Test configuration parameters
            hardware_config: Hardware connection configuration
        """
        self._facade = hardware_facade
        self._test_config = test_config
        self._hardware_config = hardware_config
        self._connected = False

        # Industrial System Manager (lazy initialized)
        self._industrial_manager: Optional[IndustrialSystemManager] = None

        # Configuration Validator
        self._config_validator = ConfigurationValidator()

    @property
    def is_connected(self) -> bool:
        """Check if hardware is connected."""
        return self._connected

    @property
    def test_config(self) -> "TestConfiguration":
        """Get the test configuration."""
        return self._test_config

    @property
    def hardware_config(self) -> "HardwareConfig":
        """Get the hardware configuration."""
        return self._hardware_config

    @property
    def industrial_manager(self) -> Optional[IndustrialSystemManager]:
        """Get the industrial system manager (may be None if not initialized)."""
        return self._industrial_manager

    # =========================================================================
    # Configuration Validation
    # =========================================================================

    async def validate_configurations(self) -> None:
        """
        Validate test and hardware configurations.

        Raises:
            ConfigurationValidationError: If validation fails
        """
        logger.info("EOLHardwareAdapter: Validating configurations...")
        await self._config_validator.validate_all_configurations(
            self._test_config,
            self._hardware_config,
        )
        logger.info("EOLHardwareAdapter: Configuration validation passed")

    async def get_configuration_summary(self) -> Dict[str, Any]:
        """Get configuration summary for logging."""
        return await self._config_validator.get_configuration_summary(
            self._test_config,
            self._hardware_config,
        )

    # =========================================================================
    # Industrial System Manager
    # =========================================================================

    async def initialize_industrial_system(self) -> None:
        """Initialize industrial system manager for tower lamp control."""
        if self._industrial_manager is not None:
            logger.debug("Industrial system already initialized")
            return

        try:
            logger.info("EOLHardwareAdapter: Initializing industrial system...")
            self._industrial_manager = IndustrialSystemManager(
                digital_io_service=self._facade.digital_io_service,
                hardware_config=self._hardware_config,
            )
            await self._industrial_manager.initialize_system()
            logger.info("EOLHardwareAdapter: Industrial system initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize industrial system: {e}")
            self._industrial_manager = None

    async def set_system_status(self, status: SystemStatus) -> None:
        """Set system status for tower lamp indication."""
        if self._industrial_manager:
            await self._industrial_manager.set_system_status(status)

    async def handle_test_completion(
        self, test_success: bool, test_error: bool = False
    ) -> None:
        """Handle test completion with tower lamp indication."""
        if self._industrial_manager:
            await self._industrial_manager.handle_test_completion(
                test_success=test_success,
                test_error=test_error,
            )

    async def shutdown_industrial_system(self) -> None:
        """Shutdown industrial system manager."""
        if self._industrial_manager:
            await self._industrial_manager.shutdown_system()
            self._industrial_manager = None

    async def connect(self) -> None:
        """Connect to all hardware devices."""
        logger.info("EOLHardwareAdapter: Connecting to hardware...")
        await self._facade.connect_all_hardware(self._hardware_config)
        self._connected = True
        logger.info("EOLHardwareAdapter: Hardware connected successfully")

    async def disconnect(self) -> None:
        """Disconnect from all hardware devices."""
        logger.info("EOLHardwareAdapter: Disconnecting from hardware...")
        await self._facade.shutdown_hardware(self._hardware_config)
        self._connected = False
        logger.info("EOLHardwareAdapter: Hardware disconnected")

    async def initialize(self) -> None:
        """Initialize hardware with configuration settings."""
        logger.info("EOLHardwareAdapter: Initializing hardware...")
        await self._facade.initialize_hardware(
            self._test_config,
            self._hardware_config,
        )
        logger.info("EOLHardwareAdapter: Hardware initialized")

    async def setup_test(self) -> None:
        """Setup hardware for test execution (power on, MCU boot, LMA standby)."""
        logger.info("EOLHardwareAdapter: Setting up test...")
        await self._facade.setup_test(
            self._test_config,
            self._hardware_config,
        )
        logger.info("EOLHardwareAdapter: Test setup complete")

    async def execute_force_test(
        self,
        dut_info: "DUTCommandInfo",
    ) -> Tuple["TestMeasurements", List["CycleResult"]]:
        """
        Execute the force test sequence.

        Args:
            dut_info: Device Under Test information

        Returns:
            Tuple of (TestMeasurements, List[CycleResult])
        """
        logger.info("EOLHardwareAdapter: Executing force test sequence...")
        measurements, cycle_results = await self._facade.perform_force_test_sequence(
            self._test_config,
            self._hardware_config,
            dut_info,
        )
        logger.info("EOLHardwareAdapter: Force test sequence completed")
        return measurements, cycle_results

    async def teardown_test(self) -> None:
        """Teardown test and return hardware to safe state."""
        logger.info("EOLHardwareAdapter: Tearing down test...")
        await self._facade.teardown_test(
            self._test_config,
            self._hardware_config,
        )
        logger.info("EOLHardwareAdapter: Test teardown complete")

    async def get_hardware_status(self) -> Dict[str, bool]:
        """Get connection status of all hardware devices."""
        return await self._facade.get_hardware_status()

    async def read_temperature(self) -> float:
        """Read current MCU temperature."""
        return await self._facade.mcu_service.get_temperature()

    async def read_force(self) -> float:
        """Read current force value from loadcell."""
        force = await self._facade.loadcell_service.read_force()
        return force.value if hasattr(force, "value") else force

    async def read_peak_force(self) -> float:
        """Read peak force value from loadcell."""
        force = await self._facade.loadcell_service.read_peak_force()
        return force.value if hasattr(force, "value") else force

    async def move_robot_to_position(self, position: float) -> None:
        """
        Move robot to specified position.

        Args:
            position: Target position in micrometers
        """
        await self._facade.robot_service.move_absolute(
            position=position,
            axis_id=self._hardware_config.robot.axis_id,
            velocity=self._test_config.velocity,
            acceleration=self._test_config.acceleration,
            deceleration=self._test_config.deceleration,
        )

    async def get_robot_position(self) -> float:
        """Get current robot position in micrometers."""
        return await self._facade.robot_service.get_position(
            self._hardware_config.robot.axis_id
        )

    async def set_temperature(self, temperature: float) -> None:
        """
        Set MCU operating temperature.

        Args:
            temperature: Target temperature in Celsius
        """
        await self._facade.mcu_service.set_operating_temperature(temperature)

    async def verify_temperature(self, expected_temp: float) -> None:
        """
        Verify MCU temperature is within tolerance.

        Args:
            expected_temp: Expected temperature in Celsius
        """
        await self._facade.verify_mcu_temperature(expected_temp, self._test_config)

    def reset_robot_homing_state(self) -> None:
        """Reset robot homing state for re-initialization."""
        self._facade.reset_robot_homing_state()

    # =========================================================================
    # Power Supply Control Methods
    # =========================================================================

    async def set_voltage(self, voltage: float) -> None:
        """
        Set power supply output voltage.

        Args:
            voltage: Target voltage in volts
        """
        await self._facade.power_service.set_voltage(voltage)

    async def get_voltage(self) -> float:
        """Get current power supply voltage."""
        return await self._facade.power_service.get_voltage()

    async def set_current(self, current: float) -> None:
        """
        Set power supply output current.

        Args:
            current: Target current in amperes
        """
        await self._facade.power_service.set_current(current)

    async def get_current(self) -> float:
        """Get current power supply current."""
        return await self._facade.power_service.get_current()

    async def set_current_limit(self, current: float) -> None:
        """
        Set power supply current limit.

        Args:
            current: Current limit in amperes
        """
        await self._facade.power_service.set_current_limit(current)

    async def get_current_limit(self) -> float:
        """Get power supply current limit."""
        return await self._facade.power_service.get_current_limit()

    async def enable_power_output(self) -> None:
        """Enable power supply output."""
        await self._facade.power_service.enable_output()

    async def disable_power_output(self) -> None:
        """Disable power supply output."""
        await self._facade.power_service.disable_output()

    async def is_power_output_enabled(self) -> bool:
        """Check if power supply output is enabled."""
        return await self._facade.power_service.is_output_enabled()

    async def get_power_status(self) -> Dict[str, Any]:
        """Get power supply status information."""
        return await self._facade.power_service.get_status()

    async def get_all_power_measurements(self) -> Dict[str, float]:
        """
        Get all power measurements at once.

        Returns:
            Dictionary containing voltage, current, and power values
        """
        return await self._facade.power_service.get_all_measurements()

    # =========================================================================
    # Digital Input Methods
    # =========================================================================

    async def read_digital_input(self, channel: int) -> bool:
        """
        Read digital input from specified channel.

        Args:
            channel: Digital input channel number

        Returns:
            True if input is HIGH, False if LOW
        """
        return await self._facade.digital_io_service.read_input(channel)

    async def read_all_digital_inputs(self) -> List[bool]:
        """
        Read all digital inputs.

        Returns:
            List of boolean values representing all input states
        """
        return await self._facade.digital_io_service.read_all_inputs()

    async def get_digital_input_count(self) -> int:
        """Get the number of available digital input channels."""
        return await self._facade.digital_io_service.get_input_count()

    async def read_multiple_digital_inputs(self, channels: List[int]) -> Dict[int, bool]:
        """
        Read multiple digital inputs.

        Args:
            channels: List of input channel numbers

        Returns:
            Dictionary mapping channel numbers to their boolean values
        """
        return await self._facade.digital_io_service.read_multiple_inputs(channels)

    # =========================================================================
    # Digital Output Methods
    # =========================================================================

    async def write_digital_output(self, channel: int, level: bool) -> bool:
        """
        Write digital output to specified channel.

        Args:
            channel: Digital output channel number
            level: Output logic level (True=HIGH, False=LOW)

        Returns:
            True if write was successful, False otherwise
        """
        return await self._facade.digital_io_service.write_output(channel, level)

    async def read_digital_output(self, channel: int) -> bool:
        """
        Read digital output state from specified channel.

        Args:
            channel: Digital output channel number

        Returns:
            True if output is HIGH, False if LOW
        """
        return await self._facade.digital_io_service.read_output(channel)

    async def reset_all_digital_outputs(self) -> bool:
        """
        Reset all digital outputs to LOW.

        Returns:
            True if reset was successful, False otherwise
        """
        return await self._facade.digital_io_service.reset_all_outputs()

    async def write_multiple_digital_outputs(self, pin_values: Dict[int, bool]) -> bool:
        """
        Write multiple digital outputs.

        Args:
            pin_values: Dictionary mapping channel numbers to their boolean values

        Returns:
            True if all writes were successful, False otherwise
        """
        return await self._facade.digital_io_service.write_multiple_outputs(pin_values)

    async def read_all_digital_outputs(self) -> List[bool]:
        """
        Read all digital output states.

        Returns:
            List of boolean values representing all output states
        """
        return await self._facade.digital_io_service.read_all_outputs()

    async def get_digital_output_count(self) -> int:
        """Get the number of available digital output channels."""
        return await self._facade.digital_io_service.get_output_count()


def create_standalone_hardware_adapter(
    test_config: Optional[TestConfiguration] = None,
    hardware_config: Optional[HardwareConfig] = None,
) -> EOLHardwareAdapter:
    """
    Factory function to create EOLHardwareAdapter based on configuration.

    Creates hardware services based on the hardware_config settings.
    Supports both mock (development) and real (production) hardware.

    Args:
        test_config: Test configuration (uses defaults if None)
        hardware_config: Hardware configuration (uses mock defaults if None)

    Returns:
        Configured EOLHardwareAdapter instance
    """
    from .hardware.factory import HardwareFactory

    # Use defaults if not provided
    if test_config is None:
        test_config = TestConfiguration()
    if hardware_config is None:
        hardware_config = HardwareConfig()

    # Convert HardwareConfig to factory-compatible dict format
    # Factory expects {"type": "...", "connection": {...}} format
    factory_config = {
        "loadcell": {
            "type": hardware_config.loadcell.model,
            "connection": {
                "port": hardware_config.loadcell.port,
                "baudrate": hardware_config.loadcell.baudrate,
                "timeout": hardware_config.loadcell.timeout,
                "bytesize": hardware_config.loadcell.bytesize,
                "stopbits": hardware_config.loadcell.stopbits,
                "parity": hardware_config.loadcell.parity,
                "indicator_id": hardware_config.loadcell.indicator_id,
            },
        },
        "mcu": {
            "type": hardware_config.mcu.model,
            "connection": {
                "port": hardware_config.mcu.port,
                "baudrate": hardware_config.mcu.baudrate,
            },
        },
        "power": {
            "type": hardware_config.power.model,
            "connection": {
                "host": hardware_config.power.host,
                "port": hardware_config.power.port,
            },
        },
        "robot": {
            "type": hardware_config.robot.model,
            "axis_id": hardware_config.robot.axis_id,
            "irq_no": hardware_config.robot.irq_no,
            "motion_param_file": hardware_config.robot.motion_param_file,
        },
        "digital_io": {
            "type": hardware_config.digital_io.model,
            "input_module_no": hardware_config.digital_io.input_module_no,
            "output_module_no": hardware_config.digital_io.output_module_no,
        },
    }

    # Create hardware services using factory
    hardware = HardwareFactory.create_all_hardware(factory_config)

    # Create facade with hardware services
    facade = HardwareServiceFacade(
        robot_service=hardware.get("robot"),
        mcu_service=hardware.get("mcu"),
        loadcell_service=hardware.get("loadcell"),
        power_service=hardware.get("power"),
        digital_io_service=hardware.get("digital_io"),
    )

    return EOLHardwareAdapter(
        hardware_facade=facade,
        test_config=test_config,
        hardware_config=hardware_config,
    )
