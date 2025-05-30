"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
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

    spc: SurePetcareAPI = hass.data[DOMAIN][config_entry.entry_id]

    for surepy_entity in spc.coordinator.data.values():

        if surepy_entity.type == EntityType.PET:
            entities.append(Pet(spc.coordinator, surepy_entity.id, spc))

        elif surepy_entity.type == EntityType.HUB and surepy_entity.raw_data().get("status", {}).get("led_mode", {}):
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
            # (dont know how to do this but people have managed to do it ¯\_(ツ)_/¯)
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
        super().__init__(coordinator, _id, spc, BinarySensorDeviceClass.CONNECTIVITY)

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

        super().__init__(coordinator, _id, spc, BinarySensorDeviceClass.PRESENCE)

        # explicit typing
        self._surepy_entity: SurePet
        self._pet_id = _id # Store pet ID
        self._tag_id = self._surepy_entity.tag_id # Store tag ID

        # Get _device_id from raw_data['position']
        # This ensures we identify the controlling device (e.g., flap) for this pet.
        self._device_id = self._surepy_entity.raw_data().get('position', {}).get('device_id')

        # picture of the pet that can be added via the sure app/website
        self._attr_entity_picture = self._surepy_entity.photo_url

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""

        pet: SurePet = self._coordinator.data.get(self._pet_id) # Use .get() for safer access
        if not pet:
            _LOGGER.debug(f"DEBUG: Pet {self._pet_id} not found in coordinator data for extra_state_attributes.")
            return {} # Return empty if pet data is missing

        attrs: dict[str, Any] = {
            "since": pet.location.since,
            "where": pet.location.where,
            **pet.raw_data(), # Keep this to include other raw data from the pet
        }
        profile_id = None # Initialize profile_id to None

        # Use the stored _tag_id for consistency
        pet_tag_id = self._tag_id
        if not pet_tag_id:
            _LOGGER.debug(f"DEBUG: Pet {pet.name} (ID: {pet.id}) has no 'tag_id' associated. Cannot determine profile_id.")
            return attrs # No tag_id means no profile_id can be found this way

        # Prioritize checking the specific controlling device (flap/feeder) first
        # This is the same logic that fixed the switch's state.
        if self._device_id: # Only proceed if we have a controlling device ID
            controlling_device_data = self.coordinator.data.get(self._device_id)

            if controlling_device_data and 'tags' in controlling_device_data.raw_data() and isinstance(controlling_device_data.raw_data()['tags'], list):
                _LOGGER.debug(f"DEBUG: Checking PRIMARY controlling device {controlling_device_data.name} (ID: {controlling_device_data.id}, Type: {controlling_device_data.type}) for pet tag {pet_tag_id}.")
                for tag_entry in controlling_device_data.raw_data()['tags']:
                    if tag_entry.get('id') == pet_tag_id and tag_entry.get('profile') is not None:
                        profile_id = tag_entry.get('profile')
                        _LOGGER.debug(f"DEBUG: Found profile_id {profile_id} for pet {pet.name} from PRIMARY device {controlling_device_data.name}.")
                        break # Found the profile on the primary device, no need to search further

        # If profile_id is still not found after checking the primary controlling device,
        # fallback to iterating all other relevant devices (less efficient, but covers edge cases)
        if profile_id is None:
            _LOGGER.debug(f"DEBUG: Profile for {pet.name} not found on primary device {self._device_id}. Falling back to searching all relevant devices for tags.")
            for entity_obj in self._coordinator.data.values():
                # Only check devices that are flaps/feeders and are NOT the primary controlling device
                if entity_obj.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP, EntityType.FEEDER] and entity_obj.id != self._device_id:
                    device_raw_data = entity_obj.raw_data()
                    if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                        for tag_entry in device_raw_data['tags']:
                            if tag_entry.get('id') == pet_tag_id and tag_entry.get('profile') is not None:
                                profile_id = tag_entry.get('profile')
                                _LOGGER.debug(f"DEBUG: Found profile_id {profile_id} for pet {pet.name} from SECONDARY device {entity_obj.name} (ID: {entity_obj.id}).")
                                break # Found the profile, exit inner loop
                        if profile_id is not None:
                            break # Found the profile, exit outer loop (device loop)

        # Assign profile_id and pet_mode if a valid profile_id was found
        if profile_id is not None:
            attrs["profile_id"] = profile_id
            if profile_id == 3:
                attrs["pet_mode"] = "Indoor Only"
            elif profile_id == 2:
                attrs["pet_mode"] = "Outdoor"
            else:
                # Handle other potential profile_ids if they exist and are meaningful
                attrs["pet_mode"] = f"Unknown Profile (ID: {profile_id})"
        else:
            _LOGGER.debug(f"DEBUG: Could not find profile_id for pet {pet.name} (ID: {pet.id}) after searching all relevant devices.")

        return attrs

    @property
    def is_on(self) -> bool:
        """Return True if the pet is at home."""
        pet: SurePet
        inside: bool = False

        if pet := self._coordinator.data.get(self._id): # Use .get() for safer access
            inside = bool(pet.location.where == Location.INSIDE)

        return inside


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Connectivity Sensor."""

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare device connectivity sensor."""

        super().__init__(coordinator, _id, spc, BinarySensorDeviceClass.CONNECTIVITY)

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
            state := device.raw_data().get("status", {})
        ) and (bool(state.get("online", False))):
            device_rssi = state.get("signal", {}).get("device_rssi")
            self._attr_extra_state_attributes["device_rssi"] = f"{device_rssi:.2f}" if device_rssi else "Unknown"
            hub_rssi = state.get("signal", {}).get("hub_rssi")
            if hub_rssi is not None:
                self._attr_extra_state_attributes["hub_rssi"] = f"{hub_rssi:.2f}"

            attrs = {
                "device_rssi": device_rssi,
                "hub_rssi": hub_rssi,
            }

        return attrs

    @property
    def is_on(self) -> bool:
        """Return True if the pet is at home."""
        return bool(self.extra_state_attributes)
