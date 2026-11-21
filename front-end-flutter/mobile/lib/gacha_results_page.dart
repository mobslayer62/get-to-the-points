import 'dart:async';

import 'package:flutter/material.dart';

import 'equip_cards_page.dart' show CardArt, effectLabel, rarityColor;

/// Shows captured cards one by one. Tap "Show all" to skip the reveal.
class GachaResultsPage extends StatefulWidget {
  final List<Map<String, dynamic>> results;

  const GachaResultsPage({super.key, required this.results});

  @override
  State<GachaResultsPage> createState() => _GachaResultsPageState();
}

class _GachaResultsPageState extends State<GachaResultsPage> {
  static const _revealDelay = Duration(milliseconds: 350);

  int _revealed = 0;
  Timer? _timer;

  bool get _allRevealed => _revealed >= widget.results.length;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(_revealDelay, (timer) {
      if (!mounted || _allRevealed) {
        timer.cancel();
        return;
      }
      setState(() => _revealed++);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _revealAll() {
    _timer?.cancel();
    setState(() => _revealed = widget.results.length);
  }

  @override
  Widget build(BuildContext context) {
    final results = widget.results;
    final single = results.length == 1;
    final bestS = results.any((r) => r['rarity'] == 'S');

    return Scaffold(
      backgroundColor: const Color(0xFF1E2A38),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.white,
        automaticallyImplyLeading: false,
        title: Text(single ? 'Captured!' : 'Captured ${results.length} cards!'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (_allRevealed && bestS)
              const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Text(
                  '★ S card! ★',
                  style: TextStyle(
                    color: Colors.amber,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            Expanded(
              child: GridView.builder(
                padding: const EdgeInsets.all(12),
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: single ? 1 : 2,
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                  childAspectRatio: single ? 0.9 : 0.85,
                ),
                itemCount: results.length,
                itemBuilder: (context, i) => AnimatedSwitcher(
                  duration: const Duration(milliseconds: 300),
                  transitionBuilder: (child, animation) => ScaleTransition(
                    scale: animation,
                    child: FadeTransition(opacity: animation, child: child),
                  ),
                  child: i < _revealed
                      ? _ResultCard(
                          key: ValueKey('card-$i'),
                          card: results[i],
                          big: single,
                        )
                      : const _HiddenCard(key: ValueKey('hidden')),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
              child: SizedBox(
                width: double.infinity,
                child: _allRevealed
                    ? FilledButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('OK'),
                      )
                    : OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _revealAll,
                        child: const Text('Show all'),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HiddenCard extends StatelessWidget {
  const _HiddenCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white10,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white24),
      ),
      child: const Center(
        child: Icon(Icons.help_outline, color: Colors.white38, size: 40),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  final Map<String, dynamic> card;
  final bool big;

  const _ResultCard({super.key, required this.card, required this.big});

  @override
  Widget build(BuildContext context) {
    final rarity = card['rarity'] as String? ?? 'A';
    final color = rarityColor(rarity);
    final isS = rarity == 'S';
    final effect = effectLabel(card);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color, width: isS ? 4 : 2),
      ),
      padding: const EdgeInsets.all(10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  rarity,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const Spacer(),
              if (card['is_new'] == true)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.red,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text(
                    'NEW',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
            ],
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: CardArt(card: card, color: color, iconSize: big ? 96 : 48),
            ),
          ),
          Text(
            card['name'] as String? ?? '',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: big ? 20 : 14,
              fontWeight: FontWeight.bold,
              color: Colors.black87,
            ),
          ),
          if (effect != null)
            Text(
              effect,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: big ? 14 : 11,
                color: Colors.green.shade700,
                fontWeight: FontWeight.w600,
              ),
            ),
          if (card['pity'] == true)
            const Text('Pity guarantee',
                style: TextStyle(fontSize: 11, color: Colors.black54)),
          if (card['guaranteed'] == true)
            const Text('×10 guarantee',
                style: TextStyle(fontSize: 11, color: Colors.black54)),
        ],
      ),
    );
  }
}
