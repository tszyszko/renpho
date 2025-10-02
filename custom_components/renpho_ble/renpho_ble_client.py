"""Active BLE client for Renpho scale communication."""

from __future__ import annotations

import asyncio
import logging
import struct
from datetime import datetime
from typing import Any, Callable, Optional

from bleak import BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

_LOGGER = logging.getLogger(__name__)

# Scale time is in seconds since 2000-01-01 00:00:00 (UTC)
SCALE_UNIX_TIMESTAMP_OFFSET = 946702800
MILLIS_2000_YEAR = 949334400000

# Service and Characteristic UUIDs
WEIGHT_MEASUREMENT_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
WEIGHT_MEASUREMENT_CONFIG = "00002902-0000-1000-8000-00805f9b34fb"

# First type characteristics
CUSTOM1_MEASUREMENT_CHARACTERISTIC = "0000ffe1-0000-1000-8000-00805f9b34fb"  # notify, read-only
CUSTOM2_MEASUREMENT_CHARACTERISTIC = "0000ffe2-0000-1000-8000-00805f9b34fb"  # indication, read-only
CUSTOM3_MEASUREMENT_CHARACTERISTIC = "0000ffe3-0000-1000-8000-00805f9b34fb"  # write-only
CUSTOM4_MEASUREMENT_CHARACTERISTIC = "0000ffe4-0000-1000-8000-00805f9b34fb"  # write-only
CUSTOM5_MEASUREMENT_CHARACTERISTIC = "0000ffe5-0000-1000-8000-00805f9b34fb"  # write-only

# Second type service and characteristics
WEIGHT_MEASUREMENT_SERVICE_ALTERNATIVE = "0000fff0-0000-1000-8000-00805f9b34fb"
CUSTOM1_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE = "0000fff1-0000-1000-8000-00805f9b34fb"  # notify, read-only
CUSTOM3_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE = "0000fff2-0000-1000-8000-00805f9b34fb"  # write-only


class RenphoBLEClient:
    """Active BLE client for Renpho scale communication."""

    def __init__(self, device: BLEDevice, callback: Callable[[dict[str, Any]], None]) -> None:
        """Initialize the BLE client."""
        self.device = device
        self.callback = callback
        self.client: Optional[BleakClient] = None
        self.use_first_type = True
        self.final_measure_received = False
        self.weight_scale = 100.0
        self.seen_protocol_type = 0
        self._connected = False
        self._connection_lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to the Renpho scale."""
        async with self._connection_lock:
            if self._connected:
                return True

            try:
                self.client = BleakClient(self.device)
                await self.client.connect()
                self._connected = True
                _LOGGER.info("Connected to Renpho scale: %s", self.device.address)
                return True
            except BleakError as err:
                _LOGGER.error("Failed to connect to Renpho scale: %s", err)
                return False

    async def disconnect(self) -> None:
        """Disconnect from the Renpho scale."""
        async with self._connection_lock:
            if self.client and self._connected:
                try:
                    await self.client.disconnect()
                    _LOGGER.info("Disconnected from Renpho scale: %s", self.device.address)
                except BleakError as err:
                    _LOGGER.error("Error disconnecting from Renpho scale: %s", err)
                finally:
                    self._connected = False

    async def start_measurement(self, weight_unit: str = "kg") -> bool:
        """Start the measurement process."""
        if not self._connected or not self.client:
            _LOGGER.error("Not connected to scale")
            return False

        try:
            # Step 0: Try to determine protocol type
            await self._try_protocol_type()

            # Step 1: Set up notifications
            await self._setup_notifications()

            # Step 2: Send weight data request
            await self._send_weight_request(weight_unit)

            # Step 3: Send time magic number
            await self._send_time_magic()

            _LOGGER.info("Measurement process started")
            return True

        except Exception as err:
            _LOGGER.error("Error starting measurement: %s", err)
            return False

    async def _try_protocol_type(self) -> None:
        """Try to determine which protocol type to use."""
        try:
            timestamp = int(datetime.now().timestamp()) - SCALE_UNIX_TIMESTAMP_OFFSET
            date_bytes = struct.pack("<I", timestamp)
            message = bytes([0x02]) + date_bytes

            await self.client.write_gatt_char(CUSTOM4_MEASUREMENT_CHARACTERISTIC, message)
            self.use_first_type = True
            _LOGGER.debug("Using first protocol type")
        except Exception:
            self.use_first_type = False
            _LOGGER.debug("Using alternative protocol type")

    async def _setup_notifications(self) -> None:
        """Set up BLE notifications and indications."""
        if self.use_first_type:
            # Set up notifications for first type
            await self.client.start_notify(
                CUSTOM1_MEASUREMENT_CHARACTERISTIC,
                self._handle_custom1_notification
            )
            await self.client.start_notify(
                CUSTOM2_MEASUREMENT_CHARACTERISTIC,
                self._handle_custom2_notification
            )
        else:
            # Set up notifications for alternative type
            await self.client.start_notify(
                CUSTOM1_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE,
                self._handle_custom1_notification
            )

    async def _send_weight_request(self, weight_unit: str) -> None:
        """Send weight data request."""
        weight_unit_byte = 0x01 if weight_unit.lower() == "kg" else 0x02
        message = self._build_message(0x13, self.seen_protocol_type, weight_unit_byte, 0x10, 0x00, 0x00, 0x00)

        if self.use_first_type:
            await self.client.write_gatt_char(CUSTOM3_MEASUREMENT_CHARACTERISTIC, message)
        else:
            await self.client.write_gatt_char(CUSTOM3_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE, message)

    async def _send_time_magic(self) -> None:
        """Send time magic number to receive weight data."""
        timestamp = int(datetime.now().timestamp()) - SCALE_UNIX_TIMESTAMP_OFFSET
        date_bytes = struct.pack("<I", timestamp)
        message = bytes([0x02]) + date_bytes

        if self.use_first_type:
            await self.client.write_gatt_char(CUSTOM4_MEASUREMENT_CHARACTERISTIC, message)
        else:
            await self.client.write_gatt_char(CUSTOM3_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE, message)

    def _handle_custom1_notification(self, characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
        """Handle custom1 characteristic notifications."""
        _LOGGER.debug("Received custom1 data: %s", [hex(b) for b in data])
        self._parse_custom1_data(data)

    def _handle_custom2_notification(self, characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
        """Handle custom2 characteristic notifications."""
        _LOGGER.debug("Received custom2 data: %s", [hex(b) for b in data])

    def _parse_custom1_data(self, data: bytearray) -> None:
        """Parse custom1 data according to the protocol."""
        if len(data) < 3:
            return

        command = data[0] & 0xff
        protocol_type = data[2] & 0xff

        if self.seen_protocol_type == 0:
            self.seen_protocol_type = protocol_type

        if command == 0x10:  # Weight measurement
            self._parse_weight_measurement(data, protocol_type)
        elif command == 0x12:  # Scale settings
            self._handle_scale_settings(data, protocol_type)
        elif command == 0x14:  # Unknown command
            self._handle_command_14(data, protocol_type)
        elif command == 0x21:  # Unknown command
            self._handle_command_21(data, protocol_type)
        elif command == 0x23:  # Historical data
            self._handle_historical_data(data, protocol_type)
        elif command == 0xa1:  # Unknown command
            self._handle_command_a1(data, protocol_type)

    def _parse_weight_measurement(self, data: bytearray, protocol_type: int) -> None:
        """Parse weight measurement data."""
        # Determine offsets based on protocol type
        if protocol_type == 0xff:
            done_state = 2
            done_offset = 4
            weight_offset = 5
            resist_offset = 7
        else:
            done_state = 1
            done_offset = 5
            weight_offset = 3
            resist_offset = 6

        if len(data) <= max(done_offset, weight_offset + 1, resist_offset + 3):
            return

        done = data[done_offset] & 0xff

        if done == 0:
            # Unsteady measurement
            self.final_measure_received = False
            _LOGGER.debug("Unsteady weight measurement")
        elif done == done_state and not self.final_measure_received:
            # Final measurement
            self.final_measure_received = True

            weight_kg = self._decode_weight(data[weight_offset], data[weight_offset + 1])

            # Adjust weight scale for alternative protocol
            if not self.use_first_type:
                weight_kg /= 10.0

            _LOGGER.debug("Final weight: %.2f kg", weight_kg)

            if weight_kg > 0.0:
                # Parse resistance values
                resistance1 = self._decode_integer_value(data[resist_offset], data[resist_offset + 1])
                resistance2 = self._decode_integer_value(data[resist_offset + 2], data[resist_offset + 3])

                _LOGGER.debug("Resistance1: %d, Resistance2: %d", resistance1, resistance2)

                # Calculate body composition using resistance
                measurement_data = {
                    "weight": weight_kg,
                    "resistance1": resistance1,
                    "resistance2": resistance2,
                    "impedance": self._calculate_impedance(resistance1),
                    "timestamp": datetime.now().isoformat()
                }

                # Send data to callback
                self.callback(measurement_data)

    def _handle_scale_settings(self, data: bytearray, protocol_type: int) -> None:
        """Handle scale settings command."""
        if len(data) > 10:
            self.weight_scale = 100.0 if (data[10] & 0xff) == 1 else 10.0

        # Send response
        response = self._build_message(0x13, protocol_type, 0x01, 0x10, 0x00, 0x00, 0x00)
        asyncio.create_task(self._send_response(response))

    def _handle_command_14(self, data: bytearray, protocol_type: int) -> None:
        """Handle command 0x14."""
        response = self._build_message(0x20, protocol_type, 0x25, 0x74, 0x18, 0x30)
        asyncio.create_task(self._send_response(response))

    def _handle_command_21(self, data: bytearray, protocol_type: int) -> None:
        """Handle command 0x21."""
        response = self._build_message(0xa0, 0x02, 0xfe, 0xff, 0xee, 0x01, 0x1c, 0x06, 0x86, 0x03, 0x02)
        asyncio.create_task(self._send_response(response))

    def _handle_historical_data(self, data: bytearray, protocol_type: int) -> None:
        """Handle historical data command."""
        # Implementation for historical data parsing
        pass

    def _handle_command_a1(self, data: bytearray, protocol_type: int) -> None:
        """Handle command 0xa1."""
        response = self._build_message(0x22, protocol_type, 0x00, 0x01)
        asyncio.create_task(self._send_response(response))

    async def _send_response(self, message: bytes) -> None:
        """Send response message."""
        if not self.client or not self._connected:
            return

        try:
            if self.use_first_type:
                await self.client.write_gatt_char(CUSTOM3_MEASUREMENT_CHARACTERISTIC, message)
            else:
                await self.client.write_gatt_char(CUSTOM3_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE, message)
        except Exception as err:
            _LOGGER.error("Error sending response: %s", err)

    def _decode_weight(self, byte1: int, byte2: int) -> float:
        """Decode weight from two bytes."""
        raw_weight = ((byte1 & 0xff) << 8) + (byte2 & 0xff)
        return raw_weight / self.weight_scale

    def _decode_integer_value(self, byte1: int, byte2: int) -> int:
        """Decode integer value from two bytes."""
        return ((byte1 & 0xff) << 8) + (byte2 & 0xff)

    def _calculate_impedance(self, resistance: int) -> float:
        """Calculate impedance from resistance value."""
        if resistance < 410:
            return 3.0
        return 0.3 * (resistance - 400.0)

    @staticmethod
    def _build_message(cmd: int, protocol_type: int, *payload: int) -> bytes:
        """Build message with checksum."""
        msg = bytearray([cmd, len(payload) + 4, protocol_type] + list(payload))

        # Calculate checksum
        checksum = sum(msg[:-1]) & 0xff
        msg[-1] = checksum

        return bytes(msg)

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected