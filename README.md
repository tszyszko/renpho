# Renpho BLE Integration - Active Communication

This is an updated version of the Renpho BLE integration that uses **active BLE communication** instead of passive advertisement scanning. This change was necessary because newer Renpho scale firmware requires active connection and communication to fetch measurement data.

## Key Changes

### From Passive to Active Communication
- **Old**: Scanned for BLE advertisements and parsed manufacturer data
- **New**: Actively connects to the scale and communicates via BLE characteristics
- **Result**: Works with newer Renpho scale firmware that doesn't broadcast data in advertisements

### New Architecture
1. **BLE Client** (`renpho_ble_client.py`): Handles active BLE communication
2. **Data Coordinator** (`sensor.py`): Manages measurement requests and data updates
3. **Enhanced Config Flow**: Tests connection during setup
4. **Manual Services**: Trigger measurements on demand

## Features

### Supported Sensors
- **Weight**: Primary weight measurement in kg
- **Body Fat**: Calculated body fat percentage
- **Body Water**: Calculated body water percentage
- **Muscle Mass**: Calculated muscle mass in kg
- **Bone Mass**: Calculated bone mass in kg
- **Impedance**: Raw impedance measurement (disabled by default)

### Services
- `renpho_ble.trigger_measurement`: Manually trigger a measurement
  - Parameters: `device_id` (required)

### Configuration
- **Automatic Discovery**: Detects Renpho scales via BLE scanning
- **Manual Entry**: Enter MAC address manually
- **Connection Testing**: Verifies connection during setup
- **Weight Unit**: Choose between kg and lb

## Installation

1. Copy the `custom_components/renpho_ble/` folder to your Home Assistant `custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Renpho Bluetooth"
5. Follow the setup wizard

## Usage

### Automatic Setup
1. Ensure your Renpho scale is nearby and powered on
2. Step on the scale briefly to wake it up
3. Start the integration setup
4. The scale should appear in the discovered devices list
5. Select it and complete setup

### Manual Setup
1. Find your scale's MAC address (check your phone's Bluetooth settings)
2. Start the integration setup
3. Choose "Configure manually"
4. Enter the MAC address
5. The integration will test the connection

### Taking Measurements
1. **Automatic**: Step on the scale - measurements will be taken automatically
2. **Manual**: Use the `renpho_ble.trigger_measurement` service
3. **Entity Updates**: Sensors update when new measurements are available

## Technical Details

### BLE Protocol
The integration implements the QN Scale BLE protocol used by Renpho scales:

- **Service UUID**: `0000ffe0-0000-1000-8000-00805f9b34fb`
- **Characteristics**:
  - `0000ffe1`: Weight data notifications
  - `0000ffe2`: Status indications
  - `0000ffe3`: Command writes
  - `0000ffe4`: Time synchronization

### Communication Flow
1. Connect to scale
2. Set up notifications on weight characteristic
3. Send weight request command
4. Send time synchronization
5. Wait for measurement data
6. Parse weight and impedance values
7. Calculate body composition metrics

### Body Composition Calculations
The integration calculates body composition using impedance values:
- **Body Fat**: Based on impedance and weight
- **Body Water**: Estimated from impedance
- **Muscle Mass**: Calculated from weight and body fat
- **Bone Mass**: Estimated as percentage of total weight

*Note: These are simplified calculations. For accurate results, use the official Renpho app.*

## Troubleshooting

### Connection Issues
- Ensure the scale is nearby (within 10 meters)
- Make sure the scale is powered on and awake
- Try stepping on the scale briefly before setup
- Check that Bluetooth is enabled on your Home Assistant system

### No Measurements
- Verify the scale is connected (check device status)
- Try triggering a manual measurement via service
- Check Home Assistant logs for error messages
- Ensure the scale is not connected to another device (phone, tablet)

### Setup Fails
- Try manual setup with MAC address
- Restart Home Assistant and try again
- Check that the scale supports BLE (not just Bluetooth Classic)
- Verify the scale is not already paired with another device

## Development

### Testing
Run the test script to verify BLE communication:
```bash
python test_renpho_ble.py
```

### Logging
Enable debug logging for the integration:
```yaml
logger:
  logs:
    custom_components.renpho_ble: debug
```

### Contributing
This integration is based on the OpenScale Android app's BLE implementation. The Java code was translated to Python using the `bleak` library for BLE communication.

## Compatibility

- **Home Assistant**: 2023.1+
- **Python**: 3.10+
- **Dependencies**: `bleak>=0.21.0`
- **Renpho Scales**: ES-CS20M-W and similar models with BLE support

## License

This integration is provided as-is for educational and personal use. The BLE protocol implementation is based on reverse engineering of the official Renpho app.