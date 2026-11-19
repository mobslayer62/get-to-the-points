import 'package:flutter/material.dart';

import 'api_service.dart';
import 'login_page.dart';

/// List of past runs from GET /api/activity-history/.
class ActivityHistoryPage extends StatefulWidget {
  const ActivityHistoryPage({super.key});

  @override
  State<ActivityHistoryPage> createState() => _ActivityHistoryPageState();
}

class _ActivityHistoryPageState extends State<ActivityHistoryPage> {
  List<dynamic>? _sessions;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await ApiService.getHistory();
      if (!mounted) return;
      setState(() {
        _sessions = data['sessions'] as List<dynamic>? ?? [];
        _error = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 401) {
        goToLoginScreen(context);
        return;
      }
      setState(() => _error = e.message);
    }
  }

  String _date(String? iso) {
    final date = iso == null ? null : DateTime.tryParse(iso)?.toLocal();
    if (date == null) return '';
    String two(int n) => n.toString().padLeft(2, '0');
    return '${date.year}-${two(date.month)}-${two(date.day)} '
        '${two(date.hour)}:${two(date.minute)}';
  }

  String _duration(dynamic seconds) {
    final s = (seconds as num?)?.toInt() ?? 0;
    return '${s ~/ 60} min ${s % 60} s';
  }

  @override
  Widget build(BuildContext context) {
    final sessions = _sessions;

    Widget body;
    if (_error != null) {
      body = Center(child: Text(_error!, textAlign: TextAlign.center));
    } else if (sessions == null) {
      body = const Center(child: CircularProgressIndicator());
    } else if (sessions.isEmpty) {
      body = const Center(child: Text('No runs yet. Go for your first run!'));
    } else {
      body = RefreshIndicator(
        onRefresh: _load,
        child: ListView.separated(
          itemCount: sessions.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final s = sessions[i] as Map<String, dynamic>;
            final meters = double.tryParse(s['distance'].toString()) ?? 0;
            return ListTile(
              leading: const Icon(Icons.directions_run),
              title: Text('${(meters / 1000).toStringAsFixed(2)} km'),
              subtitle: Text(
                '${_date(s['created_at'] as String?)} · '
                '${_duration(s['duration_seconds'])} · ${s['steps']} steps',
              ),
              trailing: Text(
                '+${s['points_earned']}',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.green,
                ),
              ),
            );
          },
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Activity history')),
      body: body,
    );
  }
}
