"""Config flow for renpho ble integration."""
from __future__ import annotations

from typing import Any

from .renpho_ble import RenphoBluetoothDeviceData as DeviceData
from .renpho_ble_client import RenphoBLEClient
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_ble_device_from_address,
)
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import DOMAIN


class RenphoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for renpho."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: DeviceData | None = None
        self._discovered_devices: dict[str, str] = {}
        self._device_name: str = ""

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = DeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the bluetooth confirmation step."""
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = device.title or device.get_device_name() or discovery_info.name
        self._device_name = title

        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={CONF_ADDRESS: discovery_info.address, CONF_NAME: title}
            )

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
            data_schema=vol.Schema({
                vol.Optional(CONF_NAME, default=title): str
            })
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            device_name = user_input.get(CONF_NAME, f"Renpho Scale {address}")

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            # Test connection to the device
            try:
                ble_device = await async_ble_device_from_address(self.hass, address)
                if not ble_device:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema({
                            vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices),
                            vol.Optional(CONF_NAME, default=device_name): str
                        }),
                        errors={"base": "device_not_found"}
                    )

                # Test connection
                client = RenphoBLEClient(ble_device, lambda x: None)
                connected = await client.connect()
                if connected:
                    await client.disconnect()
                    return self.async_create_entry(
                        title=device_name,
                        data={CONF_ADDRESS: address, CONF_NAME: device_name}
                    )
                else:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema({
                            vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices),
                            vol.Optional(CONF_NAME, default=device_name): str
                        }),
                        errors={"base": "cannot_connect"}
                    )
            except Exception as err:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({
                        vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices),
                        vol.Optional(CONF_NAME, default=device_name): str
                    }),
                    errors={"base": "unknown"}
                )

        current_addresses = self._async_current_ids()
        self._discovered_devices = {}

        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = DeviceData()
            if device.supported(discovery_info):
                device_name = f"Renpho Scale {address}"
                self._discovered_devices[address] = device_name

        if not self._discovered_devices:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default="Renpho Scale"): str
                }),
                errors={"base": "no_devices_found"}
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices),
                vol.Optional(CONF_NAME, default="Renpho Scale"): str
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RenphoOptionsFlowHandler(config_entry)


class RenphoOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Renpho BLE."""

    def __init__(self, config_entry: ConfigFlow) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "weight_unit",
                    default=self.config_entry.options.get("weight_unit", "kg")
                ): vol.In(["kg", "lb"])
            })
        )