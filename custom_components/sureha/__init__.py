"""The surepetcare integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from random import choice
from typing import Any

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from surepy import Surepy
from surepy.entities import SurepyEntity
from surepy.enums import EntityType, Location, LockState
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

# pylint: disable=import-error
from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCK_STATE,
    ATTR_PET_ID,
    ATTR_VOLTAGE_FULL,
    ATTR_VOLTAGE_LOW,
    ATTR_WHERE,
    DOMAIN,
    SERVICE_PET_LOCATION,
    SERVICE_SET_LOCK_STATE,
    SURE_API_TIMEOUT,
    SURE_BATT_VOLTAGE_FULL,
    SURE_BATT_VOLTAGE_LOW,
    SERVICE_SET_INDOOR_PET_MODE,
    SERVICE_SET_OUTDOOR_PET_MODE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.SWITCH]
# Harmonize SCAN_INTERVAL comment with coordinator's update_interval
SCAN_INTERVAL = timedelta(seconds=150)

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
    "/\x1b[38;2;255;26;102m·\x1b[0m. ｡.ᐟ\\ᵐᵉᵒʷˎˊ",
    "ᶠᵉᵉᵈ ᵐᵉ /ᐠ-ⱉ-ᐟ\\ﾉ",
    "(≗ᆽ ≗)ﾉ",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Surepetcare from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # set option defaults
    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                ATTR_VOLTAGE_FULL: SURE_BATT_VOLTAGE_FULL,
                ATTR_VOLTAGE_LOW: SURE_BATT_VOLTAGE_LOW,
            },
        )

    try:
        surepy = Surepy(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            auth_token=entry.data.get(CONF_TOKEN),
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )
    except SurePetcareAuthenticationError:
        _LOGGER.error(
            "🐾 \x1b[38;2;255;26;102m·\x1b[0m unable to auth. to surepetcare.io: wrong credentials"
        )
        raise ConfigEntryAuthFailed
    except SurePetcareError as error:
        _LOGGER.error(
            "🐾 \x1b[38;2;255;26;102m·\x1b[0m unable to connect to surepetcare.io: %s",
            error,
        )
        return False

    spc = SurePetcareAPI(hass, entry, surepy)

    async def async_update_data():
        """Fetch data from Sure Petcare API."""
        try:
            async with async_timeout.timeout(20):
                return await spc.surepy.get_entities(refresh=True)

        except SurePetcareAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except SurePetcareError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            _LOGGER.error(f"Unexpected error during data update: {err}")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    spc.coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sureha_sensors",
        update_method=async_update_data,
        update_interval=timedelta(seconds=150),
    )

    await spc.coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = spc

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await spc.async_setup()

    return True


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

    async def set_pet_location(self, pet_id: int, location: Location) -> None:
        """Update the lock state of a flap."""
        await self.surepy.sac.set_pet_location(pet_id, location)
        await self.coordinator.async_request_refresh()

    async def set_lock_state(self, flap_id: int, state: str) -> None:
        """Update the lock state of a flap."""
        # https://github.com/PyCQA/pylint/issues/2062
        # pylint: disable=no-member
        lock_states = {
            LockState.UNLOCKED.name.lower(): self.surepy.sac.unlock,
            LockState.LOCKED_IN.name.lower(): self.surepy.sac.lock_in,
            LockState.LOCKED_OUT.name.lower(): self.surepy.sac.lock_out,
            LockState.LOCKED_ALL.name.lower(): self.surepy.sac.lock,
        }

        # elegant functions dict to choose the right function | idea by @janiversen
        await lock_states[state.lower()](flap_id)
        await self.coordinator.async_request_refresh()

    # --- New Methods for Pet Mode ---
    async def set_pet_indoor_mode(self, device_id: int, tag_id: int) -> None:
        """Set a pet to indoor mode (profile_id=3) using tag_id."""
        _LOGGER.debug(f"Calling surepy.sac.set_indoor_pet for tag_id: {tag_id}, device_id: {device_id}")
        await self.surepy.sac.set_indoor_pet(device_id=device_id, tag_id=tag_id)
        await self.coordinator.async_request_refresh()


    async def set_pet_outdoor_mode(self, device_id: int, tag_id: int) -> None:
        """Set a pet to outdoor mode (profile_id=2) using tag_id."""
        _LOGGER.debug(f"Calling surepy.sac.set_outdoor_pet for tag_id: {tag_id}, device_id: {device_id}")
        await self.surepy.sac.set_outdoor_pet(device_id=device_id, tag_id=tag_id)
        await self.coordinator.async_request_refresh()
    # --- End New Methods ---

    async def async_setup(self) -> bool:
        """Set up the Sure Petcare integration services."""

        _LOGGER.info("")
        _LOGGER.info(
            "%s %s", " \x1b[38;2;255;26;102m·\x1b[0m" * 24, choice(CATS)  # nosec
        )
        _LOGGER.info("  🐾    meeowww..! to the SureHA integration!")
        _LOGGER.info("  🐾      code & issues: https://github.com/benleb/sureha")
        _LOGGER.info(" \x1b[38;2;255;26;102m·\x1b[0m" * 30)
        _LOGGER.info("")

        surepy_entities: list[SurepyEntity] = self.coordinator.data.values()

        pet_ids = [
            entity.id for entity in surepy_entities if entity.type == EntityType.PET
        ]

        # --- Service Registration for Pet Mode ---
        flap_ids = [
            entity.id
            for entity in surepy_entities
            if entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP, EntityType.FEEDER]
        ]
        all_device_ids = sorted(list(set(flap_ids)))

        set_indoor_pet_mode_schema = vol.Schema(
            {
                vol.Required(ATTR_PET_ID): vol.Any(cv.positive_int, vol.In(pet_ids)),
                vol.Required("device_id"): vol.Any(cv.positive_int, vol.In(all_device_ids)),
            }
        )

        async def handle_set_indoor_pet_mode(call: Any) -> None:
            """Call when setting a pet to indoor mode."""
            pet_id_from_service = call.data.get(ATTR_PET_ID) # This is the pet_id from the service call
            device_id = call.data.get("device_id")

            # --- NEW LOOKUP: Find the tag_id from the pet_id ---
            tag_id_for_service = None
            for entity_obj in self.coordinator.data.values():
                if entity_obj.type == EntityType.PET and entity_obj.id == pet_id_from_service:
                    tag_id_for_service = entity_obj.tag_id
                    break

            if tag_id_for_service is None:
                _LOGGER.error(f"Could not find tag_id for pet_id: {pet_id_from_service}. Cannot set indoor mode.")
                return
            # --- END NEW LOOKUP ---

            _LOGGER.info(f"Home Assistant service call: surepy.set_indoor_pet_mode for pet_id: {pet_id_from_service} (tag_id: {tag_id_for_service}), device_id: {device_id}")
            try:
                await self.set_pet_indoor_mode(device_id, tag_id_for_service)
            except SurePetcareError as err:
                _LOGGER.error(f"Failed to set pet {pet_id_from_service} on device {device_id} to indoor mode: {err}")
            except Exception as err:
                _LOGGER.exception(f"An unexpected error occurred while setting pet {pet_id_from_service} on device {device_id} to indoor mode: {err}")

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_SET_INDOOR_PET_MODE,
            handle_set_indoor_pet_mode,
            schema=set_indoor_pet_mode_schema,
        )

        set_outdoor_pet_mode_schema = vol.Schema(
            {
                vol.Required(ATTR_PET_ID): vol.Any(cv.positive_int, vol.In(pet_ids)),
                vol.Required("device_id"): vol.Any(cv.positive_int, vol.In(all_device_ids)),
            }
        )

        async def handle_set_outdoor_pet_mode(call: Any) -> None:
            """Call when setting a pet to outdoor mode."""
            pet_id_from_service = call.data.get(ATTR_PET_ID) # This is the pet_id from the service call
            device_id = call.data.get("device_id")

            # --- NEW LOOKUP: Find the tag_id from the pet_id ---
            tag_id_for_service = None
            for entity_obj in self.coordinator.data.values():
                if entity_obj.type == EntityType.PET and entity_obj.id == pet_id_from_service:
                    tag_id_for_service = entity_obj.tag_id
                    break

            if tag_id_for_service is None:
                _LOGGER.error(f"Could not find tag_id for pet_id: {pet_id_from_service}. Cannot set outdoor mode.")
                return
            # --- END NEW LOOKUP ---

            _LOGGER.info(f"Home Assistant service call: surepy.set_outdoor_pet_mode for pet_id: {pet_id_from_service} (tag_id: {tag_id_for_service}), device_id: {device_id}")
            try:
                await self.set_pet_outdoor_mode(device_id, tag_id_for_service)
            except SurePetcareError as err:
                _LOGGER.error(f"Failed to set pet {pet_id_from_service} on device {device_id} to outdoor mode: {err}")
            except Exception as err:
                _LOGGER.exception(f"An unexpected error occurred while setting pet {pet_id_from_service} on device {device_id} to outdoor mode: {err}")

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_SET_OUTDOOR_PET_MODE,
            handle_set_outdoor_pet_mode,
            schema=set_outdoor_pet_mode_schema,
        )
        # --- End Service Registration ---

        pet_location_service_schema = vol.Schema(
            {
                vol.Required(ATTR_PET_ID): vol.Any(cv.positive_int, vol.In(pet_ids)),
                vol.Required(ATTR_WHERE): vol.Any(
                    cv.string,
                    vol.In(
                        [
                            # https://github.com/PyCQA/pylint/issues/2062
                            # pylint: disable=no-member
                            Location.INSIDE.name.title(),
                            Location.OUTSIDE.name.title(),
                        ]
                    ),
                ),
            }
        )

        async def handle_set_pet_location(call: Any) -> None:
            """Call when setting the lock state."""

            try:
                if (pet_id := int(call.data.get(ATTR_PET_ID))) and (
                    where := str(call.data.get(ATTR_WHERE))
                ):
                    await self.set_pet_location(pet_id, Location[where.upper()])

            except ValueError as error:
                _LOGGER.error(
                    "🐾 \x1b[38;2;255;26;102m·\x1b[0m arguments of wrong type: %s", error
                )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_PET_LOCATION,
            handle_set_pet_location,
            schema=pet_location_service_schema,
        )

        async def handle_set_lock_state(call: Any) -> None:
            """Call when setting the lock state."""

            flap_id = call.data.get(ATTR_FLAP_ID)
            lock_state = call.data.get(ATTR_LOCK_STATE)

            await self.set_lock_state(flap_id, lock_state)

        flap_ids = [
            entity.id
            for entity in surepy_entities
            if entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]
        ]

        lock_state_service_schema = vol.Schema(
            {
                vol.Required(ATTR_FLAP_ID): vol.All(cv.positive_int, vol.In(flap_ids)),
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
