"""Adds config flow for Petcare integration."""
from __future__ import annotations

import logging

from typing import Any

import voluptuous as vol

from homeassistant import config_entries, core, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from surepy import Surepy
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError

from .const import DOMAIN, SURE_API_TIMEOUT


# from .petcare import Petcare

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str})


async def is_valid(hass: core.HomeAssistant, user_input: dict[str, Any]) -> str | None:

    _LOGGER.info(f"is_valid(..) called with {user_input = }")

    try:
        surepy = Surepy(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            auth_token=None,
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )

        return await surepy.sac.get_token()

    except SurePetcareAuthenticationError:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        return None

    except SurePetcareError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: %s", error)
        return None


# @config_entries.HANDLERS.register(DOMAIN)
class SurePetcareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, import_info: dict[str, Any]) -> data_entry_flow.FlowResult:
        """set up entry from configuration.yaml file."""

        _LOGGER.info(f"async_step_import(..) called with {import_info = }")

        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        # Specify items in the order they are to be displayed in the UI

        errors: dict[str, Any] = {}

        _LOGGER.info(f"async_step_user(..) called with {user_input = }")

        if not user_input:
            _LOGGER.info(f"no user_input, calling async_show_form(..) with {DATA_SCHEMA = }")
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        if token := await is_valid(self.hass, user_input):

            uniq_username = user_input[CONF_USERNAME].casefold()
            await self.async_set_unique_id(uniq_username, raise_on_progress=False)

            return self.async_create_entry(
                title="Sure Petcare",
                data={
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_TOKEN: token,
                },
            )

        else:

            return self.async_abort(reason="authentication_failed")
