import 'package:flutter/material.dart';

import 'api_service.dart';
import 'login_page.dart';

/// Profile and settings: player stats from GET /api/player-stats/ and log out.
class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  Map<String, dynamic>? _stats;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final stats = await ApiService.getStats();
      if (!mounted) return;
      setState(() => _stats = stats);
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 401) {
        goToLoginScreen(context);
        return;
      }
      setState(() => _error = e.message);
    }
  }

  Future<void> _logout() async {
    await ApiService.logout();
    if (!mounted) return;
    goToLoginScreen(context);
  }

  String _km(dynamic meters) {
    final value = double.tryParse(meters.toString()) ?? 0;
    return '${(value / 1000).toStringAsFixed(2)} km';
  }

  @override
  Widget build(BuildContext context) {
    final stats = _stats;

    return Scaffold(
      appBar: AppBar(title: const Text('Profile & settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            leading: const Icon(Icons.person),
            title: Text(ApiService.username ?? ''),
            subtitle: const Text('Username'),
          ),
          const Divider(),
          if (_error != null)
            ListTile(
              leading: const Icon(Icons.error_outline),
              title: Text(_error!),
            )
          else if (stats == null)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            )
          else ...[
            ListTile(
              leading: const Icon(Icons.stars, color: Colors.amber),
              title: Text('${stats['total_points']}'),
              subtitle: const Text('Points'),
            ),
            ListTile(
              leading: const Icon(Icons.route),
              title: Text(_km(stats['total_distance'])),
              subtitle: const Text('Total distance'),
            ),
            ListTile(
              leading: const Icon(Icons.flag),
              title: Text('${stats['sessions_completed']}'),
              subtitle: const Text('Runs completed'),
            ),
            ListTile(
              leading: const Icon(Icons.emoji_events),
              title: Text(_km(stats['longest_session'])),
              subtitle: const Text('Longest run'),
            ),
          ],
          const Divider(),
          ListTile(
            leading: const Icon(Icons.dns),
            title: Text(ApiService.baseUrl),
            subtitle: const Text('Server'),
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _logout,
            icon: const Icon(Icons.logout),
            label: const Text('Log out'),
          ),
        ],
      ),
    );
  }
}
