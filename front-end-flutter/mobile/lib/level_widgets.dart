import 'package:flutter/material.dart';

import 'api_service.dart';

/// Shows the level-up confirmation popup and, if confirmed, levels up.
///
/// [level] is the level summary from the server (story or level tab).
/// Returns true if the player levelled up, so the caller can refresh.
/// Used by both the Story tab and the Level tab.
Future<bool> confirmAndLevelUp(
  BuildContext context,
  Map<String, dynamic> level,
) async {
  final current = level['level'] as int;
  final next = level['next_level'] as int?;
  final cost = level['next_level_cost'] as int?;
  if (next == null || cost == null) return false;

  final rewards = (level['next_level_rewards'] as List<dynamic>? ?? [])
      .map((r) => r['title'] as String)
      .toList();

  final ok = await showDialog<bool>(
    context: context,
    builder: (context) => _LevelUpDialog(
      current: current,
      next: next,
      cost: cost,
      points: level['points'] as int,
      rewards: rewards,
    ),
  );
  if (ok != true || !context.mounted) return false;

  try {
    final result = await ApiService.levelUp();
    if (!context.mounted) return true;
    final reached = result['level']['level'];
    final unlocked = (result['unlocked_chapters'] as List<dynamic>)
        .map((c) => c['title'])
        .join(', ');
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(unlocked.isEmpty
          ? 'Level $reached reached!'
          : 'Level $reached reached! Unlocked: $unlocked'),
    ));
    return true;
  } on ApiException catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    }
    return false;
  }
}

class _LevelUpDialog extends StatelessWidget {
  final int current;
  final int next;
  final int cost;
  final int points;
  final List<String> rewards;

  const _LevelUpDialog({
    required this.current,
    required this.next,
    required this.cost,
    required this.points,
    required this.rewards,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return AlertDialog(
      title: const Text('Level up?', textAlign: TextAlign.center),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Level 1 -> Level 2
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _LevelBadge(level: current, highlighted: false),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Icon(Icons.arrow_forward, color: colors.primary),
              ),
              _LevelBadge(level: next, highlighted: true),
            ],
          ),
          const SizedBox(height: 16),
          // Cost
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.stars, color: Colors.amber),
              const SizedBox(width: 6),
              Text(
                '$cost points',
                style:
                    const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          Text(
            '$points → ${points - cost} after levelling up',
            style: TextStyle(color: colors.onSurfaceVariant),
          ),
          // Rewards (left blank when the level has none)
          if (rewards.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('You will get',
                style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            for (final r in rewards)
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.menu_book, size: 18, color: colors.primary),
                  const SizedBox(width: 6),
                  Flexible(child: Text(r)),
                ],
              ),
          ],
        ],
      ),
      actionsAlignment: MainAxisAlignment.spaceEvenly,
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Level up'),
        ),
      ],
    );
  }
}

class _LevelBadge extends StatelessWidget {
  final int level;
  final bool highlighted;

  const _LevelBadge({required this.level, required this.highlighted});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: highlighted ? colors.primary : colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        'Level $level',
        style: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.bold,
          color: highlighted ? colors.onPrimary : colors.onSurface,
        ),
      ),
    );
  }
}

/// Level, progress bar toward the next level, points still needed,
/// and the Level up button. Used by the Story tab and the Level tab.
class LevelProgressCard extends StatelessWidget {
  final Map<String, dynamic> level;
  final bool busy;
  final VoidCallback onLevelUp;

  const LevelProgressCard({
    super.key,
    required this.level,
    required this.busy,
    required this.onLevelUp,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final current = level['level'] as int;
    final max = level['max_level'] as int;
    final points = level['points'] as int;
    final cost = level['next_level_cost'] as int?;
    final canLevelUp = level['can_level_up'] == true;
    final nextUnlock = level['next_unlock'] as Map<String, dynamic>?;

    return Card(
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: colors.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Level $current',
                  style: const TextStyle(
                      fontSize: 20, fontWeight: FontWeight.bold),
                ),
                Text(' / $max'),
                const Spacer(),
                const Icon(Icons.stars, color: Colors.amber),
                const SizedBox(width: 4),
                Text('$points',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 8),
            if (cost == null)
              const Text('Maximum level reached.')
            else ...[
              LinearProgressIndicator(
                value: (points / cost).clamp(0.0, 1.0).toDouble(),
                minHeight: 10,
                borderRadius: BorderRadius.circular(5),
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  Text('$points / $cost points'),
                  const Spacer(),
                  Text(
                    canLevelUp
                        ? 'Ready to level up!'
                        : '${level['points_needed']} more to level ${current + 1}',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: canLevelUp ? Colors.green.shade700 : null,
                    ),
                  ),
                ],
              ),
              if (nextUnlock != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    'Next chapter: ${nextUnlock['title']} at level ${nextUnlock['required_level']}',
                    style: TextStyle(color: colors.onSurfaceVariant),
                  ),
                ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: canLevelUp && !busy ? onLevelUp : null,
                  icon: busy
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.arrow_upward),
                  label: Text('Level up ($cost pts)'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
