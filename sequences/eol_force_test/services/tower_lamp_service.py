"""
Tower Lamp Service for standalone EOL Tester sequence.
Simplified version for status indication via Digital I/O.
"""

import asyncio
from enum import Enum
from typing import Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..interfaces import DigitalIOService
    from ..domain.value_objects import HardwareConfig


class LampState(Enum):
    """Tower lamp states"""
    OFF = "off"
    ON = "on"
    BLINKING_SLOW = "blinking_slow"  # 2s cycle
    BLINKING_FAST = "blinking_fast"  # 0.5s cycle


class SystemStatus(Enum):
    """System status indicators"""
    SYSTEM_IDLE = "system_idle"          # Green ON
    SYSTEM_RUNNING = "system_running"    # Green ON
    TEST_PASS = "test_pass"              # Green BLINK
    TEST_FAIL = "test_fail"              # Yellow BLINK + Green ON
    SYSTEM_ERROR = "system_error"        # Red BLINK + Green ON
    EMERGENCY_STOP = "emergency_stop"    # Red BLINK + Green ON + Beep


class TowerLampService:
    """
    Simplified Tower Lamp Control Service for sequences.
    Controls Red/Yellow/Green lamps and beep for status indication.
    """

    def __init__(
        self,
        digital_io_service: "DigitalIOService",
        hardware_config: "HardwareConfig",
    ):
        """
        Initialize Tower Lamp Service.

        Args:
            digital_io_service: Digital I/O service for lamp control
            hardware_config: Hardware configuration with lamp channel assignments
        """
        self.digital_io = digital_io_service
        self.hardware_config = hardware_config

        # Get lamp channel assignments
        self.red_lamp_channel = hardware_config.digital_io.tower_lamp_red
        self.yellow_lamp_channel = hardware_config.digital_io.tower_lamp_yellow
        self.green_lamp_channel = hardware_config.digital_io.tower_lamp_green
        self.beep_channel = hardware_config.digital_io.beep

        # State tracking
        self._current_status: Optional[SystemStatus] = None
        self._blinking_task: Optional[asyncio.Task] = None

        logger.info(
            f"TowerLampService initialized - "
            f"Red: Ch{self.red_lamp_channel}, Yellow: Ch{self.yellow_lamp_channel}, "
            f"Green: Ch{self.green_lamp_channel}, Beep: Ch{self.beep_channel}"
        )

    async def set_system_status(self, status: SystemStatus) -> None:
        """Set system status with appropriate lamp pattern."""
        logger.info(f"Setting system status to {status.value}")

        # Stop current blinking if any
        await self._stop_blinking()
        self._current_status = status

        if status == SystemStatus.SYSTEM_IDLE:
            await self._set_system_idle()
        elif status == SystemStatus.SYSTEM_RUNNING:
            await self._set_system_running()
        elif status == SystemStatus.TEST_PASS:
            await self._set_test_pass()
        elif status == SystemStatus.TEST_FAIL:
            await self._set_test_fail()
        elif status == SystemStatus.SYSTEM_ERROR:
            await self._set_system_error()
        elif status == SystemStatus.EMERGENCY_STOP:
            await self._set_emergency_stop()

    async def _set_system_idle(self) -> None:
        """Green ON - System ready"""
        logger.info("System idle - Green lamp ON")
        await self._set_lamps(red=False, yellow=False, green=True)
        await self._set_beep(False)

    async def _set_system_running(self) -> None:
        """Green ON - Test running"""
        logger.info("System running - Green lamp ON")
        await self._set_lamps(red=False, yellow=False, green=True)
        await self._set_beep(False)

    async def _set_test_pass(self) -> None:
        """Green BLINK - Test passed"""
        logger.info("Test PASS - Green lamp BLINKING + Beep 1s")
        await self._set_lamps(red=False, yellow=False, green=False)
        self._blinking_task = asyncio.create_task(
            self._blink_lamp(self.green_lamp_channel, 2.0)
        )
        # Beep for 1 second
        await self._set_beep(True)
        await asyncio.sleep(1.0)
        await self._set_beep(False)

    async def _set_test_fail(self) -> None:
        """Yellow BLINK + Green ON - Test failed"""
        logger.info("Test FAIL - Yellow lamp BLINKING + Green ON + Beep 1s")
        await self._set_lamps(red=False, yellow=False, green=True)
        self._blinking_task = asyncio.create_task(
            self._blink_lamp(self.yellow_lamp_channel, 2.0)
        )
        # Beep for 1 second
        await self._set_beep(True)
        await asyncio.sleep(1.0)
        await self._set_beep(False)

    async def _set_system_error(self) -> None:
        """Red BLINK + Green ON - System error"""
        logger.error("System error - Red lamp BLINKING + Green ON")
        await self._set_lamps(red=False, yellow=False, green=True)
        self._blinking_task = asyncio.create_task(
            self._blink_lamp(self.red_lamp_channel, 2.0)
        )
        await self._set_beep(False)

    async def _set_emergency_stop(self) -> None:
        """Red BLINK + Green ON + Beep - Emergency stop"""
        logger.critical("Emergency stop - Red lamp BLINKING + Green ON + Beep")
        await self._set_lamps(red=False, yellow=False, green=True)
        self._blinking_task = asyncio.create_task(
            self._blink_lamp(self.red_lamp_channel, 2.0)
        )
        await self._set_beep(True)

    async def _set_lamps(self, red: bool, yellow: bool, green: bool) -> None:
        """Set lamp states directly."""
        try:
            if await self.digital_io.is_connected():
                await self.digital_io.write_output(self.red_lamp_channel, red)
                await self.digital_io.write_output(self.yellow_lamp_channel, yellow)
                await self.digital_io.write_output(self.green_lamp_channel, green)
            else:
                logger.warning("Digital I/O not connected - lamp control skipped")
        except Exception as e:
            logger.error(f"Failed to set lamp states: {e}")

    async def _set_beep(self, on: bool) -> None:
        """Set beep state."""
        try:
            if await self.digital_io.is_connected():
                await self.digital_io.write_output(self.beep_channel, on)
        except Exception as e:
            logger.error(f"Failed to set beep: {e}")

    async def _blink_lamp(self, channel: int, interval: float) -> None:
        """Blink a lamp at specified interval."""
        try:
            while True:
                await self.digital_io.write_output(channel, True)
                await asyncio.sleep(interval / 2)
                await self.digital_io.write_output(channel, False)
                await asyncio.sleep(interval / 2)
        except asyncio.CancelledError:
            # Ensure lamp is off when cancelled (except green)
            if channel != self.green_lamp_channel:
                try:
                    await self.digital_io.write_output(channel, False)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error in blink_lamp: {e}")

    async def _stop_blinking(self) -> None:
        """Stop any active blinking task."""
        if self._blinking_task and not self._blinking_task.done():
            self._blinking_task.cancel()
            try:
                await self._blinking_task
            except asyncio.CancelledError:
                pass
            self._blinking_task = None

    async def get_current_status(self) -> Optional[SystemStatus]:
        """Get current system status."""
        return self._current_status

    async def turn_off_all(self) -> None:
        """Turn off all lamps and beep."""
        logger.info("Turning off all lamps")
        await self._stop_blinking()
        await self._set_lamps(red=False, yellow=False, green=False)
        await self._set_beep(False)
        self._current_status = None

    async def shutdown(self) -> None:
        """Shutdown the tower lamp service."""
        logger.info("Shutting down Tower Lamp Service")
        await self.turn_off_all()
