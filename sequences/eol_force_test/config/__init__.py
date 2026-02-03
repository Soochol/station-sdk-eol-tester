"""
Configuration loader for EOL Tester sequence.
Loads hardware configuration from local config file for self-contained operation.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Config directory path (relative to this file)
CONFIG_DIR = Path(__file__).parent
HARDWARE_CONFIG_FILE = CONFIG_DIR / "hardware_config.yaml"
APPLICATION_CONFIG_FILE = CONFIG_DIR / "application.yaml"
DUT_DEFAULTS_FILE = CONFIG_DIR / "dut_defaults.yaml"
PROFILE_FILE = CONFIG_DIR / "profile.yaml"
TEST_PROFILES_DIR = CONFIG_DIR / "test_profiles"
ROBOT_MOTION_FILE = CONFIG_DIR / "robot_motion_settings.mot"


def load_hardware_config_dict() -> Dict[str, Any]:
    """
    Load hardware configuration from local YAML file.
    Auto-generates default config if it doesn't exist.

    Returns:
        Dictionary with hardware configuration
    """
    # Ensure directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not HARDWARE_CONFIG_FILE.exists():
        # Auto-generate default hardware config
        from datetime import datetime
        from ..domain.value_objects import HardwareConfig

        logger.info(f"Hardware config not found, creating default: {HARDWARE_CONFIG_FILE}")

        default_config = HardwareConfig()
        config_data = default_config.to_dict()

        # Add metadata
        config_data["metadata"] = {
            "created_at": datetime.now().isoformat(),
            "note": "Auto-generated default hardware configuration",
            "created_by": "sequences config loader (auto-generated)",
        }

        # Save to file
        with open(HARDWARE_CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Created default hardware config: {HARDWARE_CONFIG_FILE}")

    # Load and return
    try:
        with open(HARDWARE_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded hardware config from: {HARDWARE_CONFIG_FILE}")
        return config
    except Exception as e:
        logger.error(f"Failed to load hardware config: {e}")
        return {}


def load_hardware_config() -> "HardwareConfig":
    """
    Load hardware configuration as HardwareConfig object.

    Returns:
        HardwareConfig instance with loaded values
    """
    from ..domain.value_objects import HardwareConfig

    config_dict = load_hardware_config_dict()
    if config_dict:
        # Resolve motion_param_file to absolute path if it exists
        config_dict = _resolve_motion_param_file_path(config_dict)
        return HardwareConfig.from_dict(config_dict)
    return HardwareConfig()  # Default mock config


def _resolve_motion_param_file_path(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve motion_param_file relative path to absolute path.

    Args:
        config_dict: Hardware configuration dictionary

    Returns:
        Updated configuration dictionary with absolute motion_param_file path
    """
    if "robot" in config_dict and isinstance(config_dict["robot"], dict):
        motion_file = config_dict["robot"].get("motion_param_file")
        if motion_file:
            motion_path = Path(motion_file)
            # If relative path, resolve relative to config directory
            if not motion_path.is_absolute():
                # First try relative to config directory
                config_relative = CONFIG_DIR / motion_path.name
                if config_relative.exists():
                    config_dict["robot"]["motion_param_file"] = str(config_relative.resolve())
                    logger.info(f"Resolved motion_param_file to: {config_relative.resolve()}")
                else:
                    # Try as-is (might be relative to CWD)
                    if motion_path.exists():
                        config_dict["robot"]["motion_param_file"] = str(motion_path.resolve())
                        logger.info(f"Resolved motion_param_file to: {motion_path.resolve()}")
                    else:
                        logger.warning(f"motion_param_file not found: {motion_file}")
    return config_dict


def save_hardware_config(config: "HardwareConfig") -> bool:
    """
    Save hardware configuration to local YAML file.

    Args:
        config: HardwareConfig instance to save

    Returns:
        True if saved successfully
    """
    try:
        config_dict = config.to_dict()
        with open(HARDWARE_CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"Saved hardware config to: {HARDWARE_CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save hardware config: {e}")
        return False


def get_config_path() -> Path:
    """Return the path to the hardware config file."""
    return HARDWARE_CONFIG_FILE


def load_application_config() -> Dict[str, Any]:
    """
    Load application configuration from YAML file.

    Returns:
        Dictionary with application configuration
    """
    if not APPLICATION_CONFIG_FILE.exists():
        logger.warning(f"Application config not found: {APPLICATION_CONFIG_FILE}")
        return {}

    try:
        with open(APPLICATION_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded application config from: {APPLICATION_CONFIG_FILE}")
        return config
    except Exception as e:
        logger.error(f"Failed to load application config: {e}")
        return {}


def load_dut_defaults() -> Dict[str, Any]:
    """
    Load DUT defaults configuration from YAML file.

    Returns:
        Dictionary with DUT defaults
    """
    if not DUT_DEFAULTS_FILE.exists():
        logger.warning(f"DUT defaults not found: {DUT_DEFAULTS_FILE}")
        return {}

    try:
        with open(DUT_DEFAULTS_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded DUT defaults from: {DUT_DEFAULTS_FILE}")
        return config
    except Exception as e:
        logger.error(f"Failed to load DUT defaults: {e}")
        return {}


def load_profile() -> Dict[str, Any]:
    """
    Load profile configuration from YAML file.

    Returns:
        Dictionary with profile configuration
    """
    if not PROFILE_FILE.exists():
        logger.warning(f"Profile config not found: {PROFILE_FILE}")
        return {}

    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded profile config from: {PROFILE_FILE}")
        return config
    except Exception as e:
        logger.error(f"Failed to load profile config: {e}")
        return {}


def load_test_profile(profile_name: str = "default") -> Dict[str, Any]:
    """
    Load a specific test profile from the test_profiles directory.
    Auto-generates default profile if it doesn't exist.

    Args:
        profile_name: Name of the profile file (without .yaml extension)

    Returns:
        Dictionary with test profile configuration
    """
    # Ensure directory exists
    TEST_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    profile_file = TEST_PROFILES_DIR / f"{profile_name}.yaml"

    if not profile_file.exists():
        # Auto-generate default profile
        from datetime import datetime
        from ..domain.value_objects import TestConfiguration

        logger.info(f"Test profile not found, creating default: {profile_file}")

        default_config = TestConfiguration()
        config_data = default_config.to_structured_dict()

        # Add metadata
        config_data["metadata"] = {
            "profile_name": profile_name,
            "created_at": datetime.now().isoformat(),
            "note": f"Auto-generated default test profile '{profile_name}'",
            "created_by": "sequences config loader (auto-generated)",
        }

        # Save to file
        with open(profile_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Created default test profile: {profile_file}")

    # Load and return
    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded test profile from: {profile_file}")
        return config
    except Exception as e:
        logger.error(f"Failed to load test profile: {e}")
        return {}


def list_test_profiles() -> List[str]:
    """
    List available test profiles.

    Returns:
        List of profile names (without .yaml extension)
    """
    if not TEST_PROFILES_DIR.exists():
        return []

    profiles = []
    for file in TEST_PROFILES_DIR.glob("*.yaml"):
        profiles.append(file.stem)
    return sorted(profiles)


def get_robot_motion_file_path() -> Optional[Path]:
    """
    Get the path to the robot motion settings file.

    Returns:
        Path to the motion file if it exists, None otherwise
    """
    if ROBOT_MOTION_FILE.exists():
        return ROBOT_MOTION_FILE
    return None


def get_config_dir() -> Path:
    """Return the config directory path."""
    return CONFIG_DIR
