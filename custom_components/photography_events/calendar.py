"""A calendar entity holding the long-range planning view."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PhotographyEventsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PhotographyCalendar(coordinator, entry)])


class PhotographyCalendar(CoordinatorEntity, CalendarEntity):
    """Every scored opportunity as a calendar event, out to a year."""

    _attr_has_entity_name = True
    _attr_name = "Planning calendar"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator: PhotographyEventsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Photography Events",
            "manufacturer": "Photography Events",
        }

    def _all(self) -> list:
        return (self.coordinator.data or {}).get("opportunities") or []

    @staticmethod
    def _to_calendar_event(item) -> CalendarEvent:
        """One opportunity as a calendar entry.

        A multi-day window becomes an all-day event and a shooting window keeps
        its clock times. Home Assistant decides which is which by the type it is
        handed - dates for all-day, datetimes for timed - so a peak window that
        runs three weeks does not render as an appointment starting at 00:00 and
        ending at 23:59, and an 80-minute Milky Way window keeps the only two
        numbers that matter about it.
        """
        summary = item.title
        if item.extra.get("precision") == "season":
            summary = f"{item.title} - {item.extra.get('season_range', 'season')}"
        elif item.extra.get("duration_minutes"):
            summary = f"{item.title} ({item.extra['duration_minutes']} min)"

        description = item.detail
        locations = item.extra.get("primary_locations")
        if locations:
            description = f"{description}\n\nWhere: " + "; ".join(locations)
        gear = item.extra.get("recommended_gear") or item.gear.get("glass")
        if gear:
            description = f"{description}\n\nGear: {gear}"

        if item.planning_only or (item.end and (item.end - item.start) >= timedelta(hours=24)):
            end = (item.end or item.start).date() + timedelta(days=1)
            return CalendarEvent(
                summary=summary,
                description=description,
                location=item.zone_name,
                start=item.start.date(),
                # Calendars treat an all-day end as exclusive, so the last day
                # of a window needs the day after it to actually be included.
                end=end,
            )

        return CalendarEvent(
            summary=f"{summary} - {item.score}/100",
            description=description,
            location=item.zone_name,
            start=item.start,
            end=item.end or item.start,
        )

    @property
    def event(self) -> CalendarEvent | None:
        upcoming = self._all()
        return self._to_calendar_event(upcoming[0]) if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            self._to_calendar_event(item)
            for item in self._all()
            if item.start <= end_date and (item.end or item.start) >= start_date
        ]
