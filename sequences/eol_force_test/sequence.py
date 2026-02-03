"""
EOL Force Test Sequence

This sequence implements the End-of-Line force testing protocol
using the station-service-sdk v2 framework.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from loguru import logger

from station_service_sdk import (
    SequenceBase,
    RunResult,
    ExecutionContext,
    SetupError,
    TeardownError,
    StepError,
    ConnectionError,
)

from .domain.value_objects import DUTCommandInfo, TestConfiguration
from .domain.exceptions import ConfigurationValidationError
from .services.result_repository import ResultRepository

if TYPE_CHECKING:
    from .hardware_adapter import EOLHardwareAdapter
    from .services.tower_lamp_service import SystemStatus


class EOLForceTestSequence(SequenceBase):
    """
    End-of-Line Force Test Sequence

    This sequence performs comprehensive force testing across multiple
    temperatures and stroke positions for wafer fabrication devices.

    Test Flow:
    1. Setup: Connect hardware, initialize, power on, MCU boot (auto-emitted by SDK)
    2. Run: Execute temperature/position matrix measurements
    3. Teardown: Safe shutdown and cleanup (auto-emitted by SDK)

    Note: SDK automatically handles setup/teardown step emissions.
    Total steps = run steps + 2 (setup at step 0, teardown at last)
    """

    name = "eol_force_test"
    version = "1.0.0"
    description = "End-of-Line force test sequence for WF devices"

    def __init__(
        self,
        context: ExecutionContext,
        hardware_adapter: Optional["EOLHardwareAdapter"] = None,
        **kwargs: Any,
    ):
        """
        Initialize the EOL Force Test sequence.

        Args:
            context: Execution context from station-service-sdk
            hardware_adapter: Pre-configured hardware adapter (optional)
            **kwargs: Additional arguments passed to SequenceBase
        """
        super().__init__(context, **kwargs)

        self._hardware: Optional["EOLHardwareAdapter"] = hardware_adapter
        self._dut_info: Optional["DUTCommandInfo"] = None
        self._test_passed = False
        self._measurements: Dict[str, Any] = {}
        self._cycle_results: List[Any] = []
        self._result_repository: Optional[ResultRepository] = None
        self._test_start_time: Optional[datetime] = None

        # Get parameters using SDK utility method
        self.stop_on_failure = self.get_parameter("stop_on_failure", True)

    @property
    def hardware(self) -> "EOLHardwareAdapter":
        """Get the hardware adapter (raises if not initialized)."""
        if self._hardware is None:
            raise SetupError("Hardware adapter not initialized")
        return self._hardware

    async def setup(self) -> None:
        """
        Setup phase: Initialize hardware and prepare for testing.

        Note: SDK automatically emits step_start/complete for setup (lifecycle: true).
        Do NOT manually emit steps here - just perform setup logic.
        """
        self.emit_log("info", "Starting EOL Force Test setup...")

        try:
            # Initialize hardware adapter if not provided
            if self._hardware is None:
                self.emit_log("info", "Initializing hardware adapter...")
                self._hardware = await self._create_hardware_adapter()
                self.emit_log("info", "Hardware adapter initialized")

            # Check for abort request
            self.check_abort()

            # Validate configurations before proceeding
            self.emit_log("info", "Validating configurations...")
            try:
                await self.hardware.validate_configurations()
                summary = await self.hardware.get_configuration_summary()
                self.emit_log("info", f"Configuration summary: {summary}")
            except ConfigurationValidationError as e:
                self.emit_error("CONFIG_VALIDATION", str(e), recoverable=False)
                raise SetupError(f"Configuration validation failed: {e}") from e

            # Check for abort request
            self.check_abort()

            # Connect to hardware
            self.emit_log("info", "Connecting to hardware devices...")
            await self.hardware.connect()

            # Log hardware status
            status = await self.hardware.get_hardware_status()
            self.emit_log("info", f"Hardware status: {status}")

            # Check for abort request
            self.check_abort()

            # Initialize Industrial System Manager (Tower Lamp)
            self.emit_log("info", "Initializing industrial system (Tower Lamp)...")
            try:
                await self.hardware.initialize_industrial_system()
                self.emit_log("info", "Industrial system initialized - Green lamp ON")
            except Exception as lamp_error:
                self.emit_log("warning", f"Industrial system init failed (non-critical): {lamp_error}")

            # Check for abort request
            self.check_abort()

            # Initialize hardware
            self.emit_log("info", "Initializing hardware parameters...")
            await self.hardware.initialize()
            self.emit_log("info", "Hardware parameters initialized")

            # Check for abort request
            self.check_abort()

            # Setup test (power on, MCU boot, LMA standby)
            self.emit_log("info", "Setting up test environment...")
            await self.hardware.setup_test()
            self.emit_log("info", "Test environment setup complete")

            # Create DUT info from context
            self._dut_info = self._create_dut_info()
            self.emit_log("info", f"DUT: {self._dut_info.serial_number}")

            # Initialize result repository for saving test results
            self._result_repository = ResultRepository()
            self.emit_log("info", f"Result repository initialized: {self._result_repository.base_dir}")

            # Record test start time
            self._test_start_time = datetime.now()

            self.emit_log("info", "EOL Force Test setup completed successfully")

        except ConnectionError as e:
            self.emit_error("HARDWARE_CONNECTION", str(e), recoverable=False)
            raise SetupError(f"Hardware connection failed: {e}") from e
        except SetupError:
            raise
        except Exception as e:
            self.emit_error("SETUP_ERROR", str(e), recoverable=False)
            raise SetupError(f"Setup failed: {e}") from e

    async def run(self) -> RunResult:
        """
        Run phase: Execute the force test sequence.

        Note: Run steps start from index 1 (setup is step 0, managed by SDK).
        Total run steps = 1 (force_test)
        """
        self.emit_log("info", "Starting EOL Force Test execution...")

        test_config = self.hardware.test_config
        total_temps = len(test_config.temperature_list)
        total_positions = len(test_config.stroke_positions)
        total_measurements = total_temps * total_positions
        repeat_count = test_config.repeat_count

        # Total run steps: 1 (force_test)
        total_run_steps = 1

        self.emit_log(
            "info",
            f"Test matrix: {total_temps} temps x {total_positions} positions x {repeat_count} repeats = {total_measurements * repeat_count} measurements",
        )

        try:
            # Check for abort request
            self.check_abort()

            # Step 1: Execute force test sequence
            self.emit_step_start(
                "force_test",
                1,
                total_run_steps,
                f"Executing force test ({total_measurements * repeat_count} measurements)",
            )

            try:
                measurements, cycle_results = await self.hardware.execute_force_test(
                    self._dut_info,
                )

                self._measurements = measurements.to_dict() if hasattr(measurements, 'to_dict') else {}
                self._cycle_results = cycle_results

                # Build step measurements for emit_step_complete
                step_measurements = self._build_step_measurements(measurements)

                # Emit measurement events
                await self._emit_test_measurements(measurements)

                # Evaluate results
                self._test_passed = self._evaluate_results(measurements)

                self.emit_step_complete(
                    "force_test",
                    1,
                    self._test_passed,
                    test_config.estimate_test_duration_seconds(),
                    measurements=step_measurements,
                )

            except Exception as e:
                self.emit_step_complete(
                    "force_test",
                    1,
                    False,
                    0.0,
                    error=str(e),
                )
                if self.stop_on_failure:
                    self.emit_log("warning", f"Force test failed, stopping: {e}")
                    return {
                        "passed": False,
                        "measurements": self._measurements,
                        "data": {"stopped_at": "force_test", "error": str(e)},
                    }
                raise

            self.emit_log(
                "info",
                f"Force test completed: {'PASS' if self._test_passed else 'FAIL'}",
            )

            # Update Tower Lamp status based on test result
            try:
                await self.hardware.handle_test_completion(
                    test_success=self._test_passed,
                    test_error=False,
                )
            except Exception as lamp_error:
                self.emit_log("warning", f"Failed to update tower lamp: {lamp_error}")

            # Save test results to files (CSV, JSON)
            await self._save_test_results()

            return {
                "passed": self._test_passed,
                "measurements": self._measurements,
                "data": {
                    "cycle_count": len(cycle_results),
                    "temperature_count": total_temps,
                    "position_count": total_positions,
                    "repeat_count": repeat_count,
                },
            }

        except StepError:
            # Update Tower Lamp for error
            try:
                await self.hardware.handle_test_completion(test_success=False, test_error=True)
            except Exception:
                pass
            raise
        except Exception as e:
            # Update Tower Lamp for error
            try:
                await self.hardware.handle_test_completion(test_success=False, test_error=True)
            except Exception:
                pass
            self.emit_error("TEST_EXECUTION", str(e), recoverable=False)
            raise StepError(f"Force test execution failed: {e}", step_name="force_test") from e

    async def teardown(self) -> None:
        """
        Teardown phase: Safely shutdown hardware.

        Note: SDK automatically emits step_start/complete for teardown (lifecycle: true).
        Uses error accessors to check for previous errors and handle accordingly.
        """
        self.emit_log("info", "Starting EOL Force Test teardown...")

        # Check for errors in previous phases using SDK error accessors
        if self.last_error:
            self.emit_log("warning", f"Previous error detected: {self.last_error}")
            # Collect additional diagnostics on failure
            if self._hardware is not None:
                try:
                    status = await self.hardware.get_hardware_status()
                    self.emit_log("debug", f"Hardware status at teardown: {status}")
                except Exception as diag_error:
                    self.emit_log("debug", f"Failed to get diagnostics: {diag_error}")

        errors = []

        try:
            if self._hardware is not None:
                # Teardown test (return to safe state)
                try:
                    self.emit_log("info", "Tearing down test...")
                    await self.hardware.teardown_test()
                    self.emit_log("info", "Test teardown complete")
                except Exception as e:
                    errors.append(f"Teardown test failed: {e}")
                    self.emit_log("warning", f"Teardown test error: {e}")

                # Shutdown Industrial System (Tower Lamp)
                try:
                    self.emit_log("info", "Shutting down industrial system...")
                    await self.hardware.shutdown_industrial_system()
                    self.emit_log("info", "Industrial system shutdown complete")
                except Exception as e:
                    errors.append(f"Industrial system shutdown failed: {e}")
                    self.emit_log("warning", f"Industrial system shutdown error: {e}")

                # Disconnect hardware
                try:
                    self.emit_log("info", "Disconnecting hardware...")
                    await self.hardware.disconnect()
                    self.emit_log("info", "Hardware disconnected")
                except Exception as e:
                    errors.append(f"Hardware disconnect failed: {e}")
                    self.emit_log("warning", f"Disconnect error: {e}")

            self.emit_log("info", "EOL Force Test teardown completed")

            if errors:
                raise TeardownError(f"Teardown completed with errors: {'; '.join(errors)}")

        except TeardownError:
            raise
        except Exception as e:
            self.emit_error("TEARDOWN_ERROR", str(e), recoverable=False)
            raise TeardownError(f"Teardown failed: {e}") from e

    async def _create_hardware_adapter(self) -> "EOLHardwareAdapter":
        """Create hardware adapter from local configuration."""
        from .hardware_adapter import create_standalone_hardware_adapter
        from .config import load_hardware_config, load_test_profile

        # Collect parameter overrides from SDK
        overrides = self._collect_parameter_overrides()

        # Load test profile from config file (test_profiles/default.yaml)
        profile_name = self.get_parameter("test_profile", "default")
        profile_config = load_test_profile(profile_name)
        logger.info(f"Loaded test profile: {profile_name}")

        # Create test config from profile
        test_config = self._create_test_config_from_profile(profile_config)

        # Apply SDK parameter overrides (highest priority)
        if overrides:
            test_config = test_config.with_overrides(**overrides)

        # Load hardware config from local config file (self-contained)
        hardware_config = load_hardware_config()

        mode = "mock" if hardware_config.is_mock_mode() else "real hardware"
        logger.info(f"Creating hardware adapter ({mode} mode)")
        return create_standalone_hardware_adapter(
            test_config=test_config,
            hardware_config=hardware_config,
        )

    def _create_test_config_from_profile(self, profile: Dict[str, Any]) -> TestConfiguration:
        """Create TestConfiguration from profile dictionary."""
        from .domain.value_objects import PassCriteria

        if not profile:
            logger.warning("Empty profile, using defaults")
            return TestConfiguration()

        # Extract sections from profile
        hardware = profile.get("hardware", {})
        motion = profile.get("motion_control", {})
        timing = profile.get("timing", {})
        test_params = profile.get("test_parameters", {})
        execution = profile.get("execution", {})
        tolerances = profile.get("tolerances", {})
        pass_criteria_dict = profile.get("pass_criteria", {})

        # Build PassCriteria
        pass_criteria = PassCriteria(
            force_limit_min=pass_criteria_dict.get("force_limit_min", 0.0),
            force_limit_max=pass_criteria_dict.get("force_limit_max", 100.0),
            temperature_limit_min=pass_criteria_dict.get("temperature_limit_min", -10.0),
            temperature_limit_max=pass_criteria_dict.get("temperature_limit_max", 80.0),
        )

        # Build TestConfiguration
        return TestConfiguration(
            # Power settings
            voltage=hardware.get("voltage", 18.0),
            current=hardware.get("current", 20.0),
            upper_current=hardware.get("upper_current", 30.0),
            # Temperature settings
            upper_temperature=hardware.get("upper_temperature", 80.0),
            activation_temperature=hardware.get("activation_temperature", 52.0),
            standby_temperature=hardware.get("standby_temperature", 38.0),
            fan_speed=hardware.get("fan_speed", 10),
            # Motion settings
            velocity=motion.get("velocity", 100000.0),
            acceleration=motion.get("acceleration", 85000.0),
            deceleration=motion.get("deceleration", 85000.0),
            # Position settings
            initial_position=hardware.get("initial_position", 1000.0),
            operating_position=hardware.get("operating_position", 170000.0),
            # Test parameters
            temperature_list=test_params.get("temperature_list", [38.0, 52.0, 66.0]),
            stroke_positions=test_params.get("stroke_positions", [170000.0]),
            # Timing settings
            robot_move_stabilization=timing.get("robot_move_stabilization", 0.1),
            robot_standby_stabilization=timing.get("robot_standby_stabilization", 1.0),
            mcu_temperature_stabilization=timing.get("mcu_temperature_stabilization", 0.1),
            mcu_command_stabilization=timing.get("mcu_command_stabilization", 0.1),
            mcu_boot_complete_stabilization=timing.get("mcu_boot_complete_stabilization", 2.0),
            poweron_stabilization=timing.get("poweron_stabilization", 0.5),
            power_command_stabilization=timing.get("power_command_stabilization", 0.2),
            loadcell_zero_delay=timing.get("loadcell_zero_delay", 0.1),
            # Execution settings
            temperature_tolerance=tolerances.get("temperature_tolerance", 3.0),
            retry_attempts=execution.get("retry_attempts", 3),
            timeout_seconds=execution.get("timeout_seconds", 60.0),
            repeat_count=execution.get("repeat_count", 1),
            # Pass criteria
            pass_criteria=pass_criteria,
        )

    def _collect_parameter_overrides(self) -> Dict[str, Any]:
        """Collect parameter overrides from SDK get_parameter."""
        overrides: Dict[str, Any] = {}

        # Power settings
        voltage = self.get_parameter("voltage")
        if voltage is not None:
            overrides["voltage"] = voltage

        current = self.get_parameter("current")
        if current is not None:
            overrides["current"] = current

        # Temperature settings (comma-separated string -> list of floats)
        temperature_list_str = self.get_parameter("temperature_list")
        if temperature_list_str is not None:
            if isinstance(temperature_list_str, str):
                overrides["temperature_list"] = [float(t.strip()) for t in temperature_list_str.split(",")]
            elif isinstance(temperature_list_str, list):
                overrides["temperature_list"] = temperature_list_str

        standby_temperature = self.get_parameter("standby_temperature")
        if standby_temperature is not None:
            overrides["standby_temperature"] = standby_temperature

        activation_temperature = self.get_parameter("activation_temperature")
        if activation_temperature is not None:
            overrides["activation_temperature"] = activation_temperature

        # Position settings (comma-separated string -> list of floats)
        stroke_positions_str = self.get_parameter("stroke_positions")
        if stroke_positions_str is not None:
            if isinstance(stroke_positions_str, str):
                overrides["stroke_positions"] = [float(p.strip()) for p in stroke_positions_str.split(",")]
            elif isinstance(stroke_positions_str, list):
                overrides["stroke_positions"] = stroke_positions_str

        initial_position = self.get_parameter("initial_position")
        if initial_position is not None:
            overrides["initial_position"] = initial_position

        operating_position = self.get_parameter("operating_position")
        if operating_position is not None:
            overrides["operating_position"] = operating_position

        # Motion settings
        velocity = self.get_parameter("velocity")
        if velocity is not None:
            overrides["velocity"] = velocity

        acceleration = self.get_parameter("acceleration")
        if acceleration is not None:
            overrides["acceleration"] = acceleration

        # Execution settings
        repeat_count = self.get_parameter("repeat_count")
        if repeat_count is not None:
            overrides["repeat_count"] = repeat_count

        timeout_seconds = self.get_parameter("timeout_seconds")
        if timeout_seconds is not None:
            overrides["timeout_seconds"] = timeout_seconds

        return overrides

    def _create_dut_info(self) -> DUTCommandInfo:
        """Create DUT info from execution context."""
        serial_number = self.context.serial_number or "UNKNOWN"
        dut_id = self.context.wip_id or self.context.execution_id or "DUT001"
        model_number = self.get_parameter("model_number", "WF_EOL")

        return DUTCommandInfo(
            dut_id=dut_id,
            model_number=model_number,
            serial_number=serial_number,
        )

    def _build_step_measurements(self, measurements: Any) -> Dict[str, Any]:
        """Build measurements dict for emit_step_complete."""
        if not hasattr(measurements, 'to_dict'):
            return {}

        data = measurements.to_dict()
        test_config = self.hardware.test_config
        pass_criteria = test_config.pass_criteria

        # Get force limits from parameters or pass_criteria (ensure float type)
        force_limit_min = float(self.get_parameter("force_limit_min", pass_criteria.force_limit_min))
        force_limit_max = float(self.get_parameter("force_limit_max", pass_criteria.force_limit_max))

        result = {}
        for temp, positions in data.get('measurements', {}).items():
            for pos, measurement in positions.items():
                force = float(measurement.get('force', 0.0))

                # Convert temp/pos to int if whole number for cleaner names
                temp_str = int(temp) if float(temp) == int(temp) else temp
                pos_str = int(pos) if float(pos) == int(pos) else pos

                name = f"force_{temp_str}C_{pos_str}um"
                passed = force_limit_min <= force <= force_limit_max

                result[name] = {
                    "value": force,
                    "unit": "kgf",
                    "min": force_limit_min,
                    "max": force_limit_max,
                    "passed": passed,
                }

        return result

    async def _emit_test_measurements(self, measurements: Any) -> None:
        """Emit measurement events for each temperature/position."""
        step_measurements = self._build_step_measurements(measurements)

        for name, m_data in step_measurements.items():
            self.emit_measurement(
                name=name,
                value=m_data["value"],
                unit=m_data["unit"],
                min_value=m_data["min"],
                max_value=m_data["max"],
            )

    def _evaluate_results(self, measurements: Any) -> bool:
        """Evaluate test results against pass criteria."""
        if not hasattr(measurements, 'to_dict'):
            return False

        data = measurements.to_dict()
        test_config = self.hardware.test_config
        pass_criteria = test_config.pass_criteria

        # Get force limits from parameters or pass_criteria
        force_limit_min = self.get_parameter("force_limit_min", pass_criteria.force_limit_min)
        force_limit_max = self.get_parameter("force_limit_max", pass_criteria.force_limit_max)

        all_passed = True
        for temp, positions in data.get('measurements', {}).items():
            for pos, measurement in positions.items():
                force = measurement.get('force', 0.0)
                if not (force_limit_min <= force <= force_limit_max):
                    all_passed = False
                    logger.warning(
                        f"FAIL: Force {force:.2f}kgf at {temp}C/{pos}um "
                        f"outside limits [{force_limit_min}, {force_limit_max}]"
                    )

        return all_passed

    async def _save_test_results(self) -> None:
        """Save test results to files (CSV, JSON)."""
        if not self._result_repository:
            logger.warning("Result repository not initialized, skipping save")
            return

        if not self._dut_info:
            logger.warning("DUT info not available, skipping save")
            return

        try:
            # Generate test ID
            ts = datetime.now()
            test_id = f"{self._dut_info.serial_number}_{ts.strftime('%Y%m%d_%H%M%S')}"

            # Calculate duration
            if self._test_start_time:
                duration = (ts - self._test_start_time).total_seconds()
            else:
                duration = 0.0

            # Get measurements dict
            measurements_data = self._measurements.get("measurements", {})

            # Get test config for JSON export
            config_dict = {}
            if self._hardware and hasattr(self._hardware, 'test_config'):
                test_config = self._hardware.test_config
                if hasattr(test_config, 'to_structured_dict'):
                    config_dict = test_config.to_structured_dict()

            # Get repeat count for cycle info
            repeat_count = 1
            if self._hardware and hasattr(self._hardware, 'test_config'):
                repeat_count = self._hardware.test_config.repeat_count

            # Save cycle-by-cycle measurements if repeat_count > 1
            if repeat_count > 1 and self._cycle_results:
                await self._save_cycle_measurements(test_id, repeat_count)

            # Save raw measurements CSV (final/averaged values)
            self._result_repository.save_raw_measurements(
                test_id=test_id,
                serial_number=self._dut_info.serial_number,
                measurements=measurements_data,
                passed=self._test_passed,
                timestamp=ts,
            )

            # Save test summary
            self._result_repository.update_test_summary(
                test_id=test_id,
                serial_number=self._dut_info.serial_number,
                passed=self._test_passed,
                duration_seconds=duration,
                cycle_num=1,
                total_cycles=repeat_count,
                timestamp=ts,
            )

            # Save JSON (full test data)
            self._result_repository.save_test_json(
                test_id=test_id,
                serial_number=self._dut_info.serial_number,
                measurements=measurements_data,
                passed=self._test_passed,
                config=config_dict,
                duration_seconds=duration,
                timestamp=ts,
            )

            self.emit_log("info", f"Test results saved to: {self._result_repository.base_dir}")

        except Exception as e:
            logger.error(f"Failed to save test results: {e}")
            self.emit_log("warning", f"Failed to save results: {e}")

    async def _save_cycle_measurements(self, test_id: str, total_cycles: int) -> None:
        """Save cycle-by-cycle measurements to CSV (for repeat_count > 1)."""
        if not self._result_repository or not self._cycle_results:
            return

        for cycle_result in self._cycle_results:
            try:
                # Extract cycle data
                cycle_num = cycle_result.cycle_number
                is_passed = cycle_result.is_passed
                measurements = cycle_result.measurements.get("measurements", {})

                # Get timing data if available
                heating_time = 0.0
                cooling_time = 0.0
                if hasattr(cycle_result, 'execution_duration'):
                    # Use cycle duration as approximation
                    cycle_seconds = cycle_result.execution_duration.seconds
                    # Rough estimate: 60% heating, 40% cooling
                    heating_time = cycle_seconds * 0.6
                    cooling_time = cycle_seconds * 0.4

                # Get timestamp
                timestamp = cycle_result.completed_at if hasattr(cycle_result, 'completed_at') else datetime.now()

                # Save to cycle CSV
                self._result_repository.save_cycle_measurements(
                    test_id=f"{test_id}_cycle{cycle_num}",
                    serial_number=self._dut_info.serial_number,
                    cycle_num=cycle_num,
                    total_cycles=total_cycles,
                    measurements=measurements,
                    passed=is_passed,
                    heating_time=heating_time,
                    cooling_time=cooling_time,
                    timestamp=timestamp,
                )

            except Exception as e:
                logger.warning(f"Failed to save cycle {cycle_num} measurements: {e}")


# CLI entry point
if __name__ == "__main__":
    exit(EOLForceTestSequence.run_from_cli())
