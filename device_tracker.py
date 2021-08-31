"""Device tracker for SureHA pets."""
import logging

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import Config
from surepy.entities import EntityType
from surepy.entities.pet import Pet

# pylint: disable=relative-beyond-top-level
from . import DOMAIN, SurePetcareAPI
from .const import SPC

_LOGGER = logging.getLogger(__name__)

SOURCE_TYPE_FLAP = "flap"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Pet tracker from config entry."""

    cfg = Config(hass)
    config = cfg.as_dict()

    _LOGGER.debug("async_setup_entry: config=%s", config)
    _LOGGER.debug("async_setup_entry: config[latitude]=%s", config["latitude"])

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    async_add_entities(
        [
            SureDeviceTracker(pet.id, spc)
            for pet in spc.states.values()
            if pet.type == EntityType.PET
        ],
        True,
    )


class SureDeviceTracker(TrackerEntity):
    """Pet device tracker."""

    _attr_force_update = False
    _attr_icon = "mdi:cat"

    def __init__(self, _id: int, spc: SurePetcareAPI):
        """Initialize the tracker."""
        # super().__init__(account, vehicle)

        self._id = _id
        self._attr_unique_id = f"{self._id}-pet-tracker"

        self._location = (None, None)

        self._spc: SurePetcareAPI = spc
        self._surepy_entity: Pet = self._spc.states[self._id]
        self._attr_name = self._surepy_entity.name

    @property
    def latitude(self):
        """Return latitude value of the pet."""
        return self._location[0] if self._location else None

    @property
    def longitude(self):
        """Return longitude value of the pet."""
        return self._location[1] if self._location else None

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the pet."""
        return SOURCE_TYPE_FLAP

    def update(self):
        """Update state of the pet tracker."""
        self._location = (48.0, 9.9) if self._surepy_entity.location else (None, None)
