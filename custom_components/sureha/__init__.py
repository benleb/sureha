"""The surepetcare integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from random import choice
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
    CONF_IGNORED_IDS,
    DOMAIN,
    SERVICE_PET_LOCATION,
    SERVICE_SET_LOCK_STATE,
    SPC,
    SURE_API_TIMEOUT,
    SURE_BATT_VOLTAGE_FULL,
    SURE_BATT_VOLTAGE_LOW,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=3)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
            async with asyncio.timeout(20):
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

    # reload the entry when the options (battery voltages) change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return await spc.async_setup()


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry (e.g. after the options changed)."""
    await hass.config_entries.async_reload(entry.entry_id)


def get_ignored_ids(entry: ConfigEntry) -> set[int]:
    """Return the IDs of the pets/devices the user removed from Home Assistant."""

    ignored: set[int] = set()
    for value in entry.options.get(CONF_IGNORED_IDS, []):
        try:
            ignored.add(int(value))
        except (TypeError, ValueError):
            continue
    return ignored


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow deleting a pet/device from the UI.

    If Sure Petcare still reports it (e.g. a pet that is still in the account),
    its ID is added to the ignored list so it is not created again.
    """

    device_ids: set[int] = set()
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        try:
            device_ids.add(int(identifier))
        except (TypeError, ValueError):
            continue

    # entities that are not linked to the device (the pet device tracker)
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.unique_id in {f"{_id}_pet_tracker" for _id in device_ids}:
            entity_registry.async_remove(entity.entity_id)

    spc: SurePetcareAPI | None = hass.data.get(DOMAIN, {}).get(SPC)
    known_ids = set(spc.coordinator.data) if spc and spc.coordinator.data else set()

    ignored = get_ignored_ids(entry)
    if new_ignored := (device_ids & known_ids) - ignored:
        _LOGGER.info("🐾 ignoring Sure Petcare IDs: %s", sorted(new_ignored))
        # updating the options reloads the entry (see async_reload_entry)
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_IGNORED_IDS: sorted(ignored | new_ignored),
            },
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(SPC, None)

        for service in (SERVICE_PET_LOCATION, SERVICE_SET_LOCK_STATE):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


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

    @property
    def ignored_ids(self) -> set[int]:
        """IDs of pets/devices that must not be created in Home Assistant."""
        return get_ignored_ids(self.config_entry)

    @property
    def entities(self) -> list[SurepyEntity]:
        """Sure Petcare entities to create in Home Assistant."""
        ignored = self.ignored_ids
        return [
            entity
            for entity in (self.coordinator.data or {}).values()
            if entity.id not in ignored
        ]

    async def set_pet_location(self, pet_id: int, location: Location) -> None:
        """Update the location of a pet."""

        await self.surepy.sac.set_pet_location(pet_id, location)

    async def set_lock_state(self, flap_id: int, state: str) -> None:
        """Update the lock state of a flap."""

        lock_states = {
            LockState.UNLOCKED.name.lower(): self.surepy.sac.unlock,
            LockState.LOCKED_IN.name.lower(): self.surepy.sac.lock_in,
            LockState.LOCKED_OUT.name.lower(): self.surepy.sac.lock_out,
            LockState.LOCKED_ALL.name.lower(): self.surepy.sac.lock,
        }

        await lock_states[state.lower()](flap_id)

    async def async_setup(self) -> bool:
        """Set up the Sure Petcare integration."""

        _LOGGER.info("")
        _LOGGER.info(
            "%s %s", " \x1b[38;2;255;26;102m·\x1b[0m" * 24, choice(CATS)  # nosec
        )
        _LOGGER.info("  🐾   meeowww..! to the SureHA integration!")
        _LOGGER.info("  🐾     code & issues: https://github.com/scoprire87/sureha")
        _LOGGER.info(" \x1b[38;2;255;26;102m·\x1b[0m" * 30)
        _LOGGER.info("")

        await self.hass.config_entries.async_forward_entry_setups(self.config_entry, PLATFORMS)

        surepy_entities: list[SurepyEntity] = self.coordinator.data.values()

        pet_ids = [
            entity.id for entity in surepy_entities if entity.type == EntityType.PET
        ]

        pet_location_service_schema = vol.Schema(
            {
                vol.Required(ATTR_PET_ID): vol.All(cv.positive_int, vol.In(pet_ids)),
                vol.Required(ATTR_WHERE): vol.All(
                    cv.string,
                    vol.Strip,
                    vol.Title,
                    vol.In(
                        [
                            Location.INSIDE.name.title(),
                            Location.OUTSIDE.name.title(),
                        ]
                    ),
                ),
            }
        )

        async def handle_set_pet_location(call: ServiceCall) -> None:
            """Call when setting the location of a pet."""

            pet_id: int = call.data[ATTR_PET_ID]
            location = Location[call.data[ATTR_WHERE].upper()]

            try:
                await self.set_pet_location(pet_id, location)
            except SurePetcareError as error:
                raise HomeAssistantError(
                    f"Unable to set the location of pet {pet_id}: {error}"
                ) from error

            await self.coordinator.async_request_refresh()

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_PET_LOCATION,
            handle_set_pet_location,
            schema=pet_location_service_schema,
        )

        async def handle_set_lock_state(call: ServiceCall) -> None:
            """Call when setting the lock state."""

            flap_id: int = call.data[ATTR_FLAP_ID]
            lock_state: str = call.data[ATTR_LOCK_STATE]

            try:
                await self.set_lock_state(flap_id, lock_state)
            except SurePetcareError as error:
                raise HomeAssistantError(
                    f"Unable to set the lock state of flap {flap_id}: {error}"
                ) from error

            await self.coordinator.async_request_refresh()

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
                    vol.Strip,
                    vol.Lower,
                    vol.In(
                        [
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
