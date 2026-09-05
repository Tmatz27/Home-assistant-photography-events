"""Fetches every source on its own schedule and assembles scored opportunities.

Five external services feed this: Open-Meteo for layered cloud, eBird for rare
birds, iNaturalist for marine mammals, three hotline pages for blooms and
autumn colour, and optionally the Google Maps platform for real drive times.
Their appetites differ wildly - Open-Meteo is a CDN-backed forecast API that
will happily serve twelve requests a minute, while the Theodore Payne hotline
is a volunteer-run page that changes once a week.

So the coordinator's cycle is not the polling rate. Each service carries its own
minimum interval and its own cache in a ``Source``, and a cycle refreshes only
what is actually due. Three consequences worth knowing:

- **A restart cannot cause a stampede.** Sources are fetched in priority groups
  with a pause between them, concurrency inside a group is capped, and the
  hotline scrapers are pushed to a background task so Home Assistant's setup
  never waits on three page loads.
- **A failure costs freshness, not data.** The last good payload is kept and
  reused, and a failed source retries on a short backoff rather than waiting
  out its whole interval.
- **Nothing is fetched for a category that is switched off.**
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import events as event_builder
from . import field_reports as reports_module
from . import routing as routing_module
from . import verification as verify_module
from . import wildlife as wildlife_module
from .const import (
    ALL_CATEGORIES,
    CATEGORY_ASTRO,
    CATEGORY_BIRDS,
    CATEGORY_BLOOMS,
    CATEGORY_FOLIAGE,
    CATEGORY_MARINE,
    CATEGORY_PARKS,
    CATEGORY_RARE,
    CATEGORY_SUNSET,
    CONF_ALERT_SCORE,
    CONF_EBIRD_API_KEY,
    CONF_ENABLE_FIELD_REPORTS,
    CONF_ENABLED_CATEGORIES,
    CONF_GOOGLE_API_KEY,
    CONF_HOME_LATITUDE,
    CONF_HOME_LONGITUDE,
    CONF_MAX_DRIVE_HOURS,
    CONF_NPS_API_KEY,
    CONF_ROUTING_MODE,
    CONF_SUNSET_SCORE,
    DEFAULT_ALERT_SCORE,
    DEFAULT_HOME,
    DEFAULT_MAX_DRIVE_HOURS,
    DEFAULT_SUNSET_SCORE,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    EBIRD_REGIONS,
    INATURALIST_URL,
    MARINE_TAXA,
    MIN_INTERVAL_EBIRD,
    MIN_INTERVAL_FIELD_REPORTS,
    MIN_INTERVAL_INATURALIST,
    MIN_INTERVAL_PARK_ALERTS,
    MIN_INTERVAL_ROUTING,
    MIN_INTERVAL_TIDES,
    MIN_INTERVAL_AIR_QUALITY,
    MIN_INTERVAL_WEATHER,
    OPEN_METEO_AIR_QUALITY_URL,
    OPEN_METEO_URL,
    ROUTING_AUTO,
    ROUTING_LEGACY,
    ROUTING_OFF,
    ROUTING_ROUTES,
    TARGET_ZONES,
)
from .throttle import Source
from . import phenomena as phenomena_module
from . import weather_scoring
from .weather_scoring import build_air_quality_params, build_open_meteo_params

_LOGGER = logging.getLogger(__name__)

CALENDAR_HORIZON_DAYS = 365
ASTRO_HORIZON_DAYS = 30
MILKY_WAY_HORIZON_DAYS = 14
REQUEST_TIMEOUT = 30

# Open-Meteo sits behind a CDN and tolerates parallelism well; the others do
# not, so they are held to one request at a time.
WEATHER_CONCURRENCY = 4

# iNaturalist asks for no more than roughly one request a second sustained.
INATURALIST_SPACING_SECONDS = 1.1

# Breathing room between priority groups, so a restart does not open a dozen
# connections in the same tick.
GROUP_STAGGER_SECONDS = 2.0

# Routing is only asked about opportunities this close, and only about ones not
# already far outside the drive limit.
ROUTING_HORIZON_HOURS = 48
ROUTING_SLACK = 1.5


class PhotographyEventsCoordinator(DataUpdateCoordinator):
    """Polls every source on its own cadence and rebuilds the opportunity list."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_MINUTES),
        )
        self.entry = entry
        self._sources: dict[str, Source] = {
            "weather": Source("Open-Meteo", MIN_INTERVAL_WEATHER),
            "air_quality": Source("Open-Meteo air quality", MIN_INTERVAL_AIR_QUALITY),
            "ebird": Source("eBird", MIN_INTERVAL_EBIRD),
            "inaturalist": Source("iNaturalist", MIN_INTERVAL_INATURALIST),
            "field_reports": Source("Wildflower and colour hotlines", MIN_INTERVAL_FIELD_REPORTS),
            "routing": Source("Google routing", MIN_INTERVAL_ROUTING),
            "tides": Source("NOAA tide predictions", MIN_INTERVAL_TIDES),
            "park_alerts": Source("National Park Service alerts", MIN_INTERVAL_PARK_ALERTS),
        }
        self._routing_cache: dict[tuple[float, float], routing_module.DriveTime] = {}
        self._routing_endpoint: str | None = None
        self._cold_start = True

    # --- Configuration ------------------------------------------------------

    @property
    def _options(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    @property
    def enabled_categories(self) -> set[str]:
        configured = self._options.get(CONF_ENABLED_CATEGORIES)
        return set(configured) if configured else set(ALL_CATEGORIES)

    @property
    def max_drive_hours(self) -> float:
        return float(self._options.get(CONF_MAX_DRIVE_HOURS, DEFAULT_MAX_DRIVE_HOURS))

    @property
    def alert_score(self) -> int:
        return int(self._options.get(CONF_ALERT_SCORE, DEFAULT_ALERT_SCORE))

    @property
    def sunset_score(self) -> int:
        return int(self._options.get(CONF_SUNSET_SCORE, DEFAULT_SUNSET_SCORE))

    @property
    def home(self) -> tuple[float, float]:
        options = self._options
        latitude = options.get(CONF_HOME_LATITUDE)
        longitude = options.get(CONF_HOME_LONGITUDE)
        if latitude is not None and longitude is not None:
            return float(latitude), float(longitude)
        # Home Assistant's own configured location beats the packaged default.
        if self.hass.config.latitude and self.hass.config.longitude:
            return float(self.hass.config.latitude), float(self.hass.config.longitude)
        return DEFAULT_HOME

    @property
    def ebird_key(self) -> str:
        return (self._options.get(CONF_EBIRD_API_KEY) or "").strip()

    @property
    def google_key(self) -> str:
        return (self._options.get(CONF_GOOGLE_API_KEY) or "").strip()

    @property
    def nps_key(self) -> str:
        return (self._options.get(CONF_NPS_API_KEY) or "").strip()

    @property
    def routing_mode(self) -> str:
        return self._options.get(CONF_ROUTING_MODE, ROUTING_AUTO)

    @property
    def field_reports_enabled(self) -> bool:
        return bool(self._options.get(CONF_ENABLE_FIELD_REPORTS, True))

    # --- Update cycle -------------------------------------------------------

    async def _async_update_data(self) -> dict:
        now = dt_util.utcnow()
        categories = self.enabled_categories
        zones = [zone for zone in TARGET_ZONES if zone["drive_hours"] <= self.max_drive_hours]
        session = async_get_clientsession(self.hass)

        # Group 1: weather. Everything that can raise a drop-everything alert in
        # the next 48 hours depends on it, so it goes first and alone.
        if categories & {CATEGORY_SUNSET, CATEGORY_ASTRO}:
            await self._refresh(self._sources["weather"], now, lambda: self._fetch_forecasts(session, zones, now))
        forecasts = self._sources["weather"].value or {}
        if CATEGORY_SUNSET in categories:
            await self._refresh(self._sources["air_quality"], now, lambda: self._fetch_air_quality(session, zones))
        air_quality = self._sources["air_quality"].value or {}

        # Group 2: the wildlife APIs, spaced away from the weather burst.
        if categories & {CATEGORY_BIRDS, CATEGORY_MARINE}:
            await asyncio.sleep(GROUP_STAGGER_SECONDS)
        if CATEGORY_BIRDS in categories and self.ebird_key:
            await self._refresh(self._sources["ebird"], now, lambda: self._fetch_ebird(session))
        if CATEGORY_MARINE in categories:
            await self._refresh(self._sources["inaturalist"], now, lambda: self._fetch_inaturalist(session, now))

        # Group 3: the hotline scrapers. On a cold start they are deferred to a
        # background task, so setup never blocks on three page loads for data
        # that only changes once a week.
        if self.field_reports_enabled and categories & {CATEGORY_BLOOMS, CATEGORY_FOLIAGE}:
            if self._cold_start:
                self.hass.async_create_task(self._async_deferred_field_reports())
            else:
                await self._refresh(
                    self._sources["field_reports"], now, lambda: self._fetch_field_reports(session, now)
                )

        # Group 4: verification. Tide predictions turn a run night into an hour,
        # and park alerts are the only source that can say the road is shut.
        if CATEGORY_RARE in categories:
            await self._refresh(self._sources["tides"], now, lambda: self._fetch_tides(session, now))
        if CATEGORY_PARKS in categories and self.nps_key:
            await self._refresh(self._sources["park_alerts"], now, lambda: self._fetch_park_alerts(session))

        opportunities = await self._build(now, zones, forecasts, air_quality, categories)
        opportunities = await self._apply_routing(session, now, opportunities)

        opportunities = event_builder.within_drive(opportunities, self.max_drive_hours)
        action = event_builder.action_window(opportunities, now)
        top = next((item for item in action if event_builder.alert_candidate(item, self.alert_score)), None)
        self._cold_start = False

        return {
            "generated": now,
            "opportunities": sorted(opportunities, key=lambda item: item.start),
            "action_events": action,
            "top_action": top,
            "zone_count": len(zones),
            "forecast_zones": sorted(forecasts),
            "sources": {key: source.status() for key, source in self._sources.items()},
            "routing_endpoint": self._routing_endpoint,
        }

    async def _build(self, now, zones, forecasts, air_quality, categories) -> list:
        """Assemble opportunities. All pure CPU, so it runs off the event loop."""
        opportunities: list = []

        for zone in zones:
            bundle = forecasts.get(zone["id"]) or {}
            # A value cached from before the bundle shape existed is a flat
            # forecast. Tolerating it costs a line and saves a cycle of missing
            # sunsets after an upgrade.
            forecast = bundle.get("local") or (bundle if "hourly" in bundle else None)
            upstream = bundle.get("upstream") or {}
            cloud_lookup = _make_cloud_lookup(forecast)

            if CATEGORY_SUNSET in categories and forecast:
                opportunities.extend(
                    await self.hass.async_add_executor_job(
                        event_builder.build_sunset_opportunities,
                        zone,
                        forecast,
                        now,
                        self.sunset_score,
                        3,
                        upstream,
                        air_quality.get(zone["id"]),
                    )
                )

            if CATEGORY_ASTRO in categories:
                opportunities.extend(
                    await self.hass.async_add_executor_job(
                        event_builder.build_meteor_opportunities, zone, now, ASTRO_HORIZON_DAYS, cloud_lookup
                    )
                )
                opportunities.extend(
                    await self.hass.async_add_executor_job(
                        event_builder.build_milky_way_opportunities,
                        zone,
                        now,
                        MILKY_WAY_HORIZON_DAYS,
                        cloud_lookup,
                    )
                )

        sightings = list(self._sources["ebird"].value or []) + list(self._sources["inaturalist"].value or [])
        digested: list = []
        if sightings:
            digested = await self.hass.async_add_executor_job(wildlife_module.digest, sightings, now)
            opportunities.extend(
                await self.hass.async_add_executor_job(
                    event_builder.build_wildlife_opportunities, digested, now, self.home
                )
            )

        reports = self._sources["field_reports"].value or []
        if reports:
            opportunities.extend(
                await self.hass.async_add_executor_job(
                    event_builder.build_field_report_opportunities, reports, now
                )
            )

        # The evidence gate needs the live signals, so the phenomena are built
        # after the wildlife and hotline sources rather than in isolation.
        seasonal = await self.hass.async_add_executor_job(
            event_builder.build_seasonal_opportunities,
            now,
            CALENDAR_HORIZON_DAYS,
            self.home,
            digested if sightings else None,
            reports or None,
        )
        opportunities.extend(seasonal)

        if CATEGORY_RARE in categories:
            opportunities.extend(
                await self.hass.async_add_executor_job(
                    event_builder.build_grunion_runs,
                    now,
                    CALENDAR_HORIZON_DAYS,
                    self.home,
                    self._sources["tides"].value,
                )
            )

        if CATEGORY_PARKS in categories:
            opportunities.extend(
                await self.hass.async_add_executor_job(
                    event_builder.build_park_opportunities,
                    now,
                    CALENDAR_HORIZON_DAYS,
                    self._sources["park_alerts"].value,
                )
            )

        return [item for item in opportunities if item.category in categories]

    async def _refresh(self, source: Source, now: datetime, fetcher: Callable[[], Awaitable[Any]]) -> None:
        """Run a fetch if it is due, recording the outcome either way."""
        if not source.due(now):
            return
        try:
            source.succeed(now, await fetcher())
        except Exception as err:  # noqa: BLE001 - one dead service must not stop the rest
            source.fail(now, f"{type(err).__name__}: {err}")
            _LOGGER.warning("%s update failed (%s); keeping last known data", source.name, err)

    async def _async_deferred_field_reports(self) -> None:
        """Scrape the hotlines after setup has finished, then publish."""
        await asyncio.sleep(GROUP_STAGGER_SECONDS * 5)
        session = async_get_clientsession(self.hass)
        now = dt_util.utcnow()
        await self._refresh(self._sources["field_reports"], now, lambda: self._fetch_field_reports(session, now))
        if self._sources["field_reports"].value:
            await self.async_request_refresh()

    # --- Fetchers -----------------------------------------------------------

    async def _fetch_forecasts(self, session, zones: list[dict], now: datetime) -> dict[str, dict]:
        """Layered cloud at each zone *and* on its two light paths.

        Three coordinates go out per zone in a single request: the zone itself,
        the point 200km toward sunset, and the point 200km toward sunrise. The
        upstream pair is what makes a sky score trustworthy - the deck sitting
        offshore is what decides whether the light ever gets under the cirrus,
        and it is invisible from the zone's own forecast.

        Still one request per zone rather than one for everything, so a single
        bad response costs one zone instead of the whole map.
        """
        semaphore = asyncio.Semaphore(WEATHER_CONCURRENCY)

        async def fetch(zone: dict) -> tuple[str, dict | None]:
            probes = weather_scoring.light_path_probes(zone["latitude"], zone["longitude"], now)
            order = [key for key in ("sunset", "sunrise") if key in probes]
            latitudes = [zone["latitude"]] + [probes[key][0] for key in order]
            longitudes = [zone["longitude"]] + [probes[key][1] for key in order]
            params = build_open_meteo_params(latitudes, longitudes)
            async with semaphore:
                payload = await self._get_json(session, OPEN_METEO_URL, params=params, label=zone["name"])
            parts = weather_scoring.split_multi_location(payload)
            if not parts:
                return zone["id"], None
            bundle = {"local": parts[0], "upstream": {}}
            for index, key in enumerate(order, start=1):
                if index < len(parts):
                    bundle["upstream"][key] = parts[index]
            return zone["id"], bundle

        results = await asyncio.gather(*(fetch(zone) for zone in zones))
        found = {zone_id: payload for zone_id, payload in results if payload}
        if not found:
            # Every zone failing is a real outage, not a blip, and should show
            # up as a failed source rather than as an empty forecast set.
            raise RuntimeError("no zone returned a forecast")
        return found

    async def _fetch_air_quality(self, session, zones: list[dict]) -> dict[str, dict]:
        """Aerosol optical depth per zone - one request for the whole map.

        This decides saturation rather than whether anything happens at all, so
        unlike the forecast it is allowed to fail entirely: the score falls back
        to visibility and humidity and carries on.
        """
        if not zones:
            return {}
        params = build_air_quality_params(
            [zone["latitude"] for zone in zones],
            [zone["longitude"] for zone in zones],
        )
        payload = await self._get_json(session, OPEN_METEO_AIR_QUALITY_URL, params=params, label="air quality")
        parts = weather_scoring.split_multi_location(payload)
        return {zone["id"]: parts[index] for index, zone in enumerate(zones) if index < len(parts)}

    async def _fetch_ebird(self, session) -> list:
        """Notable observations across the covered counties, one region at a time."""
        headers = wildlife_module.build_ebird_headers(self.ebird_key)
        params = wildlife_module.build_ebird_params()
        local_tz = dt_util.DEFAULT_TIME_ZONE or timezone.utc

        sightings: list = []
        for index, region in enumerate(EBIRD_REGIONS):
            if index:
                await asyncio.sleep(0.5)
            payload = await self._get_json(
                session,
                wildlife_module.build_ebird_url(region),
                params=params,
                headers=headers,
                label=f"eBird {region}",
            )
            if payload:
                sightings.extend(wildlife_module.parse_ebird(payload, local_tz))
        return sightings

    async def _fetch_inaturalist(self, session, now: datetime) -> list:
        """Recent observations, one taxon at a time and deliberately slowly.

        The list is the union of the marine species worth a drive on their own
        and every species some peak window is waiting on for corroboration. The
        second half is derived from the windows themselves: a hand-kept list
        drifted, and the result was four windows that advertised live
        verification while nothing ever looked for them.
        """
        headers = wildlife_module.build_inaturalist_headers()
        local_tz = dt_util.DEFAULT_TIME_ZONE or timezone.utc
        taxa = list(dict.fromkeys((*MARINE_TAXA, *phenomena_module.corroboration_taxa())))

        sightings: list = []
        for index, taxon in enumerate(taxa):
            if index:
                await asyncio.sleep(INATURALIST_SPACING_SECONDS)
            payload = await self._get_json(
                session,
                INATURALIST_URL,
                params=wildlife_module.build_inaturalist_params(taxon, now),
                headers=headers,
                label=f"iNaturalist {taxon}",
            )
            if payload:
                sightings.extend(wildlife_module.parse_inaturalist(payload, local_tz))
        return sightings

    async def _fetch_field_reports(self, session, now: datetime) -> list:
        """Scrape the three hotlines, one at a time, once a day."""
        found: list = []
        for index, source in enumerate(reports_module.REPORT_SOURCES):
            if index:
                await asyncio.sleep(GROUP_STAGGER_SECONDS)
            markup = await self._get_text(session, source["url"], label=source["name"])
            if not markup:
                continue
            try:
                found.extend(
                    await self.hass.async_add_executor_job(reports_module.parse_report, markup, source, now)
                )
            except Exception:  # noqa: BLE001 - a layout change must not break the update
                _LOGGER.warning("Could not parse %s; skipping it this cycle", source["name"], exc_info=True)
        return found

    async def _fetch_tides(self, session, now: datetime) -> list:
        """High and low water for the stations the coastal plans depend on."""
        local_tz = dt_util.DEFAULT_TIME_ZONE or timezone.utc
        start = now.date() - timedelta(days=1)
        end = start + timedelta(days=45)

        found: list = []
        for index, station in enumerate(verify_module.TIDE_STATIONS.values()):
            if index:
                await asyncio.sleep(0.5)
            url, params = verify_module.build_tide_request(station["station"], start, end)
            payload = await self._get_json(session, url, params=params, label=f"NOAA {station['name']}")
            if payload:
                found.extend(verify_module.parse_tide_predictions(payload, local_tz))
        if not found:
            raise RuntimeError("no tide predictions returned")
        return sorted(found, key=lambda tide: tide.moment)

    async def _fetch_park_alerts(self, session) -> list:
        """Closures and warnings straight from the parks."""
        url, params = verify_module.build_nps_alerts_request(
            list(verify_module.NPS_PARK_CODES.values()), self.nps_key
        )
        payload = await self._get_json(session, url, params=params, label="NPS alerts")
        if payload is None:
            raise RuntimeError("NPS alerts unavailable")
        return verify_module.parse_nps_alerts(payload)

    # --- Google routing -----------------------------------------------------

    async def _apply_routing(self, session, now: datetime, opportunities: list) -> list:
        """Replace estimated drive times with routed ones where it matters."""
        key = self.google_key
        if not key or self.routing_mode == ROUTING_OFF or not opportunities:
            return opportunities

        horizon = now + timedelta(hours=ROUTING_HORIZON_HOURS)
        candidates = [
            item
            for item in opportunities
            if item.start <= horizon
            and item.drive_hours <= self.max_drive_hours * ROUTING_SLACK
            and _point(item) is not None
        ]
        if not candidates:
            return opportunities

        # Deduplicate before spending quota: a dozen opportunities at one zone
        # is one billable element, not a dozen.
        wanted = list(dict.fromkeys(_point(item) for item in candidates))
        unknown = [point for point in wanted if point not in self._routing_cache]
        if unknown:
            await self._refresh(
                self._sources["routing"], now, lambda: self._fetch_routing(session, unknown, key)
            )

        for item in candidates:
            routed = self._routing_cache.get(_point(item))
            if routed is None:
                continue
            item.drive_hours = round(routed.hours, 2)
            item.drive_source = routed.source
            item.drive_in_traffic = routed.in_traffic
            note = f"{routed.minutes} min by road" + (" in current traffic" if routed.in_traffic else "")
            if note not in item.reasons:
                item.reasons.append(note)
        return opportunities

    async def _fetch_routing(self, session, points: list[tuple[float, float]], key: str) -> int:
        """Fill the routing cache, trying the modern endpoint before the legacy one.

        Which endpoint a key can call is a property of the Google Cloud project,
        not of this code: Distance Matrix cannot be enabled on projects created
        after March 2025, and Routes may never have been enabled on older ones.
        Rather than make you discover that by reading an error, both are tried
        and whichever answers is remembered for next time.
        """
        origin = self.home
        order = {
            ROUTING_AUTO: (ROUTING_ROUTES, ROUTING_LEGACY),
            ROUTING_ROUTES: (ROUTING_ROUTES,),
            ROUTING_LEGACY: (ROUTING_LEGACY,),
        }.get(self.routing_mode, (ROUTING_ROUTES, ROUTING_LEGACY))
        if self._routing_endpoint in order:
            order = (self._routing_endpoint,) + tuple(e for e in order if e != self._routing_endpoint)

        filled = 0
        for batch in routing_module.chunk_destinations(points):
            for endpoint in order:
                results = await self._route_batch(session, endpoint, origin, batch, key)
                if not results:
                    continue
                self._routing_endpoint = endpoint
                for index, drive in results.items():
                    if 0 <= index < len(batch):
                        self._routing_cache[batch[index]] = drive
                        filled += 1
                break

        if not filled:
            raise RuntimeError(
                "Google returned no usable routes - check the key and that either "
                "the Routes API or the Distance Matrix API is enabled for it"
            )
        return filled

    async def _route_batch(self, session, endpoint: str, origin, batch: list, key: str) -> dict:
        if endpoint == ROUTING_ROUTES:
            url, headers, body = routing_module.build_routes_request(origin, batch, key)
            payload = await self._post_json(session, url, headers=headers, json_body=body, label="Routes API")
            return routing_module.parse_routes_response(payload) if payload is not None else {}

        url, params = routing_module.build_legacy_request(origin, batch, key)
        payload = await self._get_json(session, url, params=params, label="Distance Matrix")
        return routing_module.parse_legacy_response(payload) if payload is not None else {}

    # --- HTTP helpers -------------------------------------------------------

    async def _get_json(self, session, url: str, *, params=None, headers=None, label: str = "") -> Any:
        return await self._request(session, "get", url, params=params, headers=headers, label=label, as_json=True)

    async def _get_text(self, session, url: str, *, label: str = "") -> str | None:
        return await self._request(session, "get", url, label=label, as_json=False)

    async def _post_json(self, session, url: str, *, headers=None, json_body=None, label: str = "") -> Any:
        return await self._request(
            session, "post", url, headers=headers, json_body=json_body, label=label, as_json=True
        )

    async def _request(
        self,
        session,
        method: str,
        url: str,
        *,
        params=None,
        headers=None,
        json_body=None,
        label: str = "",
        as_json: bool = True,
    ) -> Any:
        """One request, returning None on any failure rather than raising.

        Individual requests fail quietly on purpose: one dead region or one
        unreachable hotline should cost that one result, and the enclosing
        ``Source`` decides whether the service as a whole counts as failed.
        """
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await session.request(method, url, params=params, headers=headers, json=json_body)
                if response.status != 200:
                    _LOGGER.debug("%s returned HTTP %s", label or url, response.status)
                    return None
                if as_json:
                    # Several of these answer with a JSON body under a
                    # text/plain content type, so the check is waived.
                    return await response.json(content_type=None)
                return await response.text()
        except (TimeoutError, asyncio.CancelledError):
            _LOGGER.debug("%s timed out", label or url)
            return None
        except Exception:  # noqa: BLE001 - never let one request break a cycle
            _LOGGER.debug("%s request failed", label or url, exc_info=True)
            return None


def _point(item) -> tuple[float, float] | None:
    """Routing key for an opportunity: its coordinates, rounded.

    Three decimal places is about 100 m - finer than any drive time is
    meaningful at, and coarse enough that everything happening at one zone
    collapses into a single billable element.
    """
    if item.latitude is None or item.longitude is None:
        return None
    return round(float(item.latitude), 3), round(float(item.longitude), 3)


def _make_cloud_lookup(forecast: dict | None):
    """Total cloud cover nearest a moment, or None when there is no forecast."""
    if not forecast:
        return None
    hourly = forecast.get("hourly", {})
    times = hourly.get("time") or []
    clouds = hourly.get("cloud_cover") or []
    if not times or not clouds:
        return None

    parsed: list[tuple[float, float]] = []
    for stamp, value in zip(times, clouds):
        if not isinstance(value, (int, float)):
            continue
        try:
            moment = datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        parsed.append((moment.timestamp(), float(value)))

    if not parsed:
        return None

    def lookup(moment: datetime) -> float | None:
        target = moment.timestamp()
        stamp, value = min(parsed, key=lambda item: abs(item[0] - target))
        return value if abs(stamp - target) <= 5400 else None

    return lookup
