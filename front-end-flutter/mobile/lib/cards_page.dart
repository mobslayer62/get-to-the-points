import 'package:flutter/material.dart';

import 'api_service.dart';
import 'tutorial.dart';
import 'equip_cards_page.dart';
import 'login_page.dart';

/// The player's card collection from GET /api/card-storage/.
class CardsPage extends StatefulWidget {
  const CardsPage({super.key});

  @override
  State<CardsPage> createState() => _CardsPageState();
}

class _CardsPageState extends State<CardsPage> {
  Map<String, dynamic>? _storage;
  String? _error;

  @override
  void initState() {
    super.initState();
    TutorialController.instance.report('open_cards');
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await ApiService.getCardStorage();
      if (!mounted) return;
      setState(() {
        _storage = data;
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

  @override
  Widget build(BuildContext context) {
    final storage = _storage;
    final cards = storage?['cards'] as List<dynamic>? ?? [];

    Widget body;
    if (_error != null) {
      body = Center(child: Text(_error!, textAlign: TextAlign.center));
    } else if (storage == null) {
      body = const Center(child: CircularProgressIndicator());
    } else if (cards.isEmpty) {
      body = const Center(
        child: Text('No cards yet. Earn points and capture some!'),
      );
    } else {
      body = GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 0.8,
        ),
        itemCount: cards.length,
        itemBuilder: (context, i) {
          final c = cards[i] as Map<String, dynamic>;
          final rarity = c['rarity'] as String? ?? 'A';
          final color = rarityColor(rarity);
          return Card(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: BorderSide(color: color, width: 2),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
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
                      Text('x${c['quantity']}'),
                    ],
                  ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: CardArt(card: c, color: color, iconSize: 48),
                    ),
                  ),
                  Text(
                    c['name'] as String? ?? '',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (effectLabel(c) != null)
                    Text(
                      effectLabel(c)!,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: Colors.green.shade700,
                      ),
                    ),
                  Text(
                    c['description'] as String? ?? '',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
          );
        },
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(storage == null
            ? 'Cards'
            : 'Cards (${storage['unique_cards']} unique)'),
        actions: [
          TextButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const EquipCardsPage()),
            ),
            icon: const Icon(Icons.backpack_outlined),
            label: const Text('Equip'),
          ),
        ],
      ),
      // Keep content above the phone's navigation bar
      body: SafeArea(top: false, child: body),
    );
  }
}
