"""Sure Petcare config flow."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries, core, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from surepy import Surepy
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

# pylint: disable=relative-beyond-top-level
from .const import (
    ATTR_VOLTAGE_FULL,
    ATTR_VOLTAGE_LOW,
    CONF_IGNORED_IDS,
    DOMAIN,
    SPC,
    SURE_API_TIMEOUT,
    SURE_BATT_VOLTAGE_FULL,
    SURE_BATT_VOLTAGE_LOW,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class InvalidAuth(Exception):
    """Raised when the credentials are rejected."""


class CannotConnect(Exception):
    """Raised when surepetcare.io cannot be reached."""


async def get_token(hass: core.HomeAssistant, user_input: dict[str, Any]) -> str:
    """Log in with the supplied credentials and return the auth token."""

    try:
        surepy = Surepy(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            auth_token=None,
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )

        token = await surepy.sac.get_token()

    except SurePetcareAuthenticationError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        raise InvalidAuth from error

    except SurePetcareError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: %s", error)
        raise CannotConnect from error

    if not token:
        raise InvalidAuth

    return str(token)


class SurePetcareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    """Implementation of the Sure Petcare config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SureHAOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SureHAOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow start."""

        errors: dict[str, str] = {}

        if user_input is not None:
            uniq_username = user_input[CONF_USERNAME].casefold()
            await self.async_set_unique_id(uniq_username, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            try:
                token = await get_token(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error while logging in")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Sure Petcare",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class SureHAOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SureHA options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Manage the SureHA options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[ATTR_VOLTAGE_LOW] >= user_input[ATTR_VOLTAGE_FULL]:
                errors["base"] = "invalid_voltage"
            else:
                return self.async_create_entry(
                    title="SureHA Options",
                    data={
                        **user_input,
                        CONF_IGNORED_IDS: sorted(
                            int(_id) for _id in user_input.get(CONF_IGNORED_IDS, [])
                        ),
                    },
                )

        # pets/devices that can be hidden from Home Assistant
        ignored = [
            str(_id) for _id in self.config_entry.options.get(CONF_IGNORED_IDS, [])
        ]
        choices: dict[str, str] = {_id: f"ID {_id}" for _id in ignored}
        if (spc := self.hass.data.get(DOMAIN, {}).get(SPC)) and spc.coordinator.data:
            for entity in spc.coordinator.data.values():
                type_name = entity.type.name.replace("_", " ").title()
                choices[str(entity.id)] = f"{type_name} {entity.name} ({entity.id})"

        options = {
            vol.Optional(
                ATTR_VOLTAGE_LOW,
                default=self.config_entry.options.get(
                    ATTR_VOLTAGE_LOW, SURE_BATT_VOLTAGE_LOW
                ),
            ): float,
            vol.Optional(
                ATTR_VOLTAGE_FULL,
                default=self.config_entry.options.get(
                    ATTR_VOLTAGE_FULL, SURE_BATT_VOLTAGE_FULL
                ),
            ): float,
        }

        if choices:
            options[vol.Optional(CONF_IGNORED_IDS, default=ignored)] = cv.multi_select(
                choices
            )

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=errors
        )
