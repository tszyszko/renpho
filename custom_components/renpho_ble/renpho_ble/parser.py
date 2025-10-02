"""Parser for Renpho BLE active communication.

"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorLibrary, Units
_LOGGER = logging.getLogger(__name__)

class RenphoBluetoothDeviceData(BluetoothData):
    """Data for Renpho BLE sensors using active communication."""

    def __init__(self) -> None:
        """Initialize the device data."""
        super().__init__()
        self._latest_measurement: Optional[Dict[str, Any]] = None
        self._device_configured = False

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data - used for device discovery."""
        _LOGGER.debug("Parsing Renpho BLE service_info data: %s", service_info)
        manufacturer_data = service_info.manufacturer_data
        address = service_info.address
        _LOGGER.debug("Renpho Address: " + str(address))

        # Check if this is a Renpho device by manufacturer ID
        for mfr_id, mfr_data in manufacturer_data.items():
            if mfr_id == 65535:
                _LOGGER.debug("Found Renpho device with manufacturer ID 65535")
                self.set_device_manufacturer("Renpho")
                self.set_device_name("Renpho Scale " + str(address))
                self.set_device_type("Renpho BLE Scale")
                self.set_precision(2)
                self._device_configured = True
                break

    def update_measurement(self, measurement_data: Dict[str, Any]) -> None:
        """Update with new measurement data from active BLE communication."""
        _LOGGER.debug("Updating measurement data: %s", measurement_data)
        self._latest_measurement = measurement_data

        if not self._device_configured:
            self.set_device_manufacturer("Renpho")
            self.set_device_name("Renpho Scale")
            self.set_device_type("Renpho BLE Scale")
            self.set_precision(2)
            self._device_configured = True

        # Update weight
        weight = measurement_data.get("weight", 0.0)
        if weight > 0:
            self.update_predefined_sensor(SensorLibrary.MASS__MASS_KILOGRAMS, weight)
            _LOGGER.debug("Updated weight: %.2f kg", weight)

        # Update body composition data if available
        self._update_body_composition(measurement_data)

    def _update_body_composition(self, measurement_data: Dict[str, Any]) -> None:
        """Update body composition sensors based on measurement data."""
        impedance = measurement_data.get("impedance", 0.0)
        weight = measurement_data.get("weight", 0.0)

        if impedance > 0 and weight > 0:
            # Calculate body composition using the impedance
            # These are simplified calculations - in practice you might want to use
            # more sophisticated formulas based on age, gender, height, etc.

            # Body fat percentage (simplified calculation)
            body_fat = self._calculate_body_fat(weight, impedance)
            if body_fat > 0:
                self.update_sensor("body_fat", Units.PERCENTAGE, body_fat)

            # Body water percentage
            body_water = self._calculate_body_water(weight, impedance)
            if body_water > 0:
                self.update_sensor("body_water", Units.PERCENTAGE, body_water)

            # Muscle mass
            muscle_mass = self._calculate_muscle_mass(weight, impedance)
            if muscle_mass > 0:
                self.update_sensor("muscle_mass", Units.MASS_KILOGRAMS, muscle_mass)

            # Bone mass
            bone_mass = self._calculate_bone_mass(weight, impedance)
            if bone_mass > 0:
                self.update_sensor("bone_mass", Units.MASS_KILOGRAMS, bone_mass)

    def _calculate_body_fat(self, weight: float, impedance: float) -> float:
        """Calculate body fat percentage."""
        # Simplified calculation - in practice, use proper formulas
        # based on age, gender, height, etc.
        if impedance < 300:
            return 5.0 + (impedance / 100.0)
        elif impedance < 500:
            return 10.0 + ((impedance - 300) / 50.0)
        else:
            return 15.0 + ((impedance - 500) / 100.0)

    def _calculate_body_water(self, weight: float, impedance: float) -> float:
        """Calculate body water percentage."""
        # Simplified calculation
        if impedance < 300:
            return 70.0 - (impedance / 200.0)
        elif impedance < 500:
            return 65.0 - ((impedance - 300) / 100.0)
        else:
            return 60.0 - ((impedance - 500) / 200.0)

    def _calculate_muscle_mass(self, weight: float, impedance: float) -> float:
        """Calculate muscle mass."""
        # Simplified calculation
        body_fat = self._calculate_body_fat(weight, impedance)
        fat_mass = weight * (body_fat / 100.0)
        return weight - fat_mass - 2.0  # Subtract estimated bone mass

    def _calculate_bone_mass(self, weight: float, impedance: float) -> float:
        """Calculate bone mass."""
        # Simplified calculation - typically 2-4% of body weight
        return weight * 0.03

    @property
    def latest_measurement(self) -> Optional[Dict[str, Any]]:
        """Get the latest measurement data."""
        return self._latest_measurement