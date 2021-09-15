"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from surepy.entities import SurepyEntity
from surepy.entities.devices import Hub as SureHub, SurepyDevice
from surepy.entities.pet import Pet as SurePet
from surepy.enums import EntityType, Location

# pylint: disable=relative-beyond-top-level
from . import SurePetcareAPI
from .const import DOMAIN, SPC, SURE_MANUFACTURER

PARALLEL_UPDATES = 2


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: Any,
    discovery_info: Any = None,
) -> None:
    """Set up Sure PetCare binary-sensor platform."""
    await async_setup_entry(hass, config, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Any
) -> None:
    """Set up config entry Sure PetCare Flaps sensors."""

    entities: list[SurePetcareBinarySensor] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    for surepy_entity in spc.coordinator.data.values():

        if surepy_entity.type == EntityType.PET:
            entities.append(Pet(spc.coordinator, surepy_entity.id, spc))

        elif surepy_entity.type == EntityType.HUB:
            entities.append(Hub(spc.coordinator, surepy_entity.id, spc))

        # connectivity
        elif surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(DeviceConnectivity(spc.coordinator, surepy_entity.id, spc))

    async_add_entities(entities, True)


class SurePetcareBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A binary sensor implementation for Sure Petcare Entities."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        _id: int,
        spc: SurePetcareAPI,
        device_class: str,
    ):
        """Initialize a Sure Petcare binary sensor."""
        super().__init__(coordinator)

        self._id: int = _id
        self._spc: SurePetcareAPI = spc

        self._coordinator = coordinator

        self._surepy_entity: SurepyEntity = self._coordinator.data[self._id]
        self._state: Any = self._surepy_entity.raw_data().get("status", {})

        type_name = self._surepy_entity.type.name.replace("_", " ").title()

        self._name: str = (
            # cover edge case where a device has no name set
            # (dont know how to do this but people have managed to do it  ¯\_(ツ)_/¯)
            self._surepy_entity.name
            if self._surepy_entity.name
            else f"Unnamed {type_name}"
        )

        self._attr_available = bool(self._state)

        self._attr_device_class = None if not device_class else device_class
        self._attr_name: str = f"{type_name} {self._name}"
        self._attr_unique_id = f"{self._surepy_entity.household_id}-{self._id}"

        if self._state:
            self._attr_extra_state_attributes = {**self._surepy_entity.raw_data()}

    @property
    def device_info(self):

        device = {}

        try:

            model = f"{self._surepy_entity.type.name.replace('_', ' ').title()}"
            if serial := self._surepy_entity.raw_data().get("serial_number"):
                model = f"{model} ({serial})"
            elif mac_address := self._surepy_entity.raw_data().get("mac_address"):
                model = f"{model} ({mac_address})"
            elif tag_id := self._surepy_entity.raw_data().get("tag_id"):
                model = f"{model} ({tag_id})"

            device = {
                "identifiers": {(DOMAIN, self._id)},
                "name": self._surepy_entity.name.capitalize(),
                "manufacturer": SURE_MANUFACTURER,
                "model": model,
            }

            if self._state:
                versions = self._state.get("version", {})

                if dev_fw_version := versions.get("device", {}).get("firmware"):
                    device["sw_version"] = dev_fw_version

                if (lcd_version := versions.get("lcd", {})) and (
                    rf_version := versions.get("rf", {})
                ):
                    device["sw_version"] = (
                        f"lcd: {lcd_version.get('version', lcd_version)['firmware']} | "
                        f"fw: {rf_version.get('version', rf_version)['firmware']}"
                    )

        except AttributeError:
            pass

        return device


class Hub(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Hub."""
        super().__init__(coordinator, _id, spc, DEVICE_CLASS_CONNECTIVITY)

        if self._attr_device_info:
            self._attr_device_info["identifiers"] = {(DOMAIN, str(self._id))}

        self._attr_available = self.is_on

    @property
    def is_on(self) -> bool:
        """Return True if the hub is on."""

        hub: SureHub
        online: bool = False

        if hub := self._coordinator.data[self._id]:

            self._attr_extra_state_attributes = {
                "led_mode": int(hub.raw_data()["status"]["led_mode"]),
                "pairing_mode": bool(hub.raw_data()["status"]["pairing_mode"]),
            }

            online = hub.online

        return online


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Pet."""

        super().__init__(coordinator, _id, spc, DEVICE_CLASS_PRESENCE)

        # explicit typing
        self._surepy_entity: SurePet

        # picture of the pet that can be added via the sure app/website
        self._attr_entity_picture = self._surepy_entity.photo_url

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""

        pet: SurePet
        attrs: dict[str, Any] = {}

        if pet := self._coordinator.data[self._id]:

            attrs = {
                "since": pet.location.since,
                "where": pet.location.where,
                **pet.raw_data(),
            }

        return attrs

    @property
    def is_on(self) -> bool:
        """Return True if the pet is at home."""

        pet: SurePet
        inside: bool = False

        if pet := self._coordinator.data[self._id]:
            inside = bool(pet.location.where == Location.INSIDE)

        return inside


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Connectivity Sensor."""

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare device connectivity sensor."""

        super().__init__(coordinator, _id, spc, DEVICE_CLASS_CONNECTIVITY)

        self._attr_name = f"{self._name} Connectivity"
        self._attr_unique_id = (
            f"{self._surepy_entity.household_id}-{self._id}-connectivity"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""

        device: SurepyDevice
        attrs: dict[str, Any] = {}

        if (device := self._coordinator.data[self._id]) and (
            state := device.raw_data().get("status")
        ):
            attrs = {
                "device_rssi": f'{state["signal"]["device_rssi"]:.2f}',
                "hub_rssi": f'{state["signal"]["hub_rssi"]:.2f}',
            }

        return attrs

    @property
    def is_on(self) -> bool:
        """Return True if the pet is at home."""
        return bool(self.extra_state_attributes)
