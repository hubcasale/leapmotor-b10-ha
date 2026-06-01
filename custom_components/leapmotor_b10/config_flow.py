"""Config flow for Leapmotor B10 integration."""
from __future__ import annotations

from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_ENTRY_ID,
    CONF_BATTERY_CAPACITY,
    CONF_WALLBOX_ENTITY,
    CONF_MARIADB_PASSWORD,
    DEFAULT_BATTERY_CAPACITY,
)

class LeapmotorB10ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Leapmotor B10."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Leapmotor B10", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTRY_ID): str,
                    vol.Optional(CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY): float,
                    vol.Optional(CONF_WALLBOX_ENTITY): str,
                    vol.Optional(CONF_MARIADB_PASSWORD): str,
                }
            ),
        )
