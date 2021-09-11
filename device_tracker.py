"""Device tracker for SureHA pets."""
import logging
from typing import Any

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from surepy.entities import EntityType
from surepy.entities.pet import Pet as SurePet
from surepy.enums import Location

# pylint: disable=relative-beyond-top-level
from . import DOMAIN, SurePetcareAPI
from .const import SPC

_LOGGER = logging.getLogger(__name__)

SOURCE_TYPE_FLAP = "flap"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Pet tracker from config entry."""

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    async_add_entities(
        [
            SureDeviceTracker(spc.coordinator, pet.id, spc)
            for pet in spc.coordinator.data.values()
            if pet.type == EntityType.PET
        ],
        True,
    )


class SureDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Pet device tracker."""

    _attr_force_update = False
    _attr_icon = "mdi:cat"

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI):
        """Initialize the tracker."""
        super().__init__(coordinator)

        self._spc: SurePetcareAPI = spc
        self._coordinator = coordinator

        self._id = _id
        self._attr_unique_id = f"{self._id}-pet-tracker"

        self._surepy_entity: SurePet = self._coordinator.data[self._id]
        type_name = self._surepy_entity.type.name.replace("_", " ").title()
        name: str = (
            # cover edge case where a device has no name set
            # (dont know how to do this but people have managed to do it  ¯\_(ツ)_/¯)
            self._surepy_entity.name
            if self._surepy_entity.name
            else f"Unnamed {type_name}"
        )

        self._attr_name: str = f"{type_name} {name}"

        # picture of the pet that can be added via the sure app/website
        self._attr_entity_picture = self._surepy_entity.photo_url

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return bool(self.location_name == "home")

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
    def location_name(self) -> str:
        """Return 'home' if the pet is at home."""

        pet: SurePet
        inside: bool = False

        if pet := self._coordinator.data[self._id]:
            inside = bool(pet.location.where == Location.INSIDE)

        return "home" if inside else "not_home"

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the pet."""
        return SOURCE_TYPE_FLAP
