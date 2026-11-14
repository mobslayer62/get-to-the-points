import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';

class ApiService {
  static const String baseUrl = 'http://127.0.0.1:8000/api';   // no slash at the end

  static String? _token;

  static Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Token $_token',
      };

  static Future<bool> login(String username, String password) async {
    final res = await http.post(
      Uri.parse('$baseUrl/login/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    print('login: ${res.statusCode} ${res.body}');
    if (res.statusCode == 200) {
      _token = jsonDecode(res.body)['token'];
      return true;
    }
    return false;
  }

  static Future<Map<String, dynamic>> finishSession(double distance) async {
    final res = await http.post(
      Uri.parse('$baseUrl/finish-session/'),
      headers: _headers,
      body: jsonEncode({
        'session_id': const Uuid().v4(),
        'distance': distance.toString(),
      }),
    );
    print('finish-session: ${res.statusCode} ${res.body}');
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> getStats() async {
    final res = await http.get(Uri.parse('$baseUrl/player-stats/'), headers: _headers);
    print('player-stats: ${res.statusCode} ${res.body}');
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> getHistory() async {
    final res = await http.get(Uri.parse('$baseUrl/activity-history/'), headers: _headers);
    print('activity-history: ${res.statusCode} ${res.body}');
    return jsonDecode(res.body);
  }
}