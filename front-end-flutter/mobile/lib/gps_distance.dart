import 'dart:math' as math;

/// Live distance for the run screen.
///
/// This is a copy of the server's filter in backend/Database/gps_distance.py
/// (the server's result is the one that is saved); see that file for how it
/// works. Keep the two in step when changing either.
///
/// In short: ignore inaccurate readings, smooth the rest, and only count
/// movement once you are [minMove] metres from the last counted point, and
/// only if the step counter says you took steps. Standing still never adds
/// distance and GPS wobble doesn't inflate a walk.
class DistanceFilter {
  static const double maxAccuracy = 25.0; // metres
  static const double minAccuracy = 3.0; // metres
  static const double processNoise = 4.0; // m/s
  static const double minMove = 10.0; // metres
  static const double maxSpeed = 12.0; // m/s
  static const double _earthRadius = 6371008.8; // metres

  double distance = 0;

  double? _lat, _lng; // smoothed position
  double _variance = 0;
  double _time = 0;
  _Point? _anchor; // last counted point
  _Point? _last; // last good raw reading

  /// Add one GPS reading. [seconds] is the time since the run started,
  /// [steps] the steps since the run started (-1 if the step counter is off).
  /// Returns the distance so far.
  double add(double lat, double lng, double accuracy, double seconds,
      int steps) {
    if (!_valid(lat, lng, accuracy)) return distance;
    accuracy = math.max(accuracy, minAccuracy);
    if (_last != null && seconds < _last!.time) return distance;
    _last = _Point(lat, lng, seconds, steps);

    // Smooth (a small Kalman filter).
    if (_lat == null) {
      _lat = lat;
      _lng = lng;
      _variance = accuracy * accuracy;
      _time = seconds;
      _anchor = _Point(lat, lng, seconds, steps);
      return distance;
    }
    final dt = seconds - _time;
    _variance += dt * processNoise * processNoise;
    _time = seconds;
    final gain = _variance / (_variance + accuracy * accuracy);
    _lat = _lat! + gain * (lat - _lat!);
    _lng = _lng! + gain * (lng - _lng!);
    _variance *= 1 - gain;

    // Count only real movement.
    final a = _anchor!;
    final moved = haversine(a.lat, a.lng, _lat!, _lng!);
    if (moved < minMove) return distance;
    final elapsed = seconds - a.time;
    if (elapsed > 0 && moved / elapsed > maxSpeed) {
      // A GPS glitch: forget the jump.
      _lat = a.lat;
      _lng = a.lng;
      return distance;
    }
    if (steps >= 0 && a.steps >= 0 && steps <= a.steps) {
      // No steps taken since the last counted point: it's GPS drift.
      return distance;
    }
    distance += moved;
    _anchor = _Point(_lat!, _lng!, seconds, steps);
    return distance;
  }

  /// Call once when the run stops: adds the last few metres that the
  /// smoothing hasn't caught up with yet.
  double finish() {
    final a = _anchor, last = _last;
    if (a == null || last == null) return distance;
    final gap = haversine(a.lat, a.lng, last.lat, last.lng);
    final elapsed = last.time - a.time;
    final walked = last.steps < 0 || a.steps < 0 || last.steps > a.steps;
    if (gap >= minMove / 2 &&
        walked &&
        (elapsed <= 0 || gap / elapsed <= maxSpeed)) {
      distance += gap;
      _anchor = last;
    }
    return distance;
  }

  static bool _valid(double lat, double lng, double accuracy) =>
      lat >= -90 &&
      lat <= 90 &&
      lng >= -180 &&
      lng <= 180 &&
      !(lat == 0 && lng == 0) &&
      accuracy > 0 &&
      accuracy <= maxAccuracy;

  /// Distance in metres between two latitude/longitude points.
  static double haversine(double lat1, double lng1, double lat2, double lng2) {
    double rad(double d) => d * math.pi / 180;
    final p1 = rad(lat1), p2 = rad(lat2);
    final dp = p2 - p1, dl = rad(lng2 - lng1);
    final h = math.pow(math.sin(dp / 2), 2) +
        math.cos(p1) * math.cos(p2) * math.pow(math.sin(dl / 2), 2);
    return 2 * _earthRadius * math.asin(math.min(1.0, math.sqrt(h)));
  }
}

class _Point {
  final double lat, lng, time;
  final int steps;
  const _Point(this.lat, this.lng, this.time, this.steps);
}
