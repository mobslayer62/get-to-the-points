import 'package:flutter/material.dart';

import 'api_service.dart';
import 'tutorial.dart';
import 'equip_cards_page.dart' show rarityColor;
import 'gacha_results_page.dart';
import 'login_page.dart';

/// Capture screen (the gacha): banner with rates and the pity counter,
/// capture x1 / x10.
/// Costs, rates, pity and the actual rolls all come from the server
/// (backend/Database/gacha.py).
class GachaPage extends StatefulWidget {
  const GachaPage({super.key});

  @override
  State<GachaPage> createState() => _GachaPageState();
}

class _GachaPageState extends State<GachaPage> {
  Map<String, dynamic>? _info;
  String? _error;
  bool _pulling = false;

  @override
  void initState() {
    super.initState();
    TutorialController.instance.report('open_capture');
    _load();
  }

  Future<void> _load() async {
    try {
      final info = await ApiService.getGacha();
      if (!mounted) return;
      setState(() {
        _info = info;
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

  Future<void> _pull(int count) async {
    final info = _info;
    if (info == null) return;
    final cost = count == 1 ? info['single_cost'] as int : info['ten_cost'] as int;
    final points = info['points'] as int;

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(count == 1 ? 'Capture 1 card?' : 'Capture $count cards?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.stars, color: Colors.amber),
                const SizedBox(width: 6),
                Text('$cost points',
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 4),
            Text('$points → ${points - cost} after capturing'),
            if (count > 1) ...[
              const SizedBox(height: 8),
              const Text('At least one A+ or better guaranteed.',
                  textAlign: TextAlign.center),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Capture'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    setState(() => _pulling = true);
    try {
      final data = await ApiService.pullGacha(count);
      if (!mounted) return;
      setState(() => _info = data['gacha'] as Map<String, dynamic>);
      await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => GachaResultsPage(
          results: (data['results'] as List<dynamic>)
              .cast<Map<String, dynamic>>(),
        ),
      ));
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _pulling = false);
    }
  }

  void _showRates() {
    final info = _info;
    if (info == null) return;
    final rates = info['rates'] as List<dynamic>;
    final pool = info['pool'] as Map<String, dynamic>;

    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Rates & cards'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final r in rates) ...[
                Row(
                  children: [
                    _RarityBadge(rarity: r['rarity'] as String),
                    const SizedBox(width: 8),
                    Text('${r['percent']}%',
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 4),
                for (final name in (pool[r['rarity']] as List<dynamic>? ?? []))
                  Padding(
                    padding: const EdgeInsets.only(left: 8, bottom: 2),
                    child: Text('• $name'),
                  ),
                const SizedBox(height: 10),
              ],
              Text(
                'Pity: if you get no S card in ${info['pity_pulls'] - 1} captures, '
                'capture ${info['pity_pulls']} is a guaranteed S '
                '(one you don\'t own yet, if possible).',
              ),
              const SizedBox(height: 6),
              const Text('Each card in a rarity has the same chance.'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final info = _info;

    Widget body;
    if (_error != null) {
      body = Center(child: Text(_error!, textAlign: TextAlign.center));
    } else if (info == null) {
      body = const Center(child: CircularProgressIndicator());
    } else {
      final pityTotal = info['pity_pulls'] as int;
      final since = info['pulls_since_s'] as int;
      final untilPity = info['pulls_until_pity'] as int;

      body = RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _Banner(rates: info['rates'] as List<dynamic>),
            const SizedBox(height: 16),

            // Points
            Row(
              children: [
                const Icon(Icons.stars, color: Colors.amber),
                const SizedBox(width: 6),
                Text(
                  '${info['points']} points',
                  style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                TextButton.icon(
                  onPressed: _showRates,
                  icon: const Icon(Icons.info_outline),
                  label: const Text('Rates'),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Pity counter
            Card(
              margin: EdgeInsets.zero,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const _RarityBadge(rarity: 'S'),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            untilPity == 1
                                ? 'Next capture is a guaranteed S!'
                                : 'S guaranteed within $untilPity captures',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    LinearProgressIndicator(
                      value: (since / pityTotal).clamp(0.0, 1.0).toDouble(),
                      minHeight: 8,
                      borderRadius: BorderRadius.circular(4),
                      color: rarityColor('S'),
                    ),
                    const SizedBox(height: 4),
                    Text('$since / $pityTotal captures since your last S'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Pull buttons
            Row(
              children: [
                Expanded(
                  child: _PullButton(
                    label: 'Capture ×1',
                    cost: info['single_cost'] as int,
                    enabled: info['can_single'] == true && !_pulling,
                    filled: false,
                    onPressed: () => _pull(1),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _PullButton(
                    label: 'Capture ×${info['ten_size']}',
                    cost: info['ten_cost'] as int,
                    enabled: info['can_ten'] == true && !_pulling,
                    filled: true,
                    onPressed: () => _pull(info['ten_size'] as int),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              '×10 includes at least one A+ or better.',
              textAlign: TextAlign.center,
            ),
            if (_pulling)
              const Padding(
                padding: EdgeInsets.only(top: 16),
                child: Center(child: CircularProgressIndicator()),
              ),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Capture')),
      // Keep content above the phone's navigation bar
      body: SafeArea(top: false, child: body),
    );
  }
}

/// Placeholder banner art with the headline rates.
class _Banner extends StatelessWidget {
  final List<dynamic> rates;

  const _Banner({required this.rates});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      height: 170,
      decoration: BoxDecoration(
        color: colors.primaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Icon(Icons.camera_alt, size: 72, color: rarityColor('S')),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  'Capture Support Cards',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: colors.onPrimaryContainer,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final r in rates)
                      _RarityBadge(
                        rarity: r['rarity'] as String,
                        suffix: ' ${r['percent']}%',
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RarityBadge extends StatelessWidget {
  final String rarity;
  final String suffix;

  const _RarityBadge({required this.rarity, this.suffix = ''});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: rarityColor(rarity),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        '$rarity$suffix',
        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
      ),
    );
  }
}

class _PullButton extends StatelessWidget {
  final String label;
  final int cost;
  final bool enabled;
  final bool filled;
  final VoidCallback onPressed;

  const _PullButton({
    required this.label,
    required this.cost,
    required this.enabled,
    required this.filled,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final child = Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(
        children: [
          Text(label, style: const TextStyle(fontSize: 18)),
          Text('$cost pts'),
        ],
      ),
    );
    final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(14));
    return filled
        ? FilledButton(
            onPressed: enabled ? onPressed : null,
            style: FilledButton.styleFrom(shape: shape),
            child: child,
          )
        : OutlinedButton(
            onPressed: enabled ? onPressed : null,
            style: OutlinedButton.styleFrom(shape: shape),
            child: child,
          );
  }
}
