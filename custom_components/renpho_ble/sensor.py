"""Support for renpho ble sensors."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Union

from .renpho_ble import DeviceClass, DeviceKey, SensorUpdate, Units
from .renpho_ble_client import RenphoBLEClient

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfMass,
    CONF_ADDRESS,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = {
    "weight": SensorEntityDescription(
        key="weight",
        name="Weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "body_fat": SensorEntityDescription(
        key="body_fat",
        name="Body Fat",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "body_water": SensorEntityDescription(
        key="body_water",
        name="Body Water",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "muscle_mass": SensorEntityDescription(
        key="muscle_mass",
        name="Muscle Mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "bone_mass": SensorEntityDescription(
        key="bone_mass",
        name="Bone Mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "impedance": SensorEntityDescription(
        key="impedance",
        name="Impedance",
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
}


class RenphoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Renpho scale."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialize the coordinator."""
        self.address = address
        self.name = name
        self.client: Optional[RenphoBLEClient] = None
        self._measurement_data: Dict[str, Any] = {}
        self._measurement_event = asyncio.Event()

        super().__init__(
            hass,
            _LOGGER,
            name=f"Renpho Scale {name}",
            update_interval=None,  # We update on demand
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data from the scale."""
        if not self.client or not self.client.is_connected:
            raise UpdateFailed("Scale not connected")

        # Clear previous measurement
        self._measurement_data = {}
        self._measurement_event.clear()

        # Start measurement
        success = await self.client.start_measurement()
        if not success:
            raise UpdateFailed("Failed to start measurement")

        # Wait for measurement data (with timeout)
        try:
            await asyncio.wait_for(self._measurement_event.wait(), timeout=30.0)
            return self._measurement_data
        except asyncio.TimeoutError:
            raise UpdateFailed("Measurement timeout")

    def measurement_callback(self, data: Dict[str, Any]) -> None:
        """Handle measurement data from the BLE client."""
        _LOGGER.debug("Received measurement data: %s", data)
        self._measurement_data = data
        self._measurement_event.set()

    async def connect(self) -> bool:
        """Connect to the scale."""
        try:
            ble_device = await async_ble_device_from_address(self.hass, self.address)
            if not ble_device:
                _LOGGER.error("Device not found: %s", self.address)
                return False

            self.client = RenphoBLEClient(ble_device, self.measurement_callback)
            connected = await self.client.connect()
            if connected:
                _LOGGER.info("Connected to Renpho scale: %s", self.address)
            return connected
        except Exception as err:
            _LOGGER.error("Error connecting to scale: %s", err)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the scale."""
        if self.client:
            await self.client.disconnect()
            self.client = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renpho BLE sensors."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data.get(CONF_NAME, f"Renpho Scale {address}")

    coordinator = RenphoDataUpdateCoordinator(hass, address, name)

    # Connect to the scale
    connected = await coordinator.connect()
    if not connected:
        _LOGGER.error("Failed to connect to Renpho scale: %s", address)
        return

    # Create sensors
    entities = []
    for sensor_key, description in SENSOR_DESCRIPTIONS.items():
        entities.append(
            RenphoBluetoothSensorEntity(coordinator, sensor_key, description)
        )

    async_add_entities(entities)

    # Store coordinator in hass.data for services
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up services if not already done
    if not hasattr(hass.data[DOMAIN], '_services_setup'):
        await async_setup_services(hass)
        hass.data[DOMAIN]['_services_setup'] = True


class RenphoBluetoothSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a Renpho BLE sensor."""

    def __init__(
        self,
        coordinator: RenphoDataUpdateCoordinator,
        sensor_key: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.address}_{sensor_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.name,
            manufacturer="Renpho",
            model="BLE Scale",
        )

    @property
    def native_value(self) -> Union[float, int, None]:
        """Return the native value."""
        if not self.coordinator.data:
            return None

        return self.coordinator.data.get(self._sensor_key)

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._sensor_key in self.coordinator.data
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Trigger a measurement when the entity is added
        if self.coordinator.client and self.coordinator.client.is_connected:
            await self.coordinator.async_request_refresh()

    async def async_update(self) -> None:
        """Update the sensor data."""
        if self.coordinator.client and self.coordinator.client.is_connected:
            await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self.coordinator.client:
            await self.coordinator.disconnect()
        await super().async_will_remove_from_hass()