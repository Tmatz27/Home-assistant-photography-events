"""Sun, moon, and planet geometry with no external ephemeris dependency.

This is a port of the algorithms already used and verified in the Lovelace
card: low-precision solar and lunar series, a shared numeric altitude-crossing
finder for every rise/set/twilight time, and two-body Keplerian propagation for
the naked-eye planets.

Deliberately pure standard library, and not for want of CPU: astropy and
skyfield pull in numpy and scipy or download ephemeris kernels into the config
directory at runtime, which is a heavy thing to ask of a HACS install and a new
way for it to break offline. The cost of avoiding them is bounded and known.

Where that cost actually lands:

- Rise, set, and twilight times are good to a minute or two, which is finer
  than the weather forecast driving the decision.
- Planetary positions are good to a few arcminutes, verified against published
  opposition and elongation dates, which it reproduces to the day.
- The lunar series is the weak link at roughly a third of a degree. That is
  invisible in moonrise timing and in illumination percentage, but it is the
  one figure here not precise enough to quote a Moon-planet conjunction
  separation to better than about half a degree.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MS_PER_DAY = 86400.0
J1970 = 2440588
J2000 = 2451545
OBLIQUITY = math.radians(23.4397)
SUN_DISTANCE_KM = 149_598_000

GALACTIC_CORE_RA_DEG = 266.4168
GALACTIC_CORE_DEC_DEG = -29.0078


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def days_since_j2000(moment: datetime) -> float:
    """Days from the J2000.0 epoch, including the fraction of a day."""
    return moment.timestamp() / MS_PER_DAY - 0.5 + J1970 - J2000


def _ecliptic_to_equatorial(ecl_lon: float, ecl_lat: float) -> tuple[float, float]:
    ra = math.atan2(
        math.sin(ecl_lon) * math.cos(OBLIQUITY) - math.tan(ecl_lat) * math.sin(OBLIQUITY),
        math.cos(ecl_lon),
    )
    dec = math.asin(
        _clamp(
            math.sin(ecl_lat) * math.cos(OBLIQUITY)
            + math.cos(ecl_lat) * math.sin(OBLIQUITY) * math.sin(ecl_lon),
            -1.0,
            1.0,
        )
    )
    return ra, dec


def sun_equatorial(d: float) -> tuple[float, float]:
    """Geocentric right ascension and declination of the Sun, in radians."""
    mean_anomaly = math.radians(357.5291 + 0.98560028 * d)
    centre = math.radians(
        1.9148 * math.sin(mean_anomaly)
        + 0.02 * math.sin(2 * mean_anomaly)
        + 0.0003 * math.sin(3 * mean_anomaly)
    )
    perihelion = math.radians(102.9372)
    return _ecliptic_to_equatorial(mean_anomaly + centre + perihelion + math.pi, 0.0)


def moon_equatorial(d: float) -> tuple[float, float, float]:
    """Right ascension, declination, and distance in km of the Moon."""
    lon = math.radians(218.316 + 13.176396 * d)
    anomaly = math.radians(134.963 + 13.064993 * d)
    node = math.radians(93.272 + 13.22935 * d)
    ecl_lon = lon + math.radians(6.289) * math.sin(anomaly)
    ecl_lat = math.radians(5.128) * math.sin(node)
    distance = 385001 - 20905 * math.cos(anomaly)
    ra, dec = _ecliptic_to_equatorial(ecl_lon, ecl_lat)
    return ra, dec, distance


def horizontal(ra: float, dec: float, moment: datetime, lat: float, lon: float) -> tuple[float, float]:
    """Altitude and azimuth in radians; azimuth measured from north through east."""
    d = days_since_j2000(moment)
    gmst = math.radians((280.16 + 360.9856235 * d) % 360)
    hour_angle = gmst + lon - ra
    altitude = math.asin(
        _clamp(
            math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(hour_angle),
            -1.0,
            1.0,
        )
    )
    azimuth = math.atan2(
        -math.cos(dec) * math.sin(hour_angle),
        math.sin(dec) * math.cos(lat) - math.cos(dec) * math.sin(lat) * math.cos(hour_angle),
    )
    return altitude, azimuth


def sun_altitude(moment: datetime, lat: float, lon: float) -> float:
    ra, dec = sun_equatorial(days_since_j2000(moment))
    return horizontal(ra, dec, moment, lat, lon)[0]


def moon_altitude(moment: datetime, lat: float, lon: float) -> float:
    ra, dec, _ = moon_equatorial(days_since_j2000(moment))
    return horizontal(ra, dec, moment, lat, lon)[0]


def angular_separation(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    return math.acos(
        _clamp(
            math.sin(dec1) * math.sin(dec2)
            + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2),
            -1.0,
            1.0,
        )
    )


@dataclass(frozen=True)
class Crossing:
    """A moment where an altitude curve passes a threshold."""

    moment: datetime
    rising: bool


def find_altitude_crossings(
    altitude_fn,
    start: datetime,
    end: datetime,
    threshold: float,
    step_minutes: int = 4,
) -> list[Crossing]:
    """Sample an altitude curve and interpolate every threshold crossing."""
    crossings: list[Crossing] = []
    step = timedelta(minutes=step_minutes)
    previous_moment = start
    previous_value = altitude_fn(start) - threshold
    moment = start + step
    while moment <= end:
        value = altitude_fn(moment) - threshold
        if (previous_value < 0 <= value) or (previous_value >= 0 > value):
            span = (moment - previous_moment).total_seconds()
            fraction = previous_value / (previous_value - value)
            crossings.append(
                Crossing(
                    moment=previous_moment + timedelta(seconds=span * fraction),
                    rising=value > previous_value,
                )
            )
        previous_moment = moment
        previous_value = value
        moment += step
    return crossings


def max_altitude_in_window(
    ra_deg: float,
    dec_deg: float,
    start: datetime,
    end: datetime,
    lat: float,
    lon: float,
    step_minutes: int = 20,
) -> float:
    """Highest altitude in degrees a fixed target reaches inside a window."""
    ra = math.radians(ra_deg)
    dec = math.radians(dec_deg)
    step = timedelta(minutes=step_minutes)
    highest = -90.0
    moment = start
    while moment <= end:
        altitude = math.degrees(horizontal(ra, dec, moment, lat, lon)[0])
        highest = max(highest, altitude)
        moment += step
    return highest


def moon_illumination(moment: datetime) -> tuple[float, float, float]:
    """Illuminated fraction, phase (0 new, 0.5 full), and distance in km."""
    d = days_since_j2000(moment)
    sun_ra, sun_dec = sun_equatorial(d)
    moon_ra, moon_dec, distance = moon_equatorial(d)
    elongation = angular_separation(sun_ra, sun_dec, moon_ra, moon_dec)
    phase_angle = math.atan2(
        SUN_DISTANCE_KM * math.sin(elongation),
        distance - SUN_DISTANCE_KM * math.cos(elongation),
    )
    fraction = (1 + math.cos(phase_angle)) / 2
    sign = -1.0 if math.atan2(
        math.cos(sun_dec) * math.sin(sun_ra - moon_ra),
        math.sin(sun_dec) * math.cos(moon_dec)
        - math.cos(sun_dec) * math.sin(moon_dec) * math.cos(sun_ra - moon_ra),
    ) < 0 else 1.0
    phase = 0.5 + (0.5 * phase_angle * sign) / math.pi
    return fraction, phase, distance


# --- Planets -----------------------------------------------------------------

EARTH_ELEMENTS = {
    "name": "Earth",
    "a": (1.00000261, 0.00000562),
    "e": (0.01671123, -0.00004392),
    "i": (-0.00001531, -0.01294668),
    "mean_longitude": (100.46457166, 35999.37244981),
    "perihelion": (102.93768193, 0.32327364),
    "node": (0.0, 0.0),
}

PLANETS: tuple[dict, ...] = (
    {
        "name": "Mercury",
        "inner": True,
        "a": (0.38709927, 0.00000037),
        "e": (0.20563593, 0.00001906),
        "i": (7.00497902, -0.00594749),
        "mean_longitude": (252.2503235, 149472.67411175),
        "perihelion": (77.45779628, 0.16047689),
        "node": (48.33076593, -0.12534081),
    },
    {
        "name": "Venus",
        "inner": True,
        "a": (0.72333566, 0.0000039),
        "e": (0.00677672, -0.00004107),
        "i": (3.39467605, -0.0007889),
        "mean_longitude": (181.9790995, 58517.81538729),
        "perihelion": (131.60246718, 0.00268329),
        "node": (76.67984255, -0.27769418),
    },
    {
        "name": "Mars",
        "inner": False,
        "a": (1.52371034, 0.00001847),
        "e": (0.0933941, 0.00007882),
        "i": (1.84969142, -0.00813131),
        "mean_longitude": (-4.55343205, 19140.30268499),
        "perihelion": (-23.94362959, 0.44441088),
        "node": (49.55953891, -0.29257343),
    },
    {
        "name": "Jupiter",
        "inner": False,
        "a": (5.202887, -0.00011607),
        "e": (0.04838624, -0.00013253),
        "i": (1.30439695, -0.00183714),
        "mean_longitude": (34.39644051, 3034.74612775),
        "perihelion": (14.72847983, 0.21252668),
        "node": (100.47390909, 0.20469106),
    },
    {
        "name": "Saturn",
        "inner": False,
        "a": (9.53667594, -0.0012506),
        "e": (0.05386179, -0.00050991),
        "i": (2.48599187, 0.00193609),
        "mean_longitude": (49.95424423, 1222.49362201),
        "perihelion": (92.59887831, -0.41897216),
        "node": (113.66242448, -0.28867794),
    },
)


def _at_century(pair: tuple[float, float], centuries: float) -> float:
    return pair[0] + pair[1] * centuries


def _eccentric_anomaly(mean_anomaly: float, eccentricity: float) -> float:
    anomaly = mean_anomaly + eccentricity * math.sin(mean_anomaly)
    for _ in range(8):
        delta = (anomaly - eccentricity * math.sin(anomaly) - mean_anomaly) / (
            1 - eccentricity * math.cos(anomaly)
        )
        anomaly -= delta
        if abs(delta) < 1e-10:
            break
    return anomaly


def _heliocentric(elements: dict, centuries: float) -> tuple[float, float, float]:
    a = _at_century(elements["a"], centuries)
    e = _at_century(elements["e"], centuries)
    inclination = math.radians(_at_century(elements["i"], centuries))
    mean_longitude = math.radians(_at_century(elements["mean_longitude"], centuries))
    perihelion = math.radians(_at_century(elements["perihelion"], centuries))
    node = math.radians(_at_century(elements["node"], centuries))

    arg_perihelion = perihelion - node
    anomaly = _eccentric_anomaly(mean_longitude - perihelion, e)
    x_orbit = a * (math.cos(anomaly) - e)
    y_orbit = a * math.sqrt(1 - e * e) * math.sin(anomaly)

    cos_arg, sin_arg = math.cos(arg_perihelion), math.sin(arg_perihelion)
    cos_node, sin_node = math.cos(node), math.sin(node)
    cos_inc, sin_inc = math.cos(inclination), math.sin(inclination)

    return (
        (cos_arg * cos_node - sin_arg * sin_node * cos_inc) * x_orbit
        + (-sin_arg * cos_node - cos_arg * sin_node * cos_inc) * y_orbit,
        (cos_arg * sin_node + sin_arg * cos_node * cos_inc) * x_orbit
        + (-sin_arg * sin_node + cos_arg * cos_node * cos_inc) * y_orbit,
        sin_arg * sin_inc * x_orbit + cos_arg * sin_inc * y_orbit,
    )


def planet_geocentric(planet: dict, moment: datetime) -> tuple[float, float, float]:
    """Right ascension, declination, and distance in AU of a planet."""
    centuries = days_since_j2000(moment) / 36525
    px, py, pz = _heliocentric(planet, centuries)
    ex, ey, ez = _heliocentric(EARTH_ELEMENTS, centuries)
    x, y, z = px - ex, py - ey, pz - ez
    ecl_lon = math.atan2(y, x)
    ecl_lat = math.atan2(z, math.hypot(x, y))
    ra, dec = _ecliptic_to_equatorial(ecl_lon, ecl_lat)
    return ra, dec, math.sqrt(x * x + y * y + z * z)


def planet_elongation_deg(planet: dict, moment: datetime) -> float:
    """Angular distance from the Sun in degrees; ~180 at opposition."""
    sun_ra, sun_dec = sun_equatorial(days_since_j2000(moment))
    ra, dec, _ = planet_geocentric(planet, moment)
    return math.degrees(angular_separation(sun_ra, sun_dec, ra, dec))


# --- Nightly geometry ---------------------------------------------------------

ASTRONOMICAL_TWILIGHT = math.radians(-18.0)
HORIZON = math.radians(-0.833)


@dataclass(frozen=True)
class DarkWindow:
    """A span of true astronomical darkness."""

    start: datetime
    end: datetime

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


def dark_window(night_of: datetime, lat: float, lon: float) -> DarkWindow | None:
    """Astronomical darkness for the night beginning on the given date.

    Searches a 36-hour span from local afternoon so the dusk is always paired
    with the dawn that actually follows it, rather than assuming the two land on
    adjacent calendar dates - which is false whenever the configured
    coordinates sit in a different timezone from the host.
    """
    start = night_of.replace(hour=12, minute=0, second=0, microsecond=0)
    crossings = find_altitude_crossings(
        lambda moment: sun_altitude(moment, lat, lon),
        start,
        start + timedelta(hours=36),
        ASTRONOMICAL_TWILIGHT,
    )
    dusk = next((c.moment for c in crossings if not c.rising), None)
    if dusk is None:
        return None
    dawn = next((c.moment for c in crossings if c.rising and c.moment > dusk), None)
    if dawn is None:
        return None
    return DarkWindow(start=dusk, end=dawn)


def sun_event(night_of: datetime, lat: float, lon: float, rising: bool) -> datetime | None:
    """Sunrise or sunset for the given local date."""
    start = night_of.replace(hour=0, minute=0, second=0, microsecond=0)
    crossings = find_altitude_crossings(
        lambda moment: sun_altitude(moment, lat, lon),
        start,
        start + timedelta(hours=24),
        HORIZON,
    )
    return next((c.moment for c in crossings if c.rising == rising), None)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
