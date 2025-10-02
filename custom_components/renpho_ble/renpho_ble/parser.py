"""Parser for Renpho BLE advertisements.

"""
from __future__ import annotations

import logging
import struct

from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorLibrary
_LOGGER = logging.getLogger(__name__)

class RenphoBluetoothDeviceData(BluetoothData):
    """Data for Renpho BLE sensors."""

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing Renpho BLE service_info data: %s", service_info)
        manufacturer_data = service_info.manufacturer_data
        _LOGGER.debug("Parsing Renpho BLE manufacturer_data data: %s", manufacturer_data)
        address = service_info.address
        _LOGGER.debug("Renpho Address: " + str(address))


        for mfr_id, mfr_data in manufacturer_data.items():
            _LOGGER.debug("mfr_id: " + str(mfr_id))
            _LOGGER.debug("mfr_data: " + str(mfr_data))
            if mfr_id == 65535:
                _LOGGER.debug("Parsing Renpho BLE mfr data: %s", str(mfr_data))

                # Parse weight from bytes 17-18 (little endian, divide by 100)
                if len(mfr_data) >= 19:
                    subbytes = mfr_data[17:19]
                    weight = int.from_bytes(subbytes, "little") / 100
                    _LOGGER.debug("weight: " + str(weight))

                    if weight > 0:
                        self.set_device_manufacturer("Renpho")
                        self.set_device_name("Scale " + str(address))
                        self.set_device_type("Renpho BLE ES-CS20M-W(V1)")
                        self.set_precision(2)
                        self.update_predefined_sensor(SensorLibrary.MASS__MASS_KILOGRAMS, weight)

                        # Parse body composition data if available (bytes 0-18)
                        if len(mfr_data) >= 19:
                            self._parse_body_composition(mfr_data)

    def _parse_body_composition(self, mfr_data: bytes) -> None:
        """Parse body composition data from manufacturer data."""
        _LOGGER.debug("Parsing body composition data: %s", [hex(b) for b in mfr_data])

        # Based on the Java code analysis:
        # byte 0: Unknown (always zero?)
        # bytes 1-3: Unknown
        # byte 4: Unknown (always zero?)
        # byte 5: "metabolic_age" in years
        # byte 6: Unknown (always zero?)
        # byte 7: "protein" in units of 0.1%
        # bytes 8-9: "subcutaneous_fat" in units of 0.1%
        # byte 10: "visceral_fat_grade" in unknown/absolute units
        # byte 11: Unknown (always zero?)
        # byte 12: int part of "lean_body_mass" in kg
        # bytes 13-16: Unknown (some flags/counters?)
        # bytes 17-18: "body_water" in units of 0.1%

        try:
            # Metabolic age (byte 5)
            if len(mfr_data) > 5 and mfr_data[5] != 0:
                metabolic_age = mfr_data[5]
                _LOGGER.debug("Metabolic age: %d years", metabolic_age)
                self.update_sensor("metabolic_age", "years", metabolic_age)

            # Protein percentage (byte 7, units of 0.1%)
            if len(mfr_data) > 7 and mfr_data[7] != 0:
                protein = mfr_data[7] / 10.0  # Convert from 0.1% to %
                _LOGGER.debug("Protein: %.1f%%", protein)
                self.update_sensor("protein", Units.PERCENTAGE, protein)

            # Subcutaneous fat percentage (bytes 8-9, little endian, units of 0.1%)
            if len(mfr_data) > 9:
                subcutaneous_fat_bytes = mfr_data[8:10]
                subcutaneous_fat_raw = int.from_bytes(subcutaneous_fat_bytes, "little")
                if subcutaneous_fat_raw != 0:
                    subcutaneous_fat = subcutaneous_fat_raw / 10.0  # Convert from 0.1% to %
                    _LOGGER.debug("Subcutaneous fat: %.1f%%", subcutaneous_fat)
                    self.update_sensor("subcutaneous_fat", Units.PERCENTAGE, subcutaneous_fat)

            # Visceral fat grade (byte 10)
            if len(mfr_data) > 10 and mfr_data[10] != 0:
                visceral_fat_grade = mfr_data[10]
                _LOGGER.debug("Visceral fat grade: %d", visceral_fat_grade)
                self.update_sensor("visceral_fat_grade", "grade", visceral_fat_grade)

            # Lean body mass (byte 12, integer part in kg)
            if len(mfr_data) > 12 and mfr_data[12] != 0:
                lean_body_mass = mfr_data[12]
                _LOGGER.debug("Lean body mass: %d kg", lean_body_mass)
                self.update_sensor("lean_body_mass", Units.MASS_KILOGRAMS, lean_body_mass)

            # Body water percentage (bytes 17-18, little endian, units of 0.1%)
            if len(mfr_data) > 18:
                body_water_bytes = mfr_data[17:19]
                body_water_raw = int.from_bytes(body_water_bytes, "little")
                if body_water_raw != 0:
                    body_water = body_water_raw / 10.0  # Convert from 0.1% to %
                    _LOGGER.debug("Body water: %.1f%%", body_water)
                    self.update_sensor("body_water", Units.PERCENTAGE, body_water)

        except (IndexError, ValueError) as e:
            _LOGGER.warning("Error parsing body composition data: %s", e)