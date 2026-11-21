import 'package:flutter/material.dart';

import 'api_service.dart';
import 'tutorial.dart';
import 'level_widgets.dart';
import 'login_page.dart';
import 'story_widgets.dart';

/// Level tab, opened from the level button on the main menu.
/// Shows progress to the next level and every level's cost and rewards.
/// All numbers come from GET /api/level/ (progression.py).
class LevelPage extends StatefulWidget {
  const LevelPage({super.key});

  @override
  State<LevelPage> createState() => _LevelPageState();
}

class _LevelPageState extends State<LevelPage> {
  Map<String, dynamic>? _level;
  String? _error;
  bool _levelingUp = false;

  /// Placeholder host character until real art exists.
  static const Map<String, dynamic> _host = {
    'name': 'Person B',
    'color': '#E0736A',
  };

  @override
  void initState() {
    super.initState();
    TutorialController.instance.report('open_level');
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await ApiService.getLevel();
      if (!mounted) return;
      setState(() {
        _level = data;
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

  Future<void> _levelUp() async {
    final level = _level;
    if (level == null) return;
    setState(() => _levelingUp = true);
    final leveled = await confirmAndLevelUp(context, level);
    if (!mounted) return;
    setState(() => _levelingUp = false);
    if (leveled) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final level = _level;

    Widget body;
    if (_error != null) {
      body = Center(child: Text(_error!, textAlign: TextAlign.center));
    } else if (level == null) {
      body = const Center(child: CircularProgressIndicator());
    } else {
      final levels = level['levels'] as List<dynamic>? ?? [];
      body = RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            const _LevelHeader(host: _host),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: TutorialTarget(
                id: 'level_card',
                child: LevelProgressCard(
                  level: level,
                  busy: _levelingUp,
                  onLevelUp: _levelUp,
                ),
              ),
            ),
            for (final lv in levels)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                child: _LevelRow(level: lv as Map<String, dynamic>),
              ),
            const SizedBox(height: 16),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Level')),
      // Keep content above the phone's navigation bar
      body: SafeArea(top: false, child: body),
    );
  }
}

class _LevelHeader extends StatelessWidget {
  final Map<String, dynamic> host;

  const _LevelHeader({required this.host});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      height: 190,
      color: colors.primaryContainer,
      padding: const EdgeInsets.fromLTRB(24, 16, 16, 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          PlaceholderSprite(character: host, height: 170),
          const SizedBox(width: 16),
          Expanded(
            child: Align(
              alignment: Alignment.center,
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Text(
                  'Placeholder: spend points to level up and unlock new chapters!',
                  style: TextStyle(fontSize: 15, color: Colors.black87),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// One level in the list: number, cost, rewards (blank if none), state.
class _LevelRow extends StatelessWidget {
  final Map<String, dynamic> level;

  const _LevelRow({required this.level});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final number = level['level'] as int;
    final cost = level['cost'] as int?;
    final reached = level['reached'] == true;
    final current = level['current'] == true;
    final rewards = (level['rewards'] as List<dynamic>? ?? [])
        .map((r) => r['title'] as String)
        .toList();

    final String status;
    if (current) {
      status = 'Current';
    } else if (reached) {
      status = 'Reached';
    } else {
      status = 'Locked';
    }

    return Opacity(
      opacity: reached ? 1 : 0.7,
      child: Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: current ? colors.primary : colors.outlineVariant,
            width: current ? 2 : 1,
          ),
        ),
        child: SizedBox(
          height: 84,
          child: Row(
            children: [
              // Level number block
              Container(
                width: 84,
                color: current ? colors.primary : colors.secondaryContainer,
                alignment: Alignment.center,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      'Lv',
                      style: TextStyle(
                        color: current
                            ? colors.onPrimary
                            : colors.onSecondaryContainer,
                      ),
                    ),
                    Text(
                      '$number',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: current
                            ? colors.onPrimary
                            : colors.onSecondaryContainer,
                      ),
                    ),
                  ],
                ),
              ),
              // Cost and rewards
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(14, 10, 12, 10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Text(
                            cost == null ? 'Starting level' : '$cost points',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          const Spacer(),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 3),
                            decoration: BoxDecoration(
                              color: current
                                  ? colors.primaryContainer
                                  : colors.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (!reached)
                                  const Padding(
                                    padding: EdgeInsets.only(right: 4),
                                    child: Icon(Icons.lock, size: 12),
                                  ),
                                Text(status,
                                    style: const TextStyle(fontSize: 12)),
                              ],
                            ),
                          ),
                        ],
                      ),
                      // Left blank for levels with no rewards
                      if (rewards.isNotEmpty)
                        Row(
                          children: [
                            Icon(Icons.menu_book,
                                size: 16, color: colors.primary),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                rewards.join(', '),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
