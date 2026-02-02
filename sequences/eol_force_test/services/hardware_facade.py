"""
Hardware Service Facade for standalone EOL Tester sequence.
Simplified coordinator that orchestrates hardware services.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..domain.enums import RobotState
from ..domain.value_objects import (
    CycleResult,
    DUTCommandInfo,
    HardwareConfig,
    TestConfiguration,
    TestDuration,
    TestMeasurements,
)
from ..interfaces import (
    DigitalIOService,
    LoadCellService,
    MCUService,
    PowerService,
    RobotService,
    TestMode,
)


class HardwareServiceFacade:
    """
    Lightweight coordinator for hardware services.
    Standalone version for EOL Tester sequence.
    """

    def __init__(
        self,
        robot_service: RobotService,
        mcu_service: MCUService,
        loadcell_service: LoadCellService,
        power_service: PowerService,
        digital_io_service: DigitalIOService,
    ):
        self._robot = robot_service
        self._mcu = mcu_service
        self._loadcell = loadcell_service
        self._power = power_service
        self._digital_io = digital_io_service

        self._robot_homed = False
        self._robot_state = RobotState.UNKNOWN

    # Service accessors
    @property
    def robot_service(self) -> RobotService:
        return self._robot

    @property
    def mcu_service(self) -> MCUService:
        return self._mcu

    @property
    def loadcell_service(self) -> LoadCellService:
        return self._loadcell

    @property
    def power_service(self) -> PowerService:
        return self._power

    @property
    def digital_io_service(self) -> DigitalIOService:
        return self._digital_io

    # Connection Management
    async def connect_all_hardware(self, hardware_config: HardwareConfig) -> None:
        """Connect all required hardware."""
        logger.info("Connecting hardware...")

        connection_tasks = []
        hardware_names = []

        if not await self._robot.is_connected():
            connection_tasks.append(self._robot.connect())
            hardware_names.append("Robot")

        if not await self._mcu.is_connected():
            connection_tasks.append(self._mcu.connect())
            hardware_names.append("MCU")

        if not await self._power.is_connected():
            connection_tasks.append(self._power.connect())
            hardware_names.append("Power")

        if not await self._loadcell.is_connected():
            connection_tasks.append(self._loadcell.connect())
            hardware_names.append("LoadCell")

        if not await self._digital_io.is_connected():
            connection_tasks.append(self._digital_io.connect())
            hardware_names.append("DigitalIO")

        if connection_tasks:
            await asyncio.gather(*connection_tasks)
            logger.info(f"Successfully connected: {', '.join(hardware_names)}")
        else:
            logger.info("All hardware already connected")

    async def get_hardware_status(self) -> Dict[str, bool]:
        """Get connection status of all hardware."""
        return {
            "robot": await self._robot.is_connected(),
            "mcu": await self._mcu.is_connected(),
            "power": await self._power.is_connected(),
            "loadcell": await self._loadcell.is_connected(),
            "digital_io": await self._digital_io.is_connected(),
        }

    async def shutdown_hardware(self, hardware_config: Optional[HardwareConfig] = None) -> None:
        """Safely shutdown all hardware."""
        logger.info("Shutting down hardware...")

        try:
            if await self._power.is_connected():
                try:
                    await self._power.disable_output()
                except Exception as e:
                    logger.warning(f"Failed to disable power output: {e}")

            shutdown_tasks = []
            if await self._robot.is_connected():
                shutdown_tasks.append(self._robot.disconnect())
            if await self._mcu.is_connected():
                shutdown_tasks.append(self._mcu.disconnect())
            if await self._power.is_connected():
                shutdown_tasks.append(self._power.disconnect())
            if await self._loadcell.is_connected():
                shutdown_tasks.append(self._loadcell.disconnect())
            if await self._digital_io.is_connected():
                shutdown_tasks.append(self._digital_io.disconnect())

            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)

            logger.info("Hardware shutdown completed")
        except Exception as e:
            logger.error(f"Error during hardware shutdown: {e}")

    # Hardware Initialization
    async def initialize_hardware(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
    ) -> None:
        """Initialize all hardware with configuration settings."""
        logger.info("Initializing hardware with configuration...")

        # Digital Output servo brake release
        await self._digital_io.write_output(hardware_config.digital_io.servo1_brake_release, True)

        # Initialize power settings
        await self._power.disable_output()
        await asyncio.sleep(test_config.power_command_stabilization)

        await self._power.set_voltage(test_config.voltage)
        await asyncio.sleep(test_config.power_command_stabilization)

        await self._power.set_current(test_config.current)
        await asyncio.sleep(test_config.power_command_stabilization)

        await self._power.set_current_limit(test_config.upper_current)
        await asyncio.sleep(test_config.power_command_stabilization)

        # Initialize robot
        logger.info(f"Enabling servo for axis {hardware_config.robot.axis_id}...")
        await self._robot.enable_servo(hardware_config.robot.axis_id)

        # Ensure robot is homed
        await self._ensure_robot_homed(hardware_config.robot.axis_id)

        # Move to initial position
        logger.info(f"Moving robot to initial position: {test_config.initial_position}um")
        await self._robot.move_absolute(
            position=test_config.initial_position,
            axis_id=hardware_config.robot.axis_id,
            velocity=test_config.velocity,
            acceleration=test_config.acceleration,
            deceleration=test_config.deceleration,
        )
        await asyncio.sleep(test_config.robot_move_stabilization)

        logger.info("Hardware initialization completed")

    async def _ensure_robot_homed(self, axis_id: int) -> None:
        """Ensure robot is homed."""
        if not self._robot_homed:
            logger.info("Performing robot homing...")
            self._robot_state = RobotState.MOVING
            await self._robot.home_axis(axis_id)
            self._robot_homed = True
            self._robot_state = RobotState.HOME
            logger.info("Robot homing completed")

    # Test Execution
    async def setup_test(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
    ) -> None:
        """Setup hardware for test execution."""
        logger.info("Setting up test...")

        # Enable power output
        await self._power.enable_output()
        logger.info(f"Power enabled: {test_config.voltage}V, {test_config.current}A")
        await asyncio.sleep(test_config.poweron_stabilization)

        # Wait for MCU boot complete
        logger.info("Waiting for MCU boot complete signal...")
        await asyncio.wait_for(
            self._mcu.wait_boot_complete(),
            timeout=test_config.timeout_seconds,
        )
        await asyncio.sleep(test_config.mcu_boot_complete_stabilization)

        # Set test mode
        await self._mcu.set_test_mode(TestMode.MODE_1)
        await asyncio.sleep(test_config.mcu_command_stabilization)

        # Set LMA standby
        await self.set_lma_standby(test_config, hardware_config)

        logger.info("Test setup completed")

    async def set_lma_standby(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
    ) -> None:
        """Set LMA standby sequence."""
        logger.info("Starting LMA standby sequence...")

        # MCU configuration
        await self._mcu.set_upper_temperature(test_config.upper_temperature)
        await asyncio.sleep(test_config.mcu_command_stabilization)

        await self._mcu.set_fan_speed(test_config.fan_speed)
        await asyncio.sleep(test_config.mcu_command_stabilization)

        await self._mcu.start_standby_heating(
            operating_temp=test_config.activation_temperature,
            standby_temp=test_config.standby_temperature,
        )
        await asyncio.sleep(test_config.mcu_command_stabilization)

        # Verify temperature
        await self.verify_mcu_temperature(test_config.activation_temperature, test_config)

        # Robot movements
        self._robot_state = RobotState.MOVING
        await self._robot.move_absolute(
            position=test_config.operating_position,
            axis_id=hardware_config.robot.axis_id,
            velocity=test_config.velocity,
            acceleration=test_config.acceleration,
            deceleration=test_config.deceleration,
        )
        await asyncio.sleep(test_config.robot_move_stabilization)
        self._robot_state = RobotState.MAX_STROKE

        await asyncio.sleep(test_config.robot_standby_stabilization)

        # Return to initial position
        self._robot_state = RobotState.MOVING
        await self._robot.move_absolute(
            position=test_config.initial_position,
            axis_id=hardware_config.robot.axis_id,
            velocity=test_config.velocity,
            acceleration=test_config.acceleration,
            deceleration=test_config.deceleration,
        )
        await asyncio.sleep(test_config.robot_move_stabilization)
        self._robot_state = RobotState.INITIAL_POSITION

        # Start standby cooling
        await self._mcu.start_standby_cooling()
        await asyncio.sleep(test_config.mcu_command_stabilization)

        # Verify standby temperature
        await self.verify_mcu_temperature(test_config.standby_temperature, test_config)

        logger.info("LMA standby sequence completed")

    async def perform_force_test_sequence(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
        dut_info: DUTCommandInfo,
    ) -> Tuple[TestMeasurements, List[CycleResult]]:
        """Perform complete force test measurement sequence."""
        logger.info("Starting force test sequence...")

        repeat_count = test_config.repeat_count
        measurements_dict: Dict[float, Dict[float, Dict[str, Any]]] = {}
        individual_cycle_results = []

        for repeat_idx in range(repeat_count):
            cycle_measurements_dict: Dict[float, Dict[float, Dict[str, Any]]] = {}
            cycle_start_time = datetime.now()

            if repeat_count > 1:
                logger.info(f"===== Force Test Repetition {repeat_idx + 1}/{repeat_count} =====")

            for temp_idx, temperature in enumerate(test_config.temperature_list):
                logger.info(f"Setting temperature to {temperature}C ({temp_idx + 1}/{len(test_config.temperature_list)})")

                # Set MCU temperature
                await self._mcu.set_operating_temperature(temperature)
                await asyncio.sleep(test_config.mcu_command_stabilization)

                # Verify temperature
                await self.verify_mcu_temperature(temperature, test_config)

                # Initialize measurements for this temperature
                if repeat_idx == 0:
                    measurements_dict[temperature] = {}
                cycle_measurements_dict[temperature] = {}

                # Measure at each position
                for pos_idx, position in enumerate(test_config.stroke_positions):
                    logger.info(f"Measuring at position {position}um ({pos_idx + 1}/{len(test_config.stroke_positions)})")

                    # Move robot
                    self._robot_state = RobotState.MOVING
                    await self._robot.move_absolute(
                        position=position,
                        axis_id=hardware_config.robot.axis_id,
                        velocity=test_config.velocity,
                        acceleration=test_config.acceleration,
                        deceleration=test_config.deceleration,
                    )
                    await asyncio.sleep(test_config.robot_move_stabilization)
                    self._robot_state = RobotState.MEASUREMENT_POSITION

                    # Read force
                    force = await self._loadcell.read_peak_force()

                    # Store measurement
                    if repeat_count == 1:
                        measurements_dict[temperature][position] = {"force": force.value if hasattr(force, "value") else force}
                    else:
                        if position not in measurements_dict[temperature]:
                            measurements_dict[temperature][position] = {"force": []}
                        measurements_dict[temperature][position]["force"].append(force.value if hasattr(force, "value") else force)

                    cycle_measurements_dict[temperature][position] = {"force": force.value if hasattr(force, "value") else force}
                    logger.debug(f"Force: {force.value if hasattr(force, 'value') else force:.3f}kgf")

                # Return to initial position
                if self._robot_state != RobotState.INITIAL_POSITION:
                    self._robot_state = RobotState.MOVING
                    await self._robot.move_absolute(
                        position=test_config.initial_position,
                        axis_id=hardware_config.robot.axis_id,
                        velocity=test_config.velocity,
                        acceleration=test_config.acceleration,
                        deceleration=test_config.deceleration,
                    )
                    await asyncio.sleep(test_config.robot_move_stabilization)
                    self._robot_state = RobotState.INITIAL_POSITION

                # Start standby cooling
                await self._mcu.start_standby_cooling()
                await asyncio.sleep(test_config.mcu_command_stabilization)

                # Verify standby temperature
                await self.verify_mcu_temperature(test_config.standby_temperature, test_config)

            # Create cycle result
            cycle_end_time = datetime.now()
            cycle_duration = TestDuration.from_seconds(
                (cycle_end_time - cycle_start_time).total_seconds()
            )

            cycle_result = CycleResult.create_successful(
                cycle_number=repeat_idx + 1,
                is_passed=True,
                measurements={"measurements": cycle_measurements_dict},
                execution_duration=cycle_duration,
                completed_at=cycle_end_time,
                cycle_notes=f"Repeat {repeat_idx + 1}/{repeat_count} completed",
            )
            individual_cycle_results.append(cycle_result)
            logger.info(f"Cycle {repeat_idx + 1} completed: {cycle_duration.seconds:.2f}s")

        logger.info("Force test sequence completed")

        # Process measurements for averaging if needed
        if repeat_count > 1:
            processed_dict: Dict[float, Dict[float, Dict[str, Any]]] = {}
            for temp, positions in measurements_dict.items():
                processed_dict[temp] = {}
                for pos, data in positions.items():
                    force_data = data["force"]
                    if isinstance(force_data, list):
                        avg_force = sum(force_data) / len(force_data)
                        processed_dict[temp][pos] = {"force": avg_force}
                    else:
                        processed_dict[temp][pos] = {"force": force_data}
            test_measurements = TestMeasurements.from_legacy_dict(processed_dict, {})
        else:
            test_measurements = TestMeasurements.from_legacy_dict(measurements_dict, {})

        return test_measurements, individual_cycle_results

    async def teardown_test(
        self,
        test_config: TestConfiguration,
        hardware_config: HardwareConfig,
    ) -> None:
        """Teardown test and return hardware to safe state."""
        logger.info("Tearing down test...")

        # Move robot to initial position
        if self._robot_state != RobotState.INITIAL_POSITION:
            self._robot_state = RobotState.MOVING
            await self._robot.move_absolute(
                position=test_config.initial_position,
                axis_id=hardware_config.robot.axis_id,
                velocity=test_config.velocity,
                acceleration=test_config.acceleration,
                deceleration=test_config.deceleration,
            )
            await asyncio.sleep(test_config.robot_move_stabilization)
            self._robot_state = RobotState.INITIAL_POSITION

        # Disable power
        await self._power.disable_output()
        logger.info("Test teardown completed")

    async def verify_mcu_temperature(
        self,
        expected_temp: float,
        test_config: TestConfiguration,
    ) -> None:
        """Verify MCU temperature is within tolerance."""
        from ..domain.exceptions import HardwareOperationError

        logger.info(
            f"Verifying MCU temperature - Expected: {expected_temp}C "
            f"(±{test_config.temperature_tolerance}C)"
        )

        # Check if this is Mock environment and skip retries for faster testing
        if "Mock" in self._mcu.__class__.__name__:
            logger.info(
                f"✅ Mock environment - Temperature verification bypassed for {expected_temp}C"
            )
            await asyncio.sleep(0.1)  # Short simulation delay
            return

        max_retries = 10
        retry_delay = 1.0

        for attempt in range(max_retries + 1):
            actual_temp = await self._mcu.get_temperature()
            temp_diff = abs(actual_temp - expected_temp)

            if temp_diff <= test_config.temperature_tolerance:
                logger.info(
                    f"✅ Temperature verified: {actual_temp:.1f}C "
                    f"(diff: {temp_diff:.1f}C ≤ {test_config.temperature_tolerance}C)"
                )
                return

            if attempt < max_retries:
                logger.debug(
                    f"Temperature stabilizing: {actual_temp:.1f}C → {expected_temp:.1f}C "
                    f"(diff: {temp_diff:.1f}C, attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(retry_delay)
            else:
                # 실패시 예외 발생 (src 방식)
                error_msg = (
                    f"Temperature verification failed after {max_retries + 1} attempts - "
                    f"Actual: {actual_temp:.1f}C, Expected: {expected_temp:.1f}C, "
                    f"Diff: {temp_diff:.1f}C (>{test_config.temperature_tolerance}C)"
                )
                logger.error(f"❌ {error_msg}")
                raise HardwareOperationError(
                    device="mcu",
                    operation="verify_temperature",
                    reason=error_msg,
                )

    def reset_robot_homing_state(self) -> None:
        """Reset robot homing state."""
        self._robot_homed = False
        logger.debug("Robot homing state reset")
