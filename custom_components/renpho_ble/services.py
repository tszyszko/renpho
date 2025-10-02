"""Services for Renpho BLE integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import async_entries_for_device

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Renpho BLE integration."""

    async def trigger_measurement(call: ServiceCall) -> None:
        """Trigger a measurement on a Renpho scale."""
        device_id = call.data.get("device_id")
        if not device_id:
            _LOGGER.error("device_id is required")
            return

        # Find the coordinator for this device
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if not device:
            _LOGGER.error("Device not found: %s", device_id)
            return

        # Find the coordinator in hass.data
        for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
            if hasattr(coordinator, 'address') and device.identifiers:
                for identifier in device.identifiers:
                    if identifier[1] == coordinator.address:
                        _LOGGER.info("Triggering measurement for device: %s", device.name)
                        await coordinator.async_request_refresh()
                        return

        _LOGGER.error("Coordinator not found for device: %s", device_id)

    hass.services.async_register(
        DOMAIN,
        "trigger_measurement",
        trigger_measurement,
        schema={
            "device_id": str,
        }
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for the Renpho BLE integration."""
    hass.services.async_remove(DOMAIN, "trigger_measurement")