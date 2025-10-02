#!/usr/bin/env python3
"""Test script for Renpho BLE client."""

import asyncio
import logging
from bleak import BleakScanner
from custom_components.renpho_ble.renpho_ble_client import RenphoBLEClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_renpho_ble():
    """Test the Renpho BLE client."""
    print("Scanning for Renpho devices...")

    # Scan for devices
    devices = await BleakScanner.discover(timeout=10.0)
    renpho_devices = []

    for device in devices:
        if device.name and "renpho" in device.name.lower():
            renpho_devices.append(device)
            print(f"Found Renpho device: {device.name} ({device.address})")

    if not renpho_devices:
        print("No Renpho devices found")
        return

    # Test connection to first device
    device = renpho_devices[0]
    print(f"Testing connection to {device.name} ({device.address})")

    def measurement_callback(data):
        print(f"Received measurement: {data}")

    client = RenphoBLEClient(device, measurement_callback)

    try:
        # Connect
        connected = await client.connect()
        if not connected:
            print("Failed to connect")
            return

        print("Connected successfully")

        # Start measurement
        print("Starting measurement...")
        success = await client.start_measurement()
        if success:
            print("Measurement started, waiting for data...")
            await asyncio.sleep(10)  # Wait for measurement
        else:
            print("Failed to start measurement")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    asyncio.run(test_renpho_ble())