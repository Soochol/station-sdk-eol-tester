"""
Industrial System Manager for standalone EOL Tester sequence.
Simplified coordinator for tower lamp control and status management.
"""

from typing import Optional, TYPE_CHECKING

from loguru import logger

from .tower_lamp_service import SystemStatus, TowerLampService

if TYPE_CHECKING:
    from ..interfaces import DigitalIOService
    from ..domain.value_objects import HardwareConfig


class IndustrialSystemManager:
    """
    Simplified Industrial System Manager for sequences.
    Coordinates tower lamp status and system state management.
    """

    def __init__(
        self,
        digital_io_service: "DigitalIOService",
        hardware_config: "HardwareConfig",
    ):
        """
        Initialize Industrial System Manager.

        Args:
            digital_io_service: Digital I/O service for lamp control
            hardware_config: Hardware configuration
        """
        self._digital_io = digital_io_service
        self._hardware_config = hardware_config
        self._tower_lamp: Optional[TowerLampService] = None
        self._current_status: Optional[SystemStatus] = None
        self._initialized = False

        logger.info("IndustrialSystemManager initialized")

    async def initialize_system(self) -> None:
        """Initialize industrial system to idle state."""
        logger.info("Initializing Industrial System...")

        try:
            # Connect Digital I/O if not connected
            if not await self._digital_io.is_connected():
                logger.info("Connecting Digital I/O for tower lamp control...")
                await self._digital_io.connect()

            # Initialize tower lamp service
            self._tower_lamp = TowerLampService(
                digital_io_service=self._digital_io,
                hardware_config=self._hardware_config,
            )

            # Set to idle state - Green ON
            await self.set_system_status(SystemStatus.SYSTEM_IDLE)
            self._initialized = True

            logger.info("Industrial System initialization complete - Green ON")

        except Exception as e:
            logger.error(f"Failed to initialize Industrial System: {e}")
            raise

    async def set_system_status(self, status: SystemStatus) -> None:
        """
        Set system status with tower lamp indication.

        Args:
            status: System status to set
        """
        logger.info(f"Setting system status to {status.value}")
        self._current_status = status

        if self._tower_lamp:
            await self._tower_lamp.set_system_status(status)
        else:
            logger.warning("Tower lamp service not initialized")

    async def handle_test_completion(
        self, test_success: bool, test_error: bool = False
    ) -> None:
        """
        Handle test completion with appropriate status indication.

        Args:
            test_success: Whether test completed successfully
            test_error: Whether test completed with error
        """
        if test_error:
            logger.error("Test completed with error - Red BLINK")
            await self.set_system_status(SystemStatus.SYSTEM_ERROR)
        elif test_success:
            logger.info("Test completed successfully (PASS) - Green BLINK")
            await self.set_system_status(SystemStatus.TEST_PASS)
        else:
            logger.warning("Test completed with failure (FAIL) - Yellow BLINK")
            await self.set_system_status(SystemStatus.TEST_FAIL)

    async def handle_emergency_stop(self) -> None:
        """Handle emergency stop activation."""
        logger.critical("Emergency stop activated!")
        await self.set_system_status(SystemStatus.EMERGENCY_STOP)

    async def clear_error(self) -> None:
        """Clear error state and return to idle."""
        logger.info("Clearing error state")
        await self.set_system_status(SystemStatus.SYSTEM_IDLE)

    async def get_system_status(self) -> Optional[SystemStatus]:
        """Get current system status."""
        return self._current_status

    async def shutdown_system(self) -> None:
        """Shutdown industrial system safely."""
        logger.info("Shutting down Industrial System...")

        if self._tower_lamp:
            await self._tower_lamp.shutdown()

        self._current_status = None
        self._initialized = False

        logger.info("Industrial System shutdown complete")
