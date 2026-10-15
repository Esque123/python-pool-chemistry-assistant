"""Offline sunset calculation for the SLAM shock-timing cutoff.

Lets the "too early to start the shock" cutoff track today's real, seasonal
sunset instead of a fixed clock hour -- with NO network call, NO third-party
dependency, and NO manual user input. Location is inferred automatically from
the machine's Windows time zone (registry -> representative city coordinates);
sunset is then computed with the standard NOAA sunrise/sunset equations.

Everything degrades gracefully: off Windows, on an unknown time zone, or on a
polar day/night with no sunset, the public helpers return None so the caller
can fall back to its fixed-hour cutoff.
"""

import math
from datetime import datetime


# Representative (latitude, longitude) for each Windows time-zone key, east
# longitude positive, north latitude positive. Coordinates are the zone's main
# city -- accurate to well within the ~10-15 min that a 2-hour cutoff needs.
# Unknown keys simply fall back to the fixed-hour cutoff upstream, so partial
# coverage is safe; add zones here as needed.
WINDOWS_TZ_COORDS = {
    # Africa
    "South Africa Standard Time": (-26.20, 28.04),   # Johannesburg
    "W. Central Africa Standard Time": (6.52, 3.38),  # Lagos
    "E. Africa Standard Time": (-1.29, 36.82),        # Nairobi
    "Egypt Standard Time": (30.04, 31.24),            # Cairo
    "Morocco Standard Time": (33.57, -7.59),          # Casablanca
    "Namibia Standard Time": (-22.56, 17.08),         # Windhoek
    "Mauritius Standard Time": (-20.16, 57.50),       # Port Louis
    # Europe
    "GMT Standard Time": (51.51, -0.13),              # London
    "Greenwich Standard Time": (64.15, -21.94),       # Reykjavik
    "W. Europe Standard Time": (52.52, 13.40),        # Berlin
    "Central Europe Standard Time": (50.08, 14.44),   # Prague
    "Central European Standard Time": (52.23, 21.01), # Warsaw
    "Romance Standard Time": (48.85, 2.35),           # Paris
    "E. Europe Standard Time": (47.01, 28.86),        # Chisinau
    "GTB Standard Time": (37.98, 23.73),              # Athens
    "FLE Standard Time": (60.17, 24.94),              # Helsinki
    "Russian Standard Time": (55.75, 37.62),          # Moscow
    "Turkey Standard Time": (41.01, 28.98),           # Istanbul
    # Middle East / West & Central Asia
    "Israel Standard Time": (31.78, 35.22),           # Jerusalem
    "Arabian Standard Time": (24.47, 54.37),          # Abu Dhabi
    "Arab Standard Time": (24.71, 46.68),             # Riyadh
    "Iran Standard Time": (35.69, 51.39),             # Tehran
    "Azerbaijan Standard Time": (40.41, 49.87),       # Baku
    "Caucasus Standard Time": (40.18, 44.51),         # Yerevan
    "Georgian Standard Time": (41.72, 44.78),         # Tbilisi
    "West Asia Standard Time": (41.30, 69.24),        # Tashkent
    "Central Asia Standard Time": (51.17, 71.45),     # Astana
    # South & South-East Asia
    "India Standard Time": (28.61, 77.21),            # New Delhi
    "Pakistan Standard Time": (24.86, 67.00),         # Karachi
    "Bangladesh Standard Time": (23.81, 90.41),       # Dhaka
    "Nepal Standard Time": (27.72, 85.32),            # Kathmandu
    "Sri Lanka Standard Time": (6.93, 79.84),         # Colombo
    "Myanmar Standard Time": (16.87, 96.20),          # Yangon
    "SE Asia Standard Time": (13.76, 100.50),         # Bangkok
    "Singapore Standard Time": (1.35, 103.82),        # Singapore
    # East Asia
    "China Standard Time": (39.90, 116.40),           # Beijing
    "Taipei Standard Time": (25.03, 121.57),          # Taipei
    "Tokyo Standard Time": (35.68, 139.69),           # Tokyo
    "Korea Standard Time": (37.57, 126.98),           # Seoul
    "Ulaanbaatar Standard Time": (47.89, 106.91),     # Ulaanbaatar
    "North Asia Standard Time": (56.01, 92.85),       # Krasnoyarsk
    "Vladivostok Standard Time": (43.12, 131.89),     # Vladivostok
    # Australia / Pacific
    "W. Australia Standard Time": (-31.95, 115.86),   # Perth
    "AUS Central Standard Time": (-12.46, 130.84),    # Darwin
    "Cen. Australia Standard Time": (-34.93, 138.60), # Adelaide
    "E. Australia Standard Time": (-27.47, 153.03),   # Brisbane
    "AUS Eastern Standard Time": (-33.87, 151.21),    # Sydney
    "Tasmania Standard Time": (-42.88, 147.33),       # Hobart
    "New Zealand Standard Time": (-36.85, 174.76),    # Auckland
    "Fiji Standard Time": (-18.14, 178.44),           # Suva
    "Samoa Standard Time": (-13.83, -171.77),         # Apia
    # North America
    "Hawaiian Standard Time": (21.31, -157.86),       # Honolulu
    "Alaskan Standard Time": (61.22, -149.90),        # Anchorage
    "Pacific Standard Time": (34.05, -118.24),        # Los Angeles
    "US Mountain Standard Time": (33.45, -112.07),    # Phoenix
    "Mountain Standard Time": (39.74, -104.99),       # Denver
    "Central Standard Time": (41.88, -87.63),         # Chicago
    "Central Standard Time (Mexico)": (19.43, -99.13),# Mexico City
    "Canada Central Standard Time": (50.45, -104.62), # Regina
    "Eastern Standard Time": (40.71, -74.01),         # New York
    "US Eastern Standard Time": (39.77, -86.16),      # Indianapolis
    "Atlantic Standard Time": (44.65, -63.58),        # Halifax
    "Newfoundland Standard Time": (47.56, -52.71),    # St. John's
    # Central & South America
    "Central America Standard Time": (14.63, -90.51), # Guatemala City
    "SA Pacific Standard Time": (4.71, -74.07),       # Bogota
    "Venezuela Standard Time": (10.48, -66.90),       # Caracas
    "Pacific SA Standard Time": (-33.45, -70.67),     # Santiago
    "Argentina Standard Time": (-34.60, -58.38),      # Buenos Aires
    "E. South America Standard Time": (-23.55, -46.63),  # Sao Paulo
    "Montevideo Standard Time": (-34.90, -56.19),     # Montevideo
    "Paraguay Standard Time": (-25.30, -57.63),       # Asuncion
    "Cuba Standard Time": (23.11, -82.37),            # Havana
}


def get_local_coords():
    """Return (lat, lon) for the machine's Windows time zone, else None.

    Reads the invariant TimeZoneKeyName from the registry (locale-independent),
    so it does not depend on the display language. Returns None off Windows or
    when the zone isn't in WINDOWS_TZ_COORDS.
    """
    try:
        import winreg  # Windows-only stdlib
    except ImportError:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation",
        ) as key:
            name, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
    except OSError:
        return None
    return WINDOWS_TZ_COORDS.get(name)


def _sunset_utc_hours(day, lat, lon):
    """Sunset for `day` at (lat, lon) as hours UTC, or None if the sun doesn't
    set that day (polar summer) / doesn't rise (polar winter). Standard NOAA
    sunrise/sunset algorithm."""
    zenith = 90.833  # official sunset (accounts for refraction + solar disc)
    n = day.timetuple().tm_yday
    lng_hour = lon / 15.0

    t = n + ((18.0 - lng_hour) / 24.0)  # 18 = rising-hour guess for sunset
    m = (0.9856 * t) - 3.289

    true_long = (
        m
        + (1.916 * math.sin(math.radians(m)))
        + (0.020 * math.sin(math.radians(2 * m)))
        + 282.634
    ) % 360.0

    ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_long)))) % 360.0
    # Put RA in the same quadrant as the true longitude
    ra += (math.floor(true_long / 90.0) * 90.0) - (math.floor(ra / 90.0) * 90.0)
    ra /= 15.0  # to hours

    sin_dec = 0.39782 * math.sin(math.radians(true_long))
    cos_dec = math.cos(math.asin(sin_dec))

    cos_h = (
        math.cos(math.radians(zenith)) - (sin_dec * math.sin(math.radians(lat)))
    ) / (cos_dec * math.cos(math.radians(lat)))
    if cos_h < -1.0 or cos_h > 1.0:
        return None  # no sunset (or no sunrise) at this latitude on this day

    h = math.degrees(math.acos(cos_h)) / 15.0  # sunset hour angle (hours)
    mean_time = h + ra - (0.06571 * t) - 6.622
    return (mean_time - lng_hour) % 24.0


def local_sunset(now, coords=None, utc_offset_hours=None):
    """Return a naive datetime (on `now`'s date) of today's local sunset, or
    None if location is unknown or there's no sunset that day.

    `coords` and `utc_offset_hours` are injectable for testing; by default
    coords come from the Windows time zone and the offset from the system clock.
    """
    if coords is None:
        coords = get_local_coords()
    if not coords:
        return None

    if utc_offset_hours is None:
        offset = now.astimezone().utcoffset()
        utc_offset_hours = offset.total_seconds() / 3600.0 if offset else 0.0

    utc_hours = _sunset_utc_hours(now.date(), coords[0], coords[1])
    if utc_hours is None:
        return None

    total_minutes = int(round(((utc_hours + utc_offset_hours) % 24.0) * 60.0)) % (24 * 60)
    return now.replace(
        hour=total_minutes // 60, minute=total_minutes % 60, second=0, microsecond=0
    )
