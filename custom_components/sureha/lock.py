"""Support for Sure PetCare flap locks.

Like the official Sure Petcare integration, every cat/pet flap gets three lock
entities: "locked in", "locked out" and "locked all". Locking one of them puts
the flap in that mode; unlocking the active one unlocks the flap.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from surepy.entities import SurepyEntity
from surepy.enums import EntityType, LockState
from surepy.exceptions import SurePetcareError

# pylint: disable=relative-beyond-top-level
from . import SurePetcareAPI
from .const import DOMAIN, SPC

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

LOCK_STATES = (LockState.LOCKED_IN, LockState.LOCKED_OUT, LockState.LOCKED_ALL)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sure PetCare flap locks."""

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    async_add_entities(
        SurePetcareLock(spc.coordinator, surepy_entity.id, spc, lock_state)
        for surepy_entity in spc.entities
        if surepy_entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]
        for lock_state in LOCK_STATES
    )


class SurePetcareLock(CoordinatorEntity, LockEntity):
    """One lock mode of a Sure Petcare flap."""

    _attr_should_poll = False

    def __init__(
        self, coordinator, _id: int, spc: SurePetcareAPI, lock_state: LockState
    ) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)

        self._id = _id
        self._spc = spc
        self._lock_state = lock_state

        surepy_entity: SurepyEntity = coordinator.data[_id]
        type_name = surepy_entity.type.name.replace("_", " ").title()
        name = surepy_entity.name or f"Unnamed {type_name}"
        mode = lock_state.name.lower()

        # same naming as the official integration (e.g. lock.<flap>_locked_in)
        self._attr_name = f"{name} {mode.replace('_', ' ')}"
        self._attr_unique_id = f"{surepy_entity.household_id}-{_id}-{mode}"
        self._attr_icon = {
            LockState.LOCKED_IN: "mdi:home-import-outline",
            LockState.LOCKED_OUT: "mdi:home-export-outline",
            LockState.LOCKED_ALL: "mdi:lock",
        }[lock_state]
        # attach to the flap device created by the sensors
        self._attr_device_info = {"identifiers": {(DOMAIN, _id)}}

    @property
    def _status(self) -> dict[str, Any]:
        if self.coordinator.data and (entity := self.coordinator.data.get(self._id)):
            return entity.raw_data().get("status") or {}
        return {}

    @property
    def _current_mode(self) -> LockState | None:
        mode = (self._status.get("locking") or {}).get("mode")
        try:
            return LockState(mode) if mode is not None else None
        except ValueError:
            return None

    @property
    def available(self) -> bool:
        """Return True if the flap is online and its lock mode is known."""
        return (
            super().available
            and bool(self._status.get("online"))
            and self._current_mode is not None
        )

    @property
    def is_locked(self) -> bool | None:
        """Return True if the flap is in this lock mode."""
        if (mode := self._current_mode) is None:
            return None
        return mode == self._lock_state

    async def _async_set_mode(self, mode: LockState) -> None:
        try:
            await self._spc.set_lock_state(self._id, mode.name.lower())
        except SurePetcareError as error:
            raise HomeAssistantError(
                f"Unable to set {self.name} to {mode.name.lower()}: {error}"
            ) from error

        # update all lock entities of the flap right away, then confirm with
        # the next refresh from the Sure Petcare API
        if (locking := self._status.get("locking")) is not None:
            locking["mode"] = mode.value
            self.coordinator.async_update_listeners()

        await self.coordinator.async_request_refresh()

    async def async_lock(self, **kwargs: Any) -> None:
        """Put the flap in this lock mode."""
        if self.is_locked:
            return

        self._attr_is_locking = True
        self.async_write_ha_state()
        try:
            await self._async_set_mode(self._lock_state)
        finally:
            self._attr_is_locking = False
            self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the flap, if this lock mode is the active one."""
        if not self.is_locked:
            return

        self._attr_is_unlocking = True
        self.async_write_ha_state()
        try:
            await self._async_set_mode(LockState.UNLOCKED)
        finally:
            self._attr_is_unlocking = False
            self.async_write_ha_state()
