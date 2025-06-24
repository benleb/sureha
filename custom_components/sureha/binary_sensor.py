"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

import logging
from typing import Any, cast

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

        self._surepy_entity: SurepyEntity = self._coordinator.data[_id]
        self._state: Any = self._surepy_entity.raw_data().get("status", {})

        type_name = self._surepy_entity.type.name.replace("_", " ").title()

        self._name: str = (
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
        self._surepy_entity: SurePet = cast(SurePet, self._surepy_entity) # Cast here for type hints

        self._pet_id = _id # Store pet ID
        self._tag_id = self._surepy_entity.tag_id # Store tag ID
        self._spc = spc # Store spc for access to coordinator.data in __init__

        # --- REVISED LOGIC FOR _device_id in Pet Binary Sensor ---
        # Determine _device_id in __init__ using the same robust logic as switch.py
        # Prioritize flap association for mode control, as per user's requirement.
        self._device_id = self._surepy_entity.raw_data().get('position', {}).get('device_id')
        _LOGGER.debug(f"Pet Binary Sensor Setup: Pet {self._surepy_entity.name} (ID: {self._pet_id}) initial _device_id from position: {self._device_id}")

        if self._device_id is None and self._tag_id is not None:
            _LOGGER.debug(f"Pet Binary Sensor Setup: _device_id is None for {self._surepy_entity.name}. Searching ALL FLAP devices for tag_id: {self._tag_id}")
            
            found_flap_id_init = None
            for device_id, device_entity in spc.coordinator.data.items():
                if isinstance(device_entity, SurepyDevice) and device_entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]:
                    device_raw_data = device_entity.raw_data()
                    if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                        for tag_entry in device_raw_data['tags']:
                            if tag_entry.get('id') == self._tag_id:
                                found_flap_id_init = device_id
                                _LOGGER.debug(f"Pet Binary Sensor Setup: Found tag {self._tag_id} on FLAP device {device_entity.name} (ID: {device_id}). Prioritizing this for _device_id.")
                                break
                        if found_flap_id_init:
                            break
            self._device_id = found_flap_id_init # Set _device_id to found flap ID, or None if no flap found.
            _LOGGER.debug(f"Pet Binary Sensor Setup: Final _device_id for {self._surepy_entity.name}: {self._device_id}")
        # --- END REVISED LOGIC ---

        # picture of the pet that can be added via the sure app/website
        self._attr_entity_picture = self._surepy_entity.photo_url

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""

        pet: SurePet = cast(SurePet, self._coordinator.data.get(self._pet_id))
        if not pet:
            _LOGGER.debug(f"DEBUG: Pet {self._pet_id} not found in coordinator data for extra_state_attributes.")
            return {} 

        attrs: dict[str, Any] = {
            "since": pet.location.since,
            "where": pet.location.where,
            **pet.raw_data(), 
        }
        profile_id = None 

        pet_tag_id = self._tag_id
        if not pet_tag_id:
            _LOGGER.debug(f"DEBUG: Pet {pet.name} (ID: {pet.id}) has no 'tag_id' associated. Cannot determine profile_id.")
            return attrs 


        # Use the _device_id determined in __init__ (which prioritizes flaps)
        if self._device_id: 
            controlling_device_data = self._spc.coordinator.data.get(self._device_id)

            if controlling_device_data:
                _LOGGER.debug(f"DEBUG: Checking PRIMARY controlling device {controlling_device_data.name} (ID: {controlling_device_data.id}, Type: {controlling_device_data.type}) for pet tag {pet_tag_id}.")
                device_raw_data = controlling_device_data.raw_data()
                if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                    for tag_entry in device_raw_data['tags']:
                        if tag_entry.get('id') == pet_tag_id and tag_entry.get('profile') is not None:
                            profile_id = tag_entry.get('profile')
                            _LOGGER.debug(f"DEBUG: Found profile_id {profile_id} for pet {pet.name} from PRIMARY device {controlling_device_data.name}.")
                            break 
                else:
                     _LOGGER.debug(f"DEBUG: Controlling Device {controlling_device_data.name} has no 'tags' or invalid 'tags' data.")
            else:
                _LOGGER.warning(f"DEBUG: Controlling device (ID: {self._device_id}) not found in coordinator data for pet {self._surepy_entity.name}. Cannot determine state.")


        # Fallback to iterating all *relevant* devices (flaps and feeders) for attributes
        # This fallback for attributes should still check feeders, as they also have profiles
        # but the primary lookup ensures the most relevant device (flap) is checked first
        if profile_id is None:
            _LOGGER.debug(f"DEBUG: Profile for {pet.name} not found on primary device {self._device_id}. Falling back to searching all relevant devices for tags.")
            for entity_obj in self._spc.coordinator.data.values(): 
                if isinstance(entity_obj, SurepyDevice) and entity_obj.id != self._device_id:
                    # Check both flaps and feeders for profile attributes
                    if entity_obj.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP, EntityType.FEEDER]:
                        device_raw_data = entity_obj.raw_data()
                        if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                            for tag_entry in device_raw_data['tags']:
                                if tag_entry.get('id') == pet_tag_id and tag_entry.get('profile') is not None:
                                    profile_id = tag_entry.get('profile')
                                    _LOGGER.debug(f"DEBUG: Found profile_id {profile_id} for pet {pet.name} from SECONDARY device {entity_obj.name} (ID: {entity_obj.id}).")
                                    break 
                            if profile_id is not None:
                                break 

        # Assign profile_id and pet_mode if a valid profile_id was found
        if profile_id is not None:
            attrs["profile_id"] = profile_id
            if profile_id == 3:
                attrs["pet_mode"] = "Indoor Only"
            elif profile_id == 2:
                attrs["pet_mode"] = "Outdoor"
            else:
                attrs["pet_mode"] = f"Unknown Profile (ID: {profile_id})"
        else:
            _LOGGER.debug(f"DEBUG: Could not find profile_id for pet {pet.name} (ID: {pet.id}) after searching all relevant devices.")

        return attrs

    @property
    def is_on(self) -> bool:
        """Return True if the pet is at home."""

        pet: SurePet
        inside: bool = False

        if pet := cast(SurePet, self._coordinator.data.get(self._id)): 
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

        if (device := cast(SurepyDevice, self._coordinator.data.get(self._id))) and ( # Use .get() for safer access
            state := device.raw_data().get("status")
        ) and (bool(state.get("online", False))):
            device_rssi = state.get("signal", {}).get("device_rssi")
            # Ensure _attr_extra_state_attributes is initialized if it wasn't by base class
            if not hasattr(self, '_attr_extra_state_attributes'):
                self._attr_extra_state_attributes = {}
            self._attr_extra_state_attributes["device_rssi"] = f"{device_rssi:.2f}" if device_rssi is not None else "Unknown" # Check for None
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
        # It's safer to directly check the 'online' status for connectivity, not just extra_state_attributes
        device = cast(SurepyDevice, self._coordinator.data.get(self._id))
        if device and (status := device.raw_data().get("status")):
            return bool(status.get("online", False))
        return False # Default to False if data is missing or device is not online
