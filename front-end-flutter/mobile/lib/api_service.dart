import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Thrown when a request fails. [message] is safe to show to the player.
class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, {this.statusCode});

  @override
  String toString() => message;
}

/// Thin HTTP layer. All game rules live in the Django backend.
class ApiService {
  /// Override at run time:
  ///   flutter run --dart-define=API_BASE_URL=http://192.168.1.23:8000/api
  /// Default works for the Android emulator (10.0.2.2 = your PC).
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api',
  );

  static const Duration _timeout = Duration(seconds: 10);

  static String? _token;
  static String? username;

  static bool get isLoggedIn => _token != null;

  static Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Token $_token',
      };

  // ----- Accounts -----

  static Future<void> login(String user, String password) async {
    final data = await _send(() => http.post(
          Uri.parse('$baseUrl/login/'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'username': user, 'password': password}),
        ));
    _token = data['token'] as String?;
    username = data['username'] as String?;
  }

  static Future<void> register(String user, String password) async {
    final data = await _send(() => http.post(
          Uri.parse('$baseUrl/register/'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'username': user, 'password': password}),
        ));
    _token = data['token'] as String?;
    username = data['username'] as String?;
  }

  static Future<void> logout() async {
    try {
      await _send(() => http.post(
            Uri.parse('$baseUrl/logout/'),
            headers: _headers,
          ));
    } catch (_) {
      // Log out locally even if the server can't be reached.
    }
    _token = null;
    username = null;
  }

  // ----- Activity -----

  /// Call when the player taps Start. Locks in the equipped cards for this
  /// run; finishSession only accepts a [sessionId] that was started here.
  /// Safe to retry with the same id.
  static Future<Map<String, dynamic>> startSession(String sessionId) {
    return _send(() => http.post(
          Uri.parse('$baseUrl/start-session/'),
          headers: _headers,
          body: jsonEncode({'session_id': sessionId}),
        ));
  }

  /// [sessionId] must be the id passed to [startSession] and must stay the
  /// same if you retry, so points are never awarded twice.
  static Future<Map<String, dynamic>> finishSession({
    required String sessionId,
    required double distanceMeters,
    required int steps,
    required int durationSeconds,
  }) {
    return _send(() => http.post(
          Uri.parse('$baseUrl/finish-session/'),
          headers: _headers,
          body: jsonEncode({
            'session_id': sessionId,
            'distance': distanceMeters.toStringAsFixed(2),
            'steps': steps,
            'duration_seconds': durationSeconds,
          }),
        ));
  }

  static Future<Map<String, dynamic>> getStats() {
    return _send(() => http.get(
          Uri.parse('$baseUrl/player-stats/'),
          headers: _headers,
        ));
  }

  static Future<Map<String, dynamic>> getHistory() {
    return _send(() => http.get(
          Uri.parse('$baseUrl/activity-history/'),
          headers: _headers,
        ));
  }

  /// Everything the main menu shows, in one request.
  static Future<Map<String, dynamic>> getHome() {
    return _send(() => http.get(
          Uri.parse('$baseUrl/home/'),
          headers: _headers,
        ));
  }

  static Future<Map<String, dynamic>> getCardStorage() {
    return _send(() => http.get(
          Uri.parse('$baseUrl/card-storage/'),
          headers: _headers,
        ));
  }

  // ----- Levels and story -----

  /// Level summary + every level's cost and rewards (Level tab).
  static Future<Map<String, dynamic>> getLevel() {
    return _send(() => http.get(
          Uri.parse('$baseUrl/level/'),
          headers: _headers,
        ));
  }

  static Future<Map<String, dynamic>> levelUp() {
    return _send(() => http.post(
          Uri.parse('$baseUrl/level/up/'),
          headers: _headers,
        ));
  }

  static Future<Map<String, dynamic>> getStory() {
    return _send(() => http.get(
          Uri.parse('$baseUrl/story/'),
          headers: _headers,
        ));
  }

  static Future<Map<String, dynamic>> getChapter(String chapterId) {
    return _send(() => http.get(
          Uri.parse('$baseUrl/story/$chapterId/'),
          headers: _headers,
        ));
  }

  static Future<Map<String, dynamic>> completeChapter(String chapterId) {
    return _send(() => http.post(
          Uri.parse('$baseUrl/story/$chapterId/complete/'),
          headers: _headers,
        ));
  }

  /// The player's loadout: {max_slots, cards: [{slot, card_id, name, ...}]}.
  static Future<Map<String, dynamic>> getEquippedCards() {
    return _send(() => http.get(
          Uri.parse('$baseUrl/equipped-cards/'),
          headers: _headers,
        ));
  }

  /// Replaces the loadout. List order = slot order. The server rejects
  /// more than 4 cards, duplicates, and cards the player doesn't own.
  static Future<Map<String, dynamic>> setEquippedCards(List<int> cardIds) {
    return _send(() => http.put(
          Uri.parse('$baseUrl/equipped-cards/'),
          headers: _headers,
          body: jsonEncode({'card_ids': cardIds}),
        ));
  }

  // ----- Helpers -----

  static Future<Map<String, dynamic>> _send(
    Future<http.Response> Function() request,
  ) async {
    final http.Response res;
    try {
      res = await request().timeout(_timeout);
    } on TimeoutException {
      throw ApiException(
        'The server took too long to respond. Is Django running?',
      );
    } on http.ClientException catch (e) {
      throw ApiException('Cannot reach the server at $baseUrl\n(${e.message})');
    }

    Map<String, dynamic> body = {};
    if (res.body.isNotEmpty) {
      try {
        final decoded = jsonDecode(res.body);
        if (decoded is Map<String, dynamic>) body = decoded;
      } catch (_) {
        // Non-JSON response (e.g. Django HTML error page)
      }
    }

    if (res.statusCode >= 200 && res.statusCode < 300) {
      return body;
    }

    if (res.statusCode == 401) {
      _token = null;
      throw ApiException('Please log in again.', statusCode: 401);
    }

    throw ApiException(
      _errorMessage(body, res.statusCode),
      statusCode: res.statusCode,
    );
  }

  /// Turns Django REST Framework error bodies into one readable line.
  /// Handles {"detail": ".."}, {"error": ".."} and {"field": [".."]}.
  static String _errorMessage(Map<String, dynamic> body, int statusCode) {
    for (final key in ['detail', 'error', 'non_field_errors']) {
      final value = body[key];
      if (value is String) return value;
      if (value is List && value.isNotEmpty) return value.first.toString();
    }
    for (final entry in body.entries) {
      final value = entry.value;
      if (value is List && value.isNotEmpty) {
        return '${entry.key}: ${value.first}';
      }
      if (value is String) return value;
    }
    if (statusCode == 400 && body.isEmpty) {
      return 'Bad request (400). If you are on a phone, check ALLOWED_HOSTS.';
    }
    return 'Server error ($statusCode)';
  }
}
