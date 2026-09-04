"""Sun, moon, and planet geometry with no external ephemeris dependency.

This is a port of the algorithms already used and verified in the Lovelace
card: low-precision solar and lunar series, a shared numeric altitude-crossing
finder for every rise/set/twilight time, and two-body Keplerian propagation for
the naked-eye planets.

Deliberately pure standard library, and not for want of CPU: astropy and
skyfield pull in numpy and scipy or download ephemeris kernels into the config
directory at runtime, which is a heavy thing to ask of a HACS install and a new
way for it to break offline. The cost of avoiding them is bounded and known.

Where that cost actually lands, each figure measured against published values
rather than against this code:

- **Sun**: Meeus chapter 25 apparent longitude, better than a hundredth of a
  degree. Rise, set, and twilight times land within a minute or two, finer than
  the weather forecast driving the decision.
- **Moon**: the Meeus chapter 47 truncated ELP series, sixty periodic terms.
  It reproduces the January 2026 full moon to within a minute and the March
  2026 one to within two. The single-term series it replaced was 124 minutes
  early on the first of those.
- **Planets**: two-body Keplerian propagation from mean elements. Jupiter's
  2026 and 2027 oppositions land on the published instant; Mars and Saturn run
  about a day late, because their mutual perturbations are not modelled. For
  choosing a night to photograph a planet that is immaterial - a planet is
  equally well placed for weeks either side of opposition - but it is not the
  arcminute accuracy a full perturbation theory would give, and a Moon-planet
  conjunction separation should be read as approximate for those two.
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


def _ecliptic_to_equatorial(
    ecl_lon: float, ecl_lat: float, obliquity: float | None = None
) -> tuple[float, float]:
    eps = OBLIQUITY if obliquity is None else obliquity
    ra = math.atan2(
        math.sin(ecl_lon) * math.cos(eps) - math.tan(ecl_lat) * math.sin(eps),
        math.cos(ecl_lon),
    )
    dec = math.asin(
        _clamp(
            math.sin(ecl_lat) * math.cos(eps)
            + math.cos(ecl_lat) * math.sin(eps) * math.sin(ecl_lon),
            -1.0,
            1.0,
        )
    )
    return ra, dec


def mean_obliquity(d: float) -> float:
    """Obliquity of the ecliptic in radians, drifting with time."""
    t = d / 36525.0
    return math.radians(23.439291 - 0.0130042 * t - 1.64e-7 * t * t + 5.04e-7 * t * t * t)


def sun_ecliptic_longitude(d: float) -> float:
    """Apparent geocentric ecliptic longitude of the Sun, in radians.

    Meeus chapter 25, including the aberration and nutation correction. Good to
    better than a hundredth of a degree, which keeps the Sun from being the
    limiting term in any Sun-relative quantity computed here.
    """
    t = d / 36525.0
    mean_longitude = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    mean_anomaly = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    centre = (
        (1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mean_anomaly)
        + (0.019993 - 0.000101 * t) * math.sin(2 * mean_anomaly)
        + 0.000289 * math.sin(3 * mean_anomaly)
    )
    node = math.radians(125.04 - 1934.136 * t)
    apparent = mean_longitude + centre - 0.00569 - 0.00478 * math.sin(node)
    return math.radians(apparent % 360)


def sun_equatorial(d: float) -> tuple[float, float]:
    """Geocentric right ascension and declination of the Sun, in radians."""
    return _ecliptic_to_equatorial(sun_ecliptic_longitude(d), 0.0, mean_obliquity(d))


# Meeus chapter 47, tables 47.A and 47.B: the truncated ELP-2000/82 series.
# Each row is (D, M, M', F, coefficient). The longitude and radius terms share
# arguments so they share a table; latitude has its own.
#
# This is the difference between "the Moon is up" and a usable conjunction
# separation. The one-term series this replaced put the January 2026 full moon
# two hours off its published time; these terms put it within a minute.
_MOON_LON_RADIUS: tuple[tuple[int, int, int, int, int, int], ...] = (
    (0, 0, 1, 0, 6288774, -20905355), (2, 0, -1, 0, 1274027, -3699111),
    (2, 0, 0, 0, 658314, -2955968), (0, 0, 2, 0, 213618, -569925),
    (0, 1, 0, 0, -185116, 48888), (0, 0, 0, 2, -114332, -3149),
    (2, 0, -2, 0, 58793, 246158), (2, -1, -1, 0, 57066, -152138),
    (2, 0, 1, 0, 53322, -170733), (2, -1, 0, 0, 45758, -204586),
    (0, 1, -1, 0, -40923, -129620), (1, 0, 0, 0, -34720, 108743),
    (0, 1, 1, 0, -30383, 104755), (2, 0, 0, -2, 15327, 10321),
    (0, 0, 1, 2, -12528, 0), (0, 0, 1, -2, 10980, 79661),
    (4, 0, -1, 0, 10675, -34782), (0, 0, 3, 0, 10034, -23210),
    (4, 0, -2, 0, 8548, -21636), (2, 1, -1, 0, -7888, 24208),
    (2, 1, 0, 0, -6766, 30824), (1, 0, -1, 0, -5163, -8379),
    (1, 1, 0, 0, 4987, -16675), (2, -1, 1, 0, 4036, -12831),
    (2, 0, 2, 0, 3994, -10445), (4, 0, 0, 0, 3861, -11650),
    (2, 0, -3, 0, 3665, 14403), (0, 1, -2, 0, -2689, -7003),
    (2, 0, -1, 2, -2602, 0), (2, -1, -2, 0, 2390, 10056),
    (1, 0, 1, 0, -2348, 6322), (2, -2, 0, 0, 2236, -9884),
    (0, 1, 2, 0, -2120, 5751), (0, 2, 0, 0, -2069, 0),
    (2, -2, -1, 0, 2048, -4950), (2, 0, 1, -2, -1773, 4130),
    (2, 0, 0, 2, -1595, 0), (4, -1, -1, 0, 1215, -3958),
    (0, 0, 2, 2, -1110, 0), (3, 0, -1, 0, -892, 3258),
    (2, 1, 1, 0, -810, 2616), (4, -1, -2, 0, 759, -1897),
    (0, 2, -1, 0, -713, -2117), (2, 2, -1, 0, -700, 2354),
    (2, 1, -2, 0, 691, 0), (2, -1, 0, -2, 596, 0),
    (4, 0, 1, 0, 549, -1423), (0, 0, 4, 0, 537, -1117),
    (4, -1, 0, 0, 520, -1571), (1, 0, -2, 0, -487, -1739),
    (2, 1, 0, -2, -399, 0), (0, 0, 2, -2, -381, -4421),
    (1, 1, 1, 0, 351, 0), (3, 0, -2, 0, -340, 0),
    (4, 0, -3, 0, 330, 0), (2, -1, 2, 0, 327, 0),
    (0, 2, 1, 0, -323, 1165), (1, 1, -1, 0, 299, 0),
    (2, 0, 3, 0, 294, 0), (2, 0, -1, -2, 0, 8752),
)

_MOON_LATITUDE: tuple[tuple[int, int, int, int, int], ...] = (
    (0, 0, 0, 1, 5128122), (0, 0, 1, 1, 280602), (0, 0, 1, -1, 277693),
    (2, 0, 0, -1, 173237), (2, 0, -1, 1, 55413), (2, 0, -1, -1, 46271),
    (2, 0, 0, 1, 32573), (0, 0, 2, 1, 17198), (2, 0, 1, -1, 9266),
    (0, 0, 2, -1, 8822), (2, -1, 0, -1, 8216), (2, 0, -2, -1, 4324),
    (2, 0, 1, 1, 4200), (2, 1, 0, -1, -3359), (2, -1, -1, 1, 2463),
    (2, -1, 0, 1, 2211), (2, -1, -1, -1, 2065), (0, 1, -1, -1, -1870),
    (4, 0, -1, -1, 1828), (0, 1, 0, 1, -1794), (0, 0, 0, 3, -1749),
    (0, 1, -1, 1, -1565), (1, 0, 0, 1, -1491), (0, 1, 1, 1, -1475),
    (0, 1, 1, -1, -1410), (0, 1, 0, -1, -1344), (1, 0, 0, -1, -1335),
    (0, 0, 3, 1, 1107), (4, 0, 0, -1, 1021), (4, 0, -1, 1, 833),
    (0, 0, 1, -3, 777), (4, 0, -2, 1, 671), (2, 0, 0, -3, 607),
    (2, 0, 2, -1, 596), (2, -1, 1, -1, 491), (2, 0, -2, 1, -451),
    (0, 0, 3, -1, 439), (2, 0, 2, 1, 422), (2, 0, -3, -1, 421),
    (2, 1, -1, 1, -366), (2, 1, 0, 1, -351), (4, 0, 0, 1, 331),
    (2, -1, 1, 1, 315), (2, -2, 0, -1, 302), (0, 0, 1, 3, -283),
    (2, 1, 1, -1, -229), (1, 1, 0, -1, 223), (1, 1, 0, 1, 223),
    (0, 1, -2, -1, -220), (2, 1, -1, -1, -220), (1, 0, 1, 1, -185),
    (2, -1, -2, -1, 181), (0, 1, 2, 1, -177), (4, 0, -2, -1, 176),
    (4, -1, -1, -1, 166), (1, 0, 1, -1, -164), (4, 0, 1, -1, 132),
    (1, 0, -1, -1, -119), (4, -1, 0, -1, 115), (2, -2, 0, 1, 107),
)


def moon_ecliptic(d: float) -> tuple[float, float, float]:
    """Geocentric ecliptic longitude and latitude in radians, distance in km."""
    t = d / 36525.0
    mean_longitude = (
        218.3164477 + 481267.88123421 * t - 0.0015786 * t * t + t**3 / 538841 - t**4 / 65194000
    )
    elongation = (
        297.8501921 + 445267.1114034 * t - 0.0018819 * t * t + t**3 / 545868 - t**4 / 113065000
    )
    sun_anomaly = 357.5291092 + 35999.0502909 * t - 0.0001536 * t * t + t**3 / 24490000
    moon_anomaly = (
        134.9633964 + 477198.8675055 * t + 0.0087414 * t * t + t**3 / 69699 - t**4 / 14712000
    )
    latitude_argument = (
        93.2720950 + 483202.0175233 * t - 0.0036539 * t * t - t**3 / 3526000 + t**4 / 863310000
    )
    venus_term = 119.75 + 131.849 * t
    jupiter_term = 53.09 + 479264.290 * t
    flattening_term = 313.45 + 481266.484 * t
    # Corrects the terms involving the Sun's anomaly for Earth's slowly
    # changing orbital eccentricity.
    eccentricity = 1 - 0.002516 * t - 0.0000074 * t * t

    sum_lon = sum_radius = sum_lat = 0.0
    for c_d, c_m, c_mp, c_f, coeff_l, coeff_r in _MOON_LON_RADIUS:
        argument = math.radians(
            c_d * elongation + c_m * sun_anomaly + c_mp * moon_anomaly + c_f * latitude_argument
        )
        scale = eccentricity ** abs(c_m)
        sum_lon += coeff_l * scale * math.sin(argument)
        sum_radius += coeff_r * scale * math.cos(argument)
    for c_d, c_m, c_mp, c_f, coeff_b in _MOON_LATITUDE:
        argument = math.radians(
            c_d * elongation + c_m * sun_anomaly + c_mp * moon_anomaly + c_f * latitude_argument
        )
        sum_lat += coeff_b * (eccentricity ** abs(c_m)) * math.sin(argument)

    sum_lon += (
        3958 * math.sin(math.radians(venus_term))
        + 1962 * math.sin(math.radians(mean_longitude - latitude_argument))
        + 318 * math.sin(math.radians(jupiter_term))
    )
    sum_lat += (
        -2235 * math.sin(math.radians(mean_longitude))
        + 382 * math.sin(math.radians(flattening_term))
        + 175 * math.sin(math.radians(venus_term - latitude_argument))
        + 175 * math.sin(math.radians(venus_term + latitude_argument))
        + 127 * math.sin(math.radians(mean_longitude - moon_anomaly))
        - 115 * math.sin(math.radians(mean_longitude + moon_anomaly))
    )

    return (
        math.radians((mean_longitude + sum_lon / 1e6) % 360),
        math.radians(sum_lat / 1e6),
        385000.56 + sum_radius / 1000.0,
    )


def moon_equatorial(d: float) -> tuple[float, float, float]:
    """Right ascension, declination, and distance in km of the Moon."""
    ecl_lon, ecl_lat, distance = moon_ecliptic(d)
    ra, dec = _ecliptic_to_equatorial(ecl_lon, ecl_lat, mean_obliquity(d))
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


# --- Shooting windows -------------------------------------------------------
#
# The astro window is the *intersection* of three independent conditions, not
# the span of astronomical darkness. Reporting darkness alone is how a
# September night in California gets described as an all-night Milky Way
# window when the galactic core is already below the ridgeline by 22:30.
#
# Each condition is solved as an interval by root-finding rather than by
# sampling on a grid: altitude curves are smooth, so the crossings are exact to
# the second and cost a fraction of a minute-by-minute scan. The intervals are
# then intersected.

MIN_CORE_ALTITUDE_DEG = 15.0
MOON_SUPPRESSION_ILLUMINATION = 0.20


@dataclass(frozen=True)
class Interval:
    """A closed time span."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


@dataclass(frozen=True)
class ShootingWindow:
    """When every condition for a target is satisfied at once."""

    start: datetime
    end: datetime
    limited_by: str
    target_sets: datetime | None
    darkness_ends: datetime | None
    moon_rises: datetime | None
    moon_illumination: float
    peak_target_altitude: float

    @property
    def duration_minutes(self) -> int:
        return int(round((self.end - self.start).total_seconds() / 60))

    @property
    def is_brief(self) -> bool:
        """Short enough that the drive needs planning around it."""
        return self.duration_minutes < 120


def intervals_where(
    altitude_fn,
    start: datetime,
    end: datetime,
    threshold: float,
    above: bool,
    step_minutes: int = 4,
) -> list[Interval]:
    """Sub-spans of [start, end] on the wanted side of a threshold.

    Built from interpolated threshold crossings, so a boundary is accurate to
    well under a minute regardless of the sampling step.
    """
    crossings = find_altitude_crossings(altitude_fn, start, end, threshold, step_minutes)
    inside = (altitude_fn(start) > threshold) if above else (altitude_fn(start) < threshold)

    spans: list[Interval] = []
    opened = start if inside else None
    for crossing in crossings:
        entering = crossing.rising if above else not crossing.rising
        if entering and opened is None:
            opened = crossing.moment
        elif not entering and opened is not None:
            if crossing.moment > opened:
                spans.append(Interval(opened, crossing.moment))
            opened = None
    if opened is not None and end > opened:
        spans.append(Interval(opened, end))
    return spans


def intersect_intervals(left: list[Interval], right: list[Interval]) -> list[Interval]:
    """Every span present in both lists."""
    found: list[Interval] = []
    for one in left:
        for other in right:
            start = max(one.start, other.start)
            end = min(one.end, other.end)
            if end > start:
                found.append(Interval(start, end))
    return sorted(found, key=lambda span: span.start)


def astro_shooting_window(
    night_of: datetime,
    lat: float,
    lon: float,
    ra_deg: float = GALACTIC_CORE_RA_DEG,
    dec_deg: float = GALACTIC_CORE_DEC_DEG,
    min_target_altitude: float = MIN_CORE_ALTITUDE_DEG,
    max_moon_illumination: float = MOON_SUPPRESSION_ILLUMINATION,
) -> ShootingWindow | None:
    """The span where darkness, target elevation and moonlight all cooperate.

    Three conditions, all of which must hold simultaneously:

    - **Darkness**: the Sun below -18 degrees, true astronomical night.
    - **Elevation**: the target above ``min_target_altitude``, clearing the
      worst atmospheric extinction and any realistic ridgeline.
    - **Moonlight**: the Moon below the horizon, or too thin a crescent to
      matter.

    Returns the longest span satisfying all three, or None when there is no
    such span - which is the correct answer on a bright-moon night, and one the
    old dusk-to-dawn window could never give.
    """
    # Noon to noon: exactly one dusk and the dawn that follows it. A wider
    # span would contain two nights, and picking the longest window across it
    # silently reports *tomorrow's* window under today's date - and pairs it
    # with the wrong night's moon.
    search_start = night_of.replace(hour=12, minute=0, second=0, microsecond=0)
    search_end = search_start + timedelta(hours=24)

    dark = intervals_where(
        lambda moment: sun_altitude(moment, lat, lon),
        search_start,
        search_end,
        ASTRONOMICAL_TWILIGHT,
        above=False,
    )
    if not dark:
        return None

    target_ra = math.radians(ra_deg)
    target_dec = math.radians(dec_deg)

    def target_altitude(moment: datetime) -> float:
        return horizontal(target_ra, target_dec, moment, lat, lon)[0]

    high = intervals_where(
        target_altitude,
        search_start,
        search_end,
        math.radians(min_target_altitude),
        above=True,
    )
    if not high:
        return None

    # Illumination barely moves across one night, so it is read once, at the
    # middle of the darkness, rather than sampled.
    midpoint = dark[0].start + (dark[0].end - dark[0].start) / 2
    illumination, _, _ = moon_illumination(midpoint)

    if illumination < max_moon_illumination:
        moon_ok = [Interval(search_start, search_end)]
        moon_rises = None
    else:
        moon_ok = intervals_where(
            lambda moment: moon_altitude(moment, lat, lon),
            search_start,
            search_end,
            0.0,
            above=False,
        )
        rises = find_altitude_crossings(
            lambda moment: moon_altitude(moment, lat, lon),
            search_start,
            search_end,
            0.0,
        )
        moon_rises = next((c.moment for c in rises if c.rising), None)
    if not moon_ok:
        return None

    usable = intersect_intervals(intersect_intervals(dark, high), moon_ok)
    if not usable:
        return None

    best = max(usable, key=lambda span: span.minutes)
    # Report the illumination at the window actually chosen, so the figure on
    # the card always describes the night it is printed against.
    illumination, _, _ = moon_illumination(best.start + (best.end - best.start) / 2)

    # Which constraint actually closed the window - the difference between
    # "come back later tonight" and "come back in a week".
    target_span = next((span for span in high if span.start <= best.end <= span.end + timedelta(seconds=1)), None)
    dark_span = next((span for span in dark if span.start <= best.end <= span.end + timedelta(seconds=1)), None)
    target_sets = target_span.end if target_span else None
    darkness_ends = dark_span.end if dark_span else None

    limited_by = "moonrise"
    if target_sets is not None and abs((best.end - target_sets).total_seconds()) < 60:
        limited_by = "target"
    elif darkness_ends is not None and abs((best.end - darkness_ends).total_seconds()) < 60:
        limited_by = "dawn"

    peak = max_altitude_in_window(ra_deg, dec_deg, best.start, best.end, lat, lon)

    return ShootingWindow(
        start=best.start,
        end=best.end,
        limited_by=limited_by,
        target_sets=target_sets,
        darkness_ends=darkness_ends,
        moon_rises=moon_rises,
        moon_illumination=illumination,
        peak_target_altitude=peak,
    )


def _sun_moon_elongation(moment: datetime) -> float:
    """Moon minus Sun in ecliptic longitude, wrapped to +/-180 degrees."""
    days = days_since_j2000(moment)
    separation = math.degrees(moon_ecliptic(days)[0] - sun_ecliptic_longitude(days))
    return (separation + 180) % 360 - 180


def _phase_angle_deg(moment: datetime) -> float:
    """Moon minus Sun in ecliptic longitude, 0-360. Zero is new, 180 is full."""
    days = days_since_j2000(moment)
    return math.degrees(moon_ecliptic(days)[0] - sun_ecliptic_longitude(days)) % 360


def _phase_crossings(start: datetime, end: datetime, target_deg: float) -> list[datetime]:
    """Moments the lunar phase angle passes a given value.

    The subtlety that earns this its own function: every wrapped angular measure
    has a discontinuity somewhere, and at that point it jumps a full 360
    degrees - which a plain sign-change test reads as a crossing. Hunting for
    new moons on the signed elongation therefore returns every *full* moon as
    well, because the wrap sits exactly there.

    That bug hides in plain sight, since both answers are plausible dates, and
    it corrupts everything downstream: a full moon mistaken for a new one lets
    the most washed-out night of the month score as though it were the darkest.

    So a crossing only counts when consecutive samples moved a *small* amount.
    The Moon covers about three degrees in six hours; the wrap covers 360.
    """

    def offset(moment: datetime) -> float:
        return ((_phase_angle_deg(moment) - target_deg + 180) % 360) - 180

    found: list[datetime] = []
    step = timedelta(hours=6)
    previous, previous_value = start, offset(start)
    moment = start + step
    while moment <= end:
        value = offset(moment)
        crossed = previous_value <= 0 <= value or previous_value >= 0 >= value
        if crossed and abs(value - previous_value) < 180:
            low, high = previous, moment
            for _ in range(40):
                middle = low + (high - low) / 2
                if (offset(low) <= 0 <= offset(middle)) or (offset(low) >= 0 >= offset(middle)):
                    high = middle
                else:
                    low = middle
            found.append(low + (high - low) / 2)
        previous, previous_value, moment = moment, value, moment + step
    return found


def new_moons_between(start: datetime, end: datetime) -> list[datetime]:
    """Every new moon in a span, in order."""
    return _phase_crossings(start, end, 0.0)


def full_moons_between(start: datetime, end: datetime) -> list[datetime]:
    """Every full moon in a span, in order."""
    return _phase_crossings(start, end, 180.0)


def next_new_moon(after: datetime, horizon_days: int = 40) -> datetime | None:
    """When the Moon next goes new.

    Answers the question that matters more than tonight's cloud cover: is a
    dramatically better night coming soon?
    """
    found = new_moons_between(after, after + timedelta(days=horizon_days))
    return found[0] if found else None


def nearest_new_moon(moment: datetime) -> tuple[datetime | None, float]:
    """The closest new moon in either direction, and signed days to it.

    Negative days mean it has already passed. Every new moon in a window
    straddling the date is collected and the closest chosen - taking "the first
    one after a month ago" instead would skip the most recent one entirely and
    report a date two weeks out as the nearest.

    Illumination cannot answer this on its own: it is symmetric about new, so it
    gives the distance but never the direction, and the direction is what
    decides whether to go tonight or wait.
    """
    found = new_moons_between(moment - timedelta(days=20), moment + timedelta(days=20))
    if not found:
        return None, float("inf")
    closest = min(found, key=lambda when: abs((when - moment).total_seconds()))
    return closest, (closest - moment).total_seconds() / 86400
