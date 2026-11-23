"""
Turns the raw GPS points recorded during a run into a walked distance.

Phone GPS positions wobble by a few metres even when you stand still, and a
plain "add up the distance between every pair of points" counts every wobble
as walking: standing still slowly earns points, and a 400 m loop comes out
around 500 m. This module filters the points first, in three steps:

1. Drop bad readings: accuracy worse than MAX_ACCURACY metres, broken
   coordinates, or time going backwards.
2. Smooth the rest with a small Kalman filter. Each reading pulls the
   estimated position towards it, more strongly when the reading is accurate
   and when more time has passed (the walker could have moved further).
3. Only count real movement. Distance is measured from an "anchor" point and
   only added once the smoothed position is at least MIN_MOVE metres away,
   then the anchor moves there. Wobbles smaller than that are never counted.
   If the phone's step counter is working, distance is only added when steps
   were taken since the anchor, so standing still never earns distance.
   Jumps faster than MAX_SPEED (GPS glitches) are ignored.

The app runs the same algorithm (front-end-flutter/mobile/lib/gps_distance.dart)
for the live counter; the server's result is the one that is saved.

A track is a list of points: [latitude, longitude, accuracy_m, seconds, steps]
  seconds: time since the run started
  steps:   steps since the run started, or -1 if the step counter is off
"""

import math

MAX_ACCURACY = 25.0      # metres; readings less accurate than this are ignored
MIN_ACCURACY = 3.0       # metres; nothing is trusted more than this
PROCESS_NOISE = 4.0      # m/s; how fast the true position can drift away
MIN_MOVE = 10.0          # metres from the anchor before distance is counted
MAX_SPEED = 12.0         # m/s (43 km/h); faster jumps are GPS glitches
MAX_POINTS = 20000       # about 5.5 hours at one point per second

EARTH_RADIUS = 6371008.8  # metres


def haversine(lat1, lng1, lat2, lng2):
    """Distance in metres between two latitude/longitude points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS * math.asin(min(1.0, math.sqrt(a)))


def raw_distance(track):
    """The old, unfiltered method: every hop between points is added."""
    total = 0.0
    for a, b in zip(track, track[1:]):
        total += haversine(a[0], a[1], b[0], b[1])
    return total


def _valid(point):
    lat, lng, acc = point[0], point[1], point[2]
    return (
        -90 <= lat <= 90 and -180 <= lng <= 180
        and not (lat == 0 and lng == 0)
        and 0 < acc <= MAX_ACCURACY
    )


class DistanceFilter:
    """Feed points one at a time with add(); read .distance at any moment."""

    def __init__(self):
        self.distance = 0.0
        self._lat = self._lng = None   # smoothed position
        self._variance = 0.0           # its uncertainty, in metres squared
        self._time = 0.0
        self._anchor = None            # (lat, lng, time, steps)
        self._last = None              # last good raw reading (lat, lng, time, steps)

    def add(self, lat, lng, accuracy, seconds, steps=-1):
        if not _valid((lat, lng, accuracy)):
            return self.distance
        accuracy = max(accuracy, MIN_ACCURACY)
        if self._last is not None and seconds < self._last[2]:
            return self.distance               # time went backwards: ignore
        self._last = (lat, lng, seconds, steps)

        # --- step 2: smooth ---
        if self._lat is None:
            self._lat, self._lng = lat, lng
            self._variance = accuracy ** 2
            self._time = seconds
            self._anchor = (lat, lng, seconds, steps)
            return self.distance
        dt = seconds - self._time
        self._variance += dt * PROCESS_NOISE ** 2
        self._time = seconds
        gain = self._variance / (self._variance + accuracy ** 2)
        self._lat += gain * (lat - self._lat)
        self._lng += gain * (lng - self._lng)
        self._variance *= 1 - gain

        # --- step 3: count only real movement ---
        a_lat, a_lng, a_time, a_steps = self._anchor
        moved = haversine(a_lat, a_lng, self._lat, self._lng)
        if moved < MIN_MOVE:
            return self.distance
        elapsed = seconds - a_time
        if elapsed > 0 and moved / elapsed > MAX_SPEED:
            # A glitch: forget the jump, keep the anchor where it was.
            self._lat, self._lng = a_lat, a_lng
            return self.distance
        if steps >= 0 and a_steps >= 0 and steps <= a_steps:
            # The step counter says we haven't walked: it's GPS drift.
            return self.distance
        self.distance += moved
        self._anchor = (self._lat, self._lng, seconds, steps)
        return self.distance

    def finish(self):
        """
        Call once when the run stops. The smoothed position trails slightly
        behind a moving walker, so the last few metres are added here: from
        the anchor to the last real reading, using the same rules as add().
        """
        if self._anchor is None or self._last is None:
            return self.distance
        a_lat, a_lng, a_time, a_steps = self._anchor
        lat, lng, seconds, steps = self._last
        gap = haversine(a_lat, a_lng, lat, lng)
        elapsed = seconds - a_time
        walked = steps < 0 or a_steps < 0 or steps > a_steps
        if gap >= MIN_MOVE / 2 and walked and (elapsed <= 0 or gap / elapsed <= MAX_SPEED):
            self.distance += gap
            self._anchor = (lat, lng, seconds, steps)
        return self.distance


def track_distance(track):
    """Filtered distance in metres for a whole track."""
    f = DistanceFilter()
    for point in track:
        lat, lng, acc, seconds = point[0], point[1], point[2], point[3]
        steps = point[4] if len(point) > 4 else -1
        f.add(lat, lng, acc, seconds, steps)
    return f.finish()

