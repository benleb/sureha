"""Switch for Sure PetCare Flaps/Pets modes."""
from __future__ import annotations

import logging
import asyncio 

from typing import Any, cast

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# pylint: disable=relative-beyond-top-level
from . import DOMAIN, SurePetcareAPI
from surepy.entities import SurepyEntity
from surepy.entities.pet import Pet as SurePet
from surepy.entities.devices import SurepyDevice # Import SurepyDevice for type checking
from surepy.enums import EntityType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Sure Petcare pet mode switches."""
    spc: SurePetcareAPI = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for _id, entity in spc.coordinator.data.items():
        if isinstance(entity, SurePet):
            pet_tag_id = entity.tag_id
            pet_name = entity.name
            pet_id = entity.id

            # 1. Try to get associated_device_id from raw_data['position'] (primary method)
            associated_device_id = entity.raw_data().get('position', {}).get('device_id')
            _LOGGER.debug(f"Switch Setup: Pet {pet_name} (ID: {pet_id}) initial associated_device_id from position: {associated_device_id}")

            # 2. If primary method fails and tag_id exists, fall back to searching all FLAP devices for the tag_id
            if associated_device_id is None and pet_tag_id is not None:
                _LOGGER.debug(f"Switch Setup: associated_device_id is None for {pet_name}. Searching ALL FLAP devices for tag_id: {pet_tag_id}")
                
                found_flap_id = None # We only care about flaps for the switch

                for device_id, device_entity in spc.coordinator.data.items():
                    # Only consider flap-type devices for the switch's control
                    if isinstance(device_entity, SurepyDevice) and device_entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]:
                        device_raw_data = device_entity.raw_data()
                        if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                            for tag_entry in device_raw_data['tags']:
                                if tag_entry.get('id') == pet_tag_id:
                                    found_flap_id = device_id
                                    _LOGGER.debug(f"Switch Setup: Found tag {pet_tag_id} on FLAP device {device_entity.name} (ID: {device_id}). Prioritizing this for switch.")
                                    break # Found on a flap, prioritize this one and exit inner loop
                            if found_flap_id: # If found on a flap, no need to check other devices
                                break

                if found_flap_id:
                    associated_device_id = found_flap_id
                else:
                    _LOGGER.debug(f"Switch Setup: No associated FLAP found for {pet_name} (tag_id: {pet_tag_id}). Switch will not be created.")
                    # associated_device_id remains None if no flap is found, preventing switch creation

            # Add the switch only if a tag_id exists AND a valid associated_device_id (from a flap) was found
            if pet_tag_id is not None and associated_device_id is not None:
                _LOGGER.debug(f"Adding switch for pet {pet_name} (ID: {pet_id}, Tag ID: {pet_tag_id}, Final Device ID: {associated_device_id})")
                entities.append(SurePetModeSwitch(spc, entity))
            else:
                _LOGGER.debug(
                    f"Skipping switch for pet {pet_name} (ID: {pet_id}): tag_id ({pet_tag_id}) or final associated FLAP device_id ({associated_device_id}) is missing. "
                    f"This pet may not be linked to a flap for mode control. Full raw_data: {entity.raw_data()}"
                )

    async_add_entities(entities)


class SurePetModeSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for pet indoor/outdoor mode."""

    _attr_has_entity_name = True

    def __init__(self, spc: SurePetcareAPI, entity: SurepyEntity) -> None:
        """Initialize a Sure Pet care Pet Mode Switch."""
        self.spc = spc
        self.coordinator = spc.coordinator
        self._surepy_entity: SurePet = cast(SurePet, entity) # Ensure type for pet methods

        self._pet_id = self._surepy_entity.id
        self._tag_id = self._surepy_entity.tag_id
        
        # Determine _device_id in __init__ using the same robust logic as async_setup_entry
        self._device_id = self._surepy_entity.raw_data().get('position', {}).get('device_id')
        if self._device_id is None and self._tag_id is not None:
            found_flap_id_init = None
            for device_id, device_entity in spc.coordinator.data.items():
                if isinstance(device_entity, SurepyDevice) and device_entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]:
                    device_raw_data = device_entity.raw_data()
                    if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                        for tag_entry in device_raw_data['tags']:
                            if tag_entry.get('id') == self._tag_id:
                                found_flap_id_init = device_id
                                break
                        if found_flap_id_init:
                            break
            self._device_id = found_flap_id_init # Set _device_id to found flap ID, or None if no flap found.

        super().__init__(self.coordinator)

        self._attr_unique_id = f"{DOMAIN}.{self._surepy_entity.name.lower().replace(' ', '_')}_mode_switch"
        self._attr_name = f"{self._surepy_entity.name} Mode"
        self._attr_icon = "mdi:paw"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._pet_id)},
            "name": self._surepy_entity.name,
            "manufacturer": "Sure Petcare",
            "model": "Pet",
        }

    @property
    def is_on(self) -> bool | None:
        """Return True if pet is currently in 'Indoor Only' mode (profile_id = 3)."""
        _LOGGER.debug(f"is_on property called for {self._surepy_entity.name} (ID: {self._pet_id})")

        if not self.coordinator.data:
            _LOGGER.debug(f"is_on: Coordinator data is empty for {self._surepy_entity.name}.")
            return None

        current_pet_data: SurePet = cast(SurePet, self.coordinator.data.get(self._pet_id))

        if not current_pet_data:
            _LOGGER.debug(f"is_on: Pet {self._surepy_entity.name} (ID: {self._pet_id}) not found in coordinator data. Cannot determine switch state.")
            return None

        _LOGGER.debug(f"is_on: Pet {current_pet_data.name} (ID: {current_pet_data.id}) current raw_data: {current_pet_data.raw_data()}")


        profile_id = None
        current_pet_tag_id = current_pet_data.tag_id

        if not current_pet_tag_id:
            _LOGGER.debug(f"is_on: Pet {current_pet_data.name} (ID: {current_pet_data.id}) has no 'tag_id' in its current data. Cannot determine switch state.")
            return None

        # This _device_id will now reliably be a flap ID (or None if no flap found)
        controlling_device_data = self.coordinator.data.get(self._device_id)

        if controlling_device_data:
            _LOGGER.debug(f"is_on: Checking controlling device {controlling_device_data.name} (ID: {controlling_device_data.id}, Type: {controlling_device_data.type}) for tags.")
            device_raw_data = controlling_device_data.raw_data()
            if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                _LOGGER.debug(f"is_on: Controlling Device {controlling_device_data.name} tags: {device_raw_data['tags']}")
                for tag_entry in device_raw_data['tags']:
                    if tag_entry.get('id') == current_pet_tag_id and tag_entry.get('profile') is not None:
                        profile_id = tag_entry.get('profile')
                        _LOGGER.debug(f"is_on: Found matching tag (ID: {current_pet_tag_id}) on controlling device {controlling_device_data.name} with profile_id: {profile_id}")
                        break
            else:
                 _LOGGER.debug(f"is_on: Controlling Device {controlling_device_data.name} has no 'tags' or invalid 'tags' data.")
        else:
            _LOGGER.warning(f"is_on: Controlling device (ID: {self._device_id}) not found in coordinator data for pet {self._surepy_entity.name}. Cannot determine state.")


        is_indoor_only = profile_id == 3 if profile_id is not None else None
        _LOGGER.debug(f"is_on: Pet {current_pet_data.name} (ID: {current_pet_data.id}) final calculated profile_id: {profile_id}, returning is_on: {is_indoor_only}")
        return is_indoor_only

    async def _wait_for_profile_change(self, target_profile_id: int, max_wait_time: int = 15, polling_interval: float = 1.0) -> bool:
        """
        Polls the coordinator for the specified target profile ID until it's reflected in the data.
        Returns True if the profile changes within the timeout, False otherwise.
        """
        start_time = asyncio.get_event_loop().time()
        _LOGGER.debug(f"Starting wait for profile_id {target_profile_id} for pet {self._surepy_entity.name} on device {self._device_id}")

        while True:
            await self.coordinator.async_request_refresh()

            current_profile_id = None
            controlling_device_data = self.coordinator.data.get(self._device_id)

            if controlling_device_data:
                device_raw_data = controlling_device_data.raw_data()
                if 'tags' in device_raw_data and isinstance(device_raw_data['tags'], list):
                    for tag_entry in device_raw_data['tags']:
                        if tag_entry.get('id') == self._tag_id and tag_entry.get('profile') is not None:
                            current_profile_id = tag_entry.get('profile')
                            break

            _LOGGER.debug(f"Polling: Current profile for {self._surepy_entity.name} on device {self._device_id}: {current_profile_id}")

            if current_profile_id == target_profile_id:
                _LOGGER.debug(f"Polling: Profile changed to {target_profile_id} for {self._surepy_entity.name} within timeout.")
                return True

            if asyncio.get_event_loop().time() - start_time > max_wait_time:
                _LOGGER.warning(f"Polling: Profile for {self._surepy_entity.name} did not change to {target_profile_id} within {max_wait_time} seconds.")
                return False

            await asyncio.sleep(polling_interval)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on (set pet to 'Indoor Only' mode)."""
        if self._tag_id is None or self._device_id is None:
            _LOGGER.error(f"Failed to turn on indoor mode for {self._surepy_entity.name}: Missing tag_id ({self._tag_id}) or device_id ({self._device_id}).")
            return

        _LOGGER.debug(f"Turning ON (Indoor Only) for pet {self._surepy_entity.name} (tag_id: {self._tag_id}) on device {self._device_id}")
        await self.spc.set_pet_indoor_mode(device_id=self._device_id, tag_id=self._tag_id)

        if not await self._wait_for_profile_change(target_profile_id=3, max_wait_time=15, polling_interval=1.0):
            _LOGGER.error(f"Failed to confirm pet {self._surepy_entity.name} is in Indoor Only mode after setting within timeout.")


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (set pet to 'Outdoor' mode)."""
        if self._tag_id is None or self._device_id is None:
            _LOGGER.error(f"Failed to turn off outdoor mode for {self._surepy_entity.name}: Missing tag_id ({self._tag_id}) or device_id ({self._device_id}).")
            return

        _LOGGER.debug(f"Turning OFF (Outdoor) for pet {self._surepy_entity.name} (tag_id: {self._tag_id}) on device {self._device_id}")
        await self.spc.set_pet_outdoor_mode(device_id=self._device_id, tag_id=self._tag_id)

        if not await self._wait_for_profile_change(target_profile_id=2, max_wait_time=15, polling_interval=1.0):
            _LOGGER.error(f"Failed to confirm pet {self._surepy_entity.name} is in Outdoor mode after setting within timeout.")
