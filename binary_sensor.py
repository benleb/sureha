"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

import logging
from typing import Any

from surepy.entities import PetLocation, SurepyEntity
from surepy.entities.pet import Pet as SurePet
from surepy.enums import EntityType, Location

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

# pylint: disable=relative-beyond-top-level
from . import SurePetcareAPI
from .const import DOMAIN, SPC, SURE_MANUFACTURER, TOPIC_UPDATE

PARALLEL_UPDATES = 2


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: Any,
    discovery_info: Any = None,
) -> None:
    await async_setup_entry(hass, config, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Any
) -> None:
    """Set up config entry Sure PetCare Flaps sensors."""

    entities: list[SurePetcareBinarySensor] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    for surepy_entity in spc.states.values():

        entity = None

        if surepy_entity.type == EntityType.PET:
            entity = Pet(surepy_entity.id, spc)
            entities.append(entity)

        elif surepy_entity.type == EntityType.HUB:
            entity = Hub(surepy_entity.id, spc)
            entities.append(entity)

        # connectivity
        elif surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entity = DeviceConnectivity(surepy_entity.id, spc)
            entities.append(entity)

        if entity:
            _LOGGER.debug("\x1b[38;2;255;26;102m·\x1b[0m🐾 %s added...", entity.name)

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorEntity):  # type: ignore
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(
        self,
        _id: int,
        spc: SurePetcareAPI,
        device_class: str,
        # sure_type: EntityType,
    ):
        """Initialize a Sure Petcare binary sensor."""

        self._id = _id
        self._device_class = device_class

        self._spc: SurePetcareAPI = spc

        self._surepy_entity: SurepyEntity = self._spc.states[self._id]
        self._state: Any = None

        # cover special case where a device has no name set
        type_name = self._surepy_entity.type.name.replace("_", " ").title()
        name = (
            self._surepy_entity.name
            if self._surepy_entity.name
            else f"Unnamed {type_name}"
        )
        self._name = f"{type_name} {name}"

    @property
    def should_poll(self) -> bool:
        """Return if the entity should use default polling."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def device_class(self) -> str | None:
        """Return the device class."""
        return None if not self._device_class else self._device_class

    @property
    def device_info(self):

        device = {}

        try:
            device = {
                "identifiers": {(DOMAIN, self._id)},
                "name": self._surepy_entity.name.title(),
                "manufacturer": SURE_MANUFACTURER,
                "model": self._surepy_entity.type.name.replace("_", " ").title(),
            }

            if self._state:
                versions = self._state.get("version", {})

                if dev_fw_version := versions.get("device", {}).get("firmware"):
                    device["sw_version"] = dev_fw_version

                if (lcd_version := versions.get("lcd", {})) and (
                    rf_version := versions.get("rf", {})
                ):
                    device[
                        "sw_version"
                    ] = f"{lcd_version['version']} | {rf_version['version']}"

        except AttributeError:
            pass

        return device

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._id}"

    @callback  # type: ignore
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_entity = self._spc.states[self._id]
        self._state = self._surepy_entity.raw_data()["status"]
        # _LOGGER.debug("🐾 %s updated", self._surepy_entity.name)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )

        @callback  # type: ignore
        def update() -> None:
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

        self._async_update()


class Hub(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Hub."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY)  # , EntityType.HUB)

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state["online"])

    @property
    def is_on(self) -> bool:
        """Return true if entity is online."""
        return self.available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._surepy_entity.raw_data():
            attributes = {
                "led_mode": int(self._surepy_entity.raw_data()["status"]["led_mode"]),
                "pairing_mode": bool(
                    self._surepy_entity.raw_data()["status"]["pairing_mode"]
                ),
            }

        return attributes


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Pet."""
        super().__init__(_id, spc, DEVICE_CLASS_PRESENCE)  # , EntityType.PET)

        self._surepy_entity: SurePet
        self._state: PetLocation

    @property
    def is_on(self) -> bool:
        """Return true if entity is at home."""
        try:
            return bool(Location(self._state.where) == Location.INSIDE)
        except (KeyError, TypeError):
            return False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "since": self._state.since,
                "where": self._state.where,
                **self._surepy_entity.raw_data(),
            }

        return attributes

    @property
    def device_info(self):
        pass

    @property
    def entity_picture(self) -> str | None:
        return self._surepy_entity.photo_url

    @callback  # type: ignore
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_entity = self._spc.states[self._id]
        self._state = self._surepy_entity.location
        # _LOGGER.debug("🐾 %s updated", self._surepy_entity.name)


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(
        self,
        _id: int,
        # sure_type: EntityType,
        spc: SurePetcareAPI,
    ) -> None:
        """Initialize a Sure Petcare Device."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY)  # , sure_type)

    # @property
    # def device_info(self):

    #     device = {
    #         "identifiers": {(DOMAIN, self._id)},
    #         "name": self._surepy_entity.name.title(),
    #         "manufacturer": SURE_MANUFACTURER,
    #         "model": self._surepy_entity.type.name.capitalize(),
    #     }

    #     if self._state:
    #         versions = self._state.get("version", {})

    #         if dev_fw_version := versions.get("device", {}).get("firmware"):
    #             device["sw_version"] = dev_fw_version

    #         if (lcd_version := versions.get("lcd", {})) and (
    #             rf_version := versions.get("rf", {})
    #         ):
    #             device[
    #                 "sw_version"
    #             ] = f"{lcd_version['version']} | {rf_version['version']}"

    #     return device

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name} Connectivity"

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._id}-connectivity"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state)

    @property
    def is_on(self) -> bool:
        """Return true if entity is online."""
        return self.available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "device_rssi": f'{self._state["signal"]["device_rssi"]:.2f}',
                "hub_rssi": f'{self._state["signal"]["hub_rssi"]:.2f}',
            }

        return attributes
