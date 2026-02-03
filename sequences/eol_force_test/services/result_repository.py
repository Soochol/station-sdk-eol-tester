"""Result repository for saving test results to files.

This module provides CSV and JSON file storage for test results,
matching the functionality of src/application/services/core/repository_service.py
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


class ResultRepository:
    """Handles saving test results to CSV and JSON files."""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the result repository.

        Args:
            base_dir: Base directory for results. Defaults to sequences/eol_force_test/results/
        """
        self._base_dir = base_dir or Path(__file__).parent.parent / "results"
        self._raw_data_dir = self._base_dir / "raw_data"
        self._cycle_data_dir = self._base_dir / "cycle_data"
        self._summary_file = self._base_dir / "test_summary.csv"

        # Session tracking for cycle files
        self._cycle_session_timestamp: Optional[str] = None

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create result directories if they don't exist."""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._raw_data_dir.mkdir(parents=True, exist_ok=True)
        self._cycle_data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        """Return the base directory path."""
        return self._base_dir

    def save_raw_measurements(
        self,
        test_id: str,
        serial_number: str,
        measurements: Dict[float, Dict[float, Dict[str, float]]],
        passed: bool,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """
        Save raw measurements to CSV (pivot table format).

        Format: Test_ID, Serial, Date, Time, Status, T38_P170, T52_P170, ...

        Args:
            test_id: Unique test identifier
            serial_number: DUT serial number
            measurements: Dict[temperature][position][force]
            passed: Test pass/fail status
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Path to the created/updated CSV file
        """
        ts = timestamp or datetime.now()
        filename = f"raw_measurements_{ts.strftime('%Y%m%d_%H%M%S')}.csv"
        csv_path = self._raw_data_dir / filename

        # Build header and data row
        header = ["Test_ID", "Serial", "Date", "Time", "Status"]
        data_row = [
            test_id,
            serial_number,
            ts.strftime("%Y-%m-%d"),
            ts.strftime("%H:%M:%S"),
            "PASS" if passed else "FAIL",
        ]

        # Add temperature/position columns (sorted)
        for temp in sorted(measurements.keys()):
            for pos in sorted(measurements[temp].keys()):
                col_name = f"T{int(temp)}_P{int(pos/1000)}"  # Convert um to mm
                header.append(col_name)
                force = measurements[temp][pos].get("force", 0.0)
                data_row.append(f"{force:.3f}")

        # Write CSV
        file_exists = csv_path.exists()
        mode = "a" if file_exists else "w"
        with open(csv_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(data_row)

        logger.info(f"Saved raw measurements to: {csv_path}")
        return csv_path

    def save_cycle_measurements(
        self,
        test_id: str,
        serial_number: str,
        cycle_num: int,
        total_cycles: int,
        measurements: Dict[float, Dict[float, Dict[str, float]]],
        passed: bool,
        heating_time: float = 0.0,
        cooling_time: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """
        Save cycle-by-cycle measurements to CSV.

        Format: Cycle, Test_ID, Serial, Date, Time, Status, T##_P###..., Heating_Time_s, Cooling_Time_s

        Args:
            test_id: Unique test identifier
            serial_number: DUT serial number
            cycle_num: Current cycle number (1-based)
            total_cycles: Total number of cycles
            measurements: Dict[temperature][position][force]
            passed: Cycle pass/fail status
            heating_time: Average heating time in seconds
            cooling_time: Average cooling time in seconds
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Path to the created/updated CSV file
        """
        ts = timestamp or datetime.now()

        # Create session timestamp on first cycle
        if cycle_num == 1:
            self._cycle_session_timestamp = ts.strftime("%Y%m%d_%H%M%S")

        filename = f"cycle_measurements_{self._cycle_session_timestamp}_total{total_cycles}cycles.csv"
        csv_path = self._cycle_data_dir / filename

        # Build header and data row
        header = ["Cycle", "Test_ID", "Serial", "Date", "Time", "Status"]
        data_row = [
            cycle_num,
            test_id,
            serial_number,
            ts.strftime("%Y-%m-%d"),
            ts.strftime("%H:%M:%S"),
            "PASS" if passed else "FAIL",
        ]

        # Add measurement columns
        for temp in sorted(measurements.keys()):
            for pos in sorted(measurements[temp].keys()):
                col_name = f"T{int(temp)}_P{int(pos/1000)}"
                header.append(col_name)
                force = measurements[temp][pos].get("force", 0.0)
                data_row.append(f"{force:.2f}")

        # Add timing columns
        header.extend(["Heating_Time_s", "Cooling_Time_s"])
        data_row.extend([f"{heating_time:.2f}", f"{cooling_time:.2f}"])

        # Write CSV
        file_exists = csv_path.exists()
        mode = "a" if file_exists else "w"
        with open(csv_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(data_row)

        logger.info(f"Saved cycle {cycle_num}/{total_cycles} to: {csv_path}")
        return csv_path

    def update_test_summary(
        self,
        test_id: str,
        serial_number: str,
        passed: bool,
        duration_seconds: float,
        operator_id: str = "operator",
        cycle_num: Optional[int] = None,
        total_cycles: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """
        Append test result to summary CSV.

        Format: Test_ID, Serial_Number, Test_Date, Test_Time, Status, Duration_sec, Operator_ID, Cycle, Total_Cycles

        Args:
            test_id: Unique test identifier
            serial_number: DUT serial number
            passed: Test pass/fail status
            duration_seconds: Test duration in seconds
            operator_id: Operator identifier
            cycle_num: Optional cycle number
            total_cycles: Optional total cycles
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Path to the summary CSV file
        """
        ts = timestamp or datetime.now()

        header = [
            "Test_ID",
            "Serial_Number",
            "Test_Date",
            "Test_Time",
            "Status",
            "Duration_sec",
            "Operator_ID",
            "Cycle",
            "Total_Cycles",
        ]
        data_row = [
            test_id,
            serial_number,
            ts.strftime("%Y-%m-%d"),
            ts.strftime("%H:%M:%S"),
            "PASS" if passed else "FAIL",
            f"{duration_seconds:.2f}",
            operator_id,
            cycle_num or 1,
            total_cycles or 1,
        ]

        file_exists = self._summary_file.exists()
        mode = "a" if file_exists else "w"
        with open(self._summary_file, mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(data_row)

        logger.info(f"Updated test summary: {self._summary_file}")
        return self._summary_file

    def save_test_json(
        self,
        test_id: str,
        serial_number: str,
        measurements: Dict[float, Dict[float, Dict[str, float]]],
        passed: bool,
        config: Dict[str, Any],
        duration_seconds: float,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """
        Save complete test data to JSON file.

        Args:
            test_id: Unique test identifier
            serial_number: DUT serial number
            measurements: Dict[temperature][position][force]
            passed: Test pass/fail status
            config: Test configuration dictionary
            duration_seconds: Test duration in seconds
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Path to the created JSON file
        """
        ts = timestamp or datetime.now()

        json_path = self._base_dir / f"{test_id}.json"

        # Convert float keys to strings for JSON serialization
        serializable_measurements = {}
        for temp, positions in measurements.items():
            temp_key = str(temp)
            serializable_measurements[temp_key] = {}
            for pos, m in positions.items():
                pos_key = str(pos)
                serializable_measurements[temp_key][pos_key] = m

        data = {
            "test_id": test_id,
            "serial_number": serial_number,
            "status": "PASS" if passed else "FAIL",
            "created_at": ts.isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "measurements": serializable_measurements,
            "configuration": config,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved test JSON to: {json_path}")
        return json_path
