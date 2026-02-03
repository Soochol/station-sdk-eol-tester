"""
Standalone value objects for EOL Tester sequence.
Simplified versions without complex external dependencies.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Dict, List, Optional



@dataclass(frozen=True)
class PassCriteria:
    """Pass/fail criteria for test evaluation."""

    force_limit_min: float = 0.0
    force_limit_max: float = 100.0
    temperature_limit_min: float = -10.0
    temperature_limit_max: float = 80.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "force_limit_min": self.force_limit_min,
            "force_limit_max": self.force_limit_max,
            "temperature_limit_min": self.temperature_limit_min,
            "temperature_limit_max": self.temperature_limit_max,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PassCriteria":
        return cls(
            force_limit_min=float(data.get("force_limit_min", 0.0)),
            force_limit_max=float(data.get("force_limit_max", 100.0)),
            temperature_limit_min=float(data.get("temperature_limit_min", -10.0)),
            temperature_limit_max=float(data.get("temperature_limit_max", 80.0)),
        )


@dataclass(frozen=True)
class TestConfiguration:
    """
    Test configuration value object containing all test parameters.
    Simplified standalone version.
    """

    # Power supply settings
    voltage: float = 18.0
    current: float = 20.0
    upper_current: float = 30.0

    # MCU/Temperature settings
    upper_temperature: float = 80.0
    activation_temperature: float = 52.0
    standby_temperature: float = 38.0
    fan_speed: int = 10

    # Motion control settings
    velocity: float = 100000.0
    acceleration: float = 85000.0
    deceleration: float = 85000.0

    # Position settings
    initial_position: float = 1000.0
    operating_position: float = 170000.0

    # Test parameters
    temperature_list: List[float] = field(
        default_factory=lambda: [38.0, 52.0, 66.0]
    )
    stroke_positions: List[float] = field(
        default_factory=lambda: [170000.0]
    )

    # Timing settings
    robot_move_stabilization: float = 0.1
    robot_standby_stabilization: float = 1.0
    mcu_temperature_stabilization: float = 0.1
    mcu_command_stabilization: float = 0.1
    mcu_boot_complete_stabilization: float = 2.0
    poweron_stabilization: float = 0.5
    power_command_stabilization: float = 0.2
    loadcell_zero_delay: float = 0.1

    # Measurement settings
    temperature_tolerance: float = 3.0

    # Execution settings
    retry_attempts: int = 3
    timeout_seconds: float = 60.0
    repeat_count: int = 1

    # Pass criteria
    pass_criteria: PassCriteria = field(default_factory=PassCriteria)

    def estimate_test_duration_seconds(self) -> float:
        """Estimate total test duration in seconds."""
        temps = len(self.temperature_list)
        positions = len(self.stroke_positions)
        base_time = 30.0 + 15.0  # setup + cleanup
        per_measurement = 5.0
        return base_time + (temps * positions * per_measurement * self.repeat_count)

    def with_overrides(self, **overrides) -> "TestConfiguration":
        """Create new configuration with overrides."""
        processed = overrides.copy()
        if "pass_criteria" in processed and isinstance(processed["pass_criteria"], dict):
            processed["pass_criteria"] = PassCriteria.from_dict(processed["pass_criteria"])
        return replace(self, **processed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voltage": self.voltage,
            "current": self.current,
            "upper_current": self.upper_current,
            "upper_temperature": self.upper_temperature,
            "activation_temperature": self.activation_temperature,
            "standby_temperature": self.standby_temperature,
            "fan_speed": self.fan_speed,
            "velocity": self.velocity,
            "acceleration": self.acceleration,
            "deceleration": self.deceleration,
            "initial_position": self.initial_position,
            "operating_position": self.operating_position,
            "temperature_list": list(self.temperature_list),
            "stroke_positions": list(self.stroke_positions),
            "robot_move_stabilization": self.robot_move_stabilization,
            "robot_standby_stabilization": self.robot_standby_stabilization,
            "mcu_command_stabilization": self.mcu_command_stabilization,
            "mcu_boot_complete_stabilization": self.mcu_boot_complete_stabilization,
            "poweron_stabilization": self.poweron_stabilization,
            "power_command_stabilization": self.power_command_stabilization,
            "temperature_tolerance": self.temperature_tolerance,
            "timeout_seconds": self.timeout_seconds,
            "repeat_count": self.repeat_count,
            "pass_criteria": self.pass_criteria.to_dict(),
        }

    def to_structured_dict(self) -> Dict[str, Any]:
        """Convert to structured dictionary for YAML export (matches default.yaml format)."""
        return {
            "hardware": {
                "voltage": self.voltage,
                "current": self.current,
                "upper_current": self.upper_current,
                "upper_temperature": self.upper_temperature,
                "activation_temperature": self.activation_temperature,
                "standby_temperature": self.standby_temperature,
                "fan_speed": self.fan_speed,
                "operating_position": self.operating_position,
                "initial_position": self.initial_position,
            },
            "motion_control": {
                "velocity": self.velocity,
                "acceleration": self.acceleration,
                "deceleration": self.deceleration,
            },
            "timing": {
                "robot_move_stabilization": self.robot_move_stabilization,
                "mcu_temperature_stabilization": self.mcu_temperature_stabilization,
                "robot_standby_stabilization": self.robot_standby_stabilization,
                "poweron_stabilization": self.poweron_stabilization,
                "power_command_stabilization": self.power_command_stabilization,
                "loadcell_zero_delay": self.loadcell_zero_delay,
                "mcu_command_stabilization": self.mcu_command_stabilization,
                "mcu_boot_complete_stabilization": self.mcu_boot_complete_stabilization,
            },
            "test_parameters": {
                "temperature_list": list(self.temperature_list),
                "stroke_positions": list(self.stroke_positions),
            },
            "safety": {
                "max_voltage": 50.0,
                "max_current": 48.0,
                "max_velocity": 100000.0,
                "max_acceleration": 100000.0,
                "max_deceleration": 100000.0,
                "max_stroke": 180000.0,
            },
            "execution": {
                "retry_attempts": self.retry_attempts,
                "timeout_seconds": self.timeout_seconds,
                "repeat_count": self.repeat_count,
            },
            "tolerances": {
                "measurement_tolerance": 0.001,
                "force_precision": 2,
                "temperature_precision": 1,
                "temperature_tolerance": self.temperature_tolerance,
            },
            "pass_criteria": {
                **self.pass_criteria.to_dict(),
                "measurement_tolerance": 0.001,
                "force_precision": 2,
                "temperature_precision": 1,
                "position_tolerance": 0.5,
                "max_test_duration": 300.0,
                "min_stabilization_time": 0.5,
                "spec_points": [],
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestConfiguration":
        data_copy = data.copy()
        if "pass_criteria" in data_copy and isinstance(data_copy["pass_criteria"], dict):
            data_copy["pass_criteria"] = PassCriteria.from_dict(data_copy["pass_criteria"])
        return cls(**data_copy)


@dataclass(frozen=True)
class RobotConfig:
    """Robot configuration."""
    model: str = "mock"
    axis_id: int = 0
    irq_no: int = 7
    timeout: float = 30.0
    polling_interval: int = 250
    motion_param_file: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RobotConfig":
        return cls(
            model=str(data.get("model", "mock")),
            axis_id=int(data.get("axis_id", 0)),
            irq_no=int(data.get("irq_no", 7)),
            timeout=float(data.get("timeout", 30.0)),
            polling_interval=int(data.get("polling_interval", 250)),
            motion_param_file=data.get("motion_param_file"),
        )


@dataclass(frozen=True)
class LoadCellConfig:
    """LoadCell configuration."""
    model: str = "mock"
    port: str = "COM8"
    baudrate: int = 9600
    timeout: float = 1.0
    bytesize: int = 8
    stopbits: int = 1
    parity: str = "even"
    indicator_id: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoadCellConfig":
        return cls(
            model=str(data.get("model", "mock")),
            port=str(data.get("port", "COM8")),
            baudrate=int(data.get("baudrate", 9600)),
            timeout=float(data.get("timeout", 1.0)),
            bytesize=int(data.get("bytesize", 8)),
            stopbits=int(data.get("stopbits", 1)),
            parity=str(data.get("parity", "even")),
            indicator_id=int(data.get("indicator_id", 0)),
        )


@dataclass(frozen=True)
class MCUConfig:
    """MCU configuration."""
    model: str = "mock"
    port: str = "COM10"
    baudrate: int = 115200
    timeout: float = 10.0
    bytesize: int = 8
    stopbits: int = 1
    parity: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCUConfig":
        return cls(
            model=str(data.get("model", "mock")),
            port=str(data.get("port", "COM10")),
            baudrate=int(data.get("baudrate", 115200)),
            timeout=float(data.get("timeout", 10.0)),
            bytesize=int(data.get("bytesize", 8)),
            stopbits=int(data.get("stopbits", 1)),
            parity=data.get("parity"),
        )


@dataclass(frozen=True)
class PowerConfig:
    """Power supply configuration."""
    model: str = "mock"
    host: str = "192.168.11.1"
    port: int = 5000
    timeout: float = 5.0
    channel: int = 1
    delimiter: str = "\n"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PowerConfig":
        delimiter = data.get("delimiter", "\n")
        if delimiter is None:
            delimiter = "\n"
        return cls(
            model=str(data.get("model", "mock")),
            host=str(data.get("host", "192.168.11.1")),
            port=int(data.get("port", 5000)),
            timeout=float(data.get("timeout", 5.0)),
            channel=int(data.get("channel", 1)),
            delimiter=str(delimiter),
        )


@dataclass(frozen=True)
class DigitalInputConfig:
    """Digital input pin configuration."""
    pin_number: int = 0
    contact_type: str = "A"
    edge_type: str = "rising"
    name: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DigitalInputConfig":
        return cls(
            pin_number=int(data.get("pin_number", 0)),
            contact_type=str(data.get("contact_type", "A")),
            edge_type=str(data.get("edge_type", "rising")),
            name=str(data.get("name", "")),
        )


@dataclass(frozen=True)
class DigitalIOConfig:
    """Digital I/O configuration."""
    model: str = "mock"
    input_module_no: int = 0   # Module for digital inputs
    output_module_no: int = 1  # Module for digital outputs
    # Input sensors
    emergency_stop_button: Optional[DigitalInputConfig] = None
    operator_start_button_left: Optional[DigitalInputConfig] = None
    operator_start_button_right: Optional[DigitalInputConfig] = None
    safety_door_closed_sensor: Optional[DigitalInputConfig] = None
    dut_clamp_safety_sensor: Optional[DigitalInputConfig] = None
    dut_chain_safety_sensor: Optional[DigitalInputConfig] = None
    # Output pins
    servo1_brake_release: int = 0
    tower_lamp_red: int = 4
    tower_lamp_yellow: int = 5
    tower_lamp_green: int = 6
    beep: int = 7

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DigitalIOConfig":
        def parse_input_config(key: str) -> Optional[DigitalInputConfig]:
            if key in data and isinstance(data[key], dict):
                return DigitalInputConfig.from_dict(data[key])
            return None

        return cls(
            model=str(data.get("model", "mock")),
            input_module_no=int(data.get("input_module_no", 0)),
            output_module_no=int(data.get("output_module_no", 1)),
            emergency_stop_button=parse_input_config("emergency_stop_button"),
            operator_start_button_left=parse_input_config("operator_start_button_left"),
            operator_start_button_right=parse_input_config("operator_start_button_right"),
            safety_door_closed_sensor=parse_input_config("safety_door_closed_sensor"),
            dut_clamp_safety_sensor=parse_input_config("dut_clamp_safety_sensor"),
            dut_chain_safety_sensor=parse_input_config("dut_chain_safety_sensor"),
            servo1_brake_release=int(data.get("servo1_brake_release", 0)),
            tower_lamp_red=int(data.get("tower_lamp_red", 4)),
            tower_lamp_yellow=int(data.get("tower_lamp_yellow", 5)),
            tower_lamp_green=int(data.get("tower_lamp_green", 6)),
            beep=int(data.get("beep", 7)),
        )


@dataclass(frozen=True)
class HardwareConfig:
    """
    Unified hardware configuration.
    Simplified standalone version.
    """

    robot: RobotConfig = field(default_factory=RobotConfig)
    loadcell: LoadCellConfig = field(default_factory=LoadCellConfig)
    mcu: MCUConfig = field(default_factory=MCUConfig)
    power: PowerConfig = field(default_factory=PowerConfig)
    digital_io: DigitalIOConfig = field(default_factory=DigitalIOConfig)

    def is_mock_mode(self) -> bool:
        return all([
            self.robot.model == "mock",
            self.loadcell.model == "mock",
            self.mcu.model == "mock",
            self.power.model == "mock",
            self.digital_io.model == "mock",
        ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robot": {"model": self.robot.model, "axis_id": self.robot.axis_id},
            "loadcell": {
                "model": self.loadcell.model,
                "port": self.loadcell.port,
                "baudrate": self.loadcell.baudrate,
                "parity": self.loadcell.parity,
                "indicator_id": self.loadcell.indicator_id,
            },
            "mcu": {"model": self.mcu.model, "port": self.mcu.port},
            "power": {"model": self.power.model, "host": self.power.host},
            "digital_io": {"model": self.digital_io.model},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardwareConfig":
        return cls(
            robot=RobotConfig.from_dict(data.get("robot", {})) if "robot" in data else RobotConfig(),
            loadcell=LoadCellConfig.from_dict(data.get("loadcell", {})) if "loadcell" in data else LoadCellConfig(),
            mcu=MCUConfig.from_dict(data.get("mcu", {})) if "mcu" in data else MCUConfig(),
            power=PowerConfig.from_dict(data.get("power", {})) if "power" in data else PowerConfig(),
            digital_io=DigitalIOConfig.from_dict(data.get("digital_io", {})) if "digital_io" in data else DigitalIOConfig(),
        )


@dataclass(frozen=True)
class DUTCommandInfo:
    """DUT information for commands."""

    dut_id: str
    model_number: str
    serial_number: str
    manufacturer: str = "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dut_id": self.dut_id,
            "model_number": self.model_number,
            "serial_number": self.serial_number,
            "manufacturer": self.manufacturer,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DUTCommandInfo":
        return cls(
            dut_id=data["dut_id"],
            model_number=data["model_number"],
            serial_number=data["serial_number"],
            manufacturer=data.get("manufacturer", "Unknown"),
        )


@dataclass
class TestMeasurements:
    """Collection of test measurements."""

    measurements: Dict[float, Dict[float, Dict[str, float]]] = field(default_factory=dict)
    timing_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "measurements": self.measurements,
            "timing_data": self.timing_data,
        }

    @classmethod
    def from_legacy_dict(
        cls,
        measurements_dict: Dict[float, Dict[float, Dict[str, float]]],
        timing_data: Optional[Dict[str, Any]] = None,
    ) -> "TestMeasurements":
        return cls(
            measurements=measurements_dict,
            timing_data=timing_data or {},
        )


@dataclass
class TestDuration:
    """Test duration value object."""

    seconds: float

    @classmethod
    def from_seconds(cls, seconds: float) -> "TestDuration":
        return cls(seconds=seconds)


@dataclass
class CycleResult:
    """Result of a single test cycle."""

    cycle_number: int
    is_passed: bool
    measurements: Dict[str, Any]
    execution_duration: TestDuration
    completed_at: datetime
    cycle_notes: str = ""
    error_message: Optional[str] = None

    @classmethod
    def create_successful(
        cls,
        cycle_number: int,
        is_passed: bool,
        measurements: Dict[str, Any],
        execution_duration: TestDuration,
        completed_at: datetime,
        cycle_notes: str = "",
    ) -> "CycleResult":
        return cls(
            cycle_number=cycle_number,
            is_passed=is_passed,
            measurements=measurements,
            execution_duration=execution_duration,
            completed_at=completed_at,
            cycle_notes=cycle_notes,
        )

    @classmethod
    def create_failed(
        cls,
        cycle_number: int,
        error_message: str,
        execution_duration: TestDuration,
        completed_at: datetime,
    ) -> "CycleResult":
        return cls(
            cycle_number=cycle_number,
            is_passed=False,
            measurements={},
            execution_duration=execution_duration,
            completed_at=completed_at,
            error_message=error_message,
        )
