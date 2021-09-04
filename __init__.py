"""The surepetcare integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from random import choice
from typing import Any

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from surepy import Surepy
from surepy.enums import LockState
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

# pylint: disable=import-error
from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCK_STATE,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SPC,
    SURE_API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]
SCAN_INTERVAL = timedelta(minutes=3)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

CATS = [
    "/ᐠ｡▿｡ᐟ\\*ᵖᵘʳʳ",
    "/ᐠ_ꞈ_ᐟ\\ɴʏᴀ~",
    "/ᐠ ._. ᐟ\\ﾉ",
    "/ᐠ. ｡.ᐟ\\ᵐᵉᵒʷˎˊ",
    "ᶠᵉᵉᵈ ᵐᵉ /ᐠ-ⱉ-ᐟ\\ﾉ",
    "(≗ᆽ ≗)ﾉ",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up."""

    hass.data.setdefault(DOMAIN, {})

    try:
        surepy = Surepy(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            auth_token=entry.data[CONF_TOKEN] if CONF_TOKEN in entry.data else None,
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )
    except SurePetcareAuthenticationError:
        _LOGGER.error(
            "🐾 \x1b[38;2;255;26;102m·\x1b[0m unable to auth. to surepetcare.io: wrong credentials"
        )
        return False
    except SurePetcareError as error:
        _LOGGER.error(
            "🐾 \x1b[38;2;255;26;102m·\x1b[0m unable to connect to surepetcare.io: %s",
            error,
        )
        return False

    spc = SurePetcareAPI(hass, entry, surepy)

    async def async_update_data():

        try:
            # asyncio.TimeoutError and aiohttp.ClientError already handled

            async with async_timeout.timeout(20):
                return await spc.surepy.get_entities(refresh=True)

        except SurePetcareAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except SurePetcareError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    spc.coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sureha_sensors",
        update_method=async_update_data,
        update_interval=timedelta(seconds=150),
    )

    await spc.coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][SPC] = spc

    return await spc.async_setup()


class SurePetcareAPI:
    """Define a generic Sure Petcare object."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, surepy: Surepy
    ) -> None:
        """Initialize the Sure Petcare object."""

        self.coordinator: DataUpdateCoordinator

        self.hass = hass
        self.config_entry = config_entry
        self.surepy = surepy

        self.states: dict[int, Any] = {}

    async def set_lock_state(self, flap_id: int, state: str) -> None:
        """Update the lock state of a flap."""

        # https://github.com/PyCQA/pylint/issues/2062
        # pylint: disable=no-member
        if state == LockState.UNLOCKED.name.lower():
            await self.surepy.sac.unlock(flap_id)
        elif state == LockState.LOCKED_IN.name.lower():
            await self.surepy.sac.lock_in(flap_id)
        elif state == LockState.LOCKED_OUT.name.lower():
            await self.surepy.sac.lock_out(flap_id)
        elif state == LockState.LOCKED_ALL.name.lower():
            await self.surepy.sac.lock(flap_id)

    async def async_setup(self) -> bool:
        """Set up the Sure Petcare integration."""

        _LOGGER.info("")
        _LOGGER.info(
            "%s %s", " \x1b[38;2;255;26;102m·\x1b[0m" * 24, choice(CATS)  # nosec
        )
        _LOGGER.info("  🐾   meeowww..! to the SureHA integration!")
        _LOGGER.info("  🐾     code & issues: https://github.com/benleb/sureha")
        _LOGGER.info(" \x1b[38;2;255;26;102m·\x1b[0m" * 30)
        _LOGGER.info("")

        self.hass.async_add_job(
            self.hass.config_entries.async_forward_entry_setup(  # type: ignore
                self.config_entry, "binary_sensor"
            )
        )

        self.hass.async_add_job(
            self.hass.config_entries.async_forward_entry_setup(  # type: ignore
                self.config_entry, "sensor"
            )
        )

        # self.hass.async_add_job(
        #     self.hass.config_entries.async_forward_entry_setup(  # type: ignore
        #         self.config_entry, "device_tracker"
        #     )
        # )

        async def handle_set_lock_state(call: Any) -> None:
            """Call when setting the lock state."""
            await self.set_lock_state(
                call.data[ATTR_FLAP_ID], call.data[ATTR_LOCK_STATE]
            )

            await self.coordinator.async_request_refresh()

        lock_state_service_schema = vol.Schema(
            {
                vol.Required(ATTR_FLAP_ID): vol.All(
                    cv.positive_int, vol.In(self.states.keys())
                ),
                vol.Required(ATTR_LOCK_STATE): vol.All(
                    cv.string,
                    vol.Lower,
                    vol.In(
                        [
                            # https://github.com/PyCQA/pylint/issues/2062
                            # pylint: disable=no-member
                            LockState.UNLOCKED.name.lower(),
                            LockState.LOCKED_IN.name.lower(),
                            LockState.LOCKED_OUT.name.lower(),
                            LockState.LOCKED_ALL.name.lower(),
                        ]
                    ),
                ),
            }
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_SET_LOCK_STATE,
            handle_set_lock_state,
            schema=lock_state_service_schema,
        )

        return True
