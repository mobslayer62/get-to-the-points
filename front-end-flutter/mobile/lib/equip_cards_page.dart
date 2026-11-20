import 'package:flutter/material.dart';

import 'api_service.dart';
import 'login_page.dart';

/// Pick up to 4 unique cards to bring into your runs.
/// Tap an owned card to equip it; tap an equipped card (or its slot) to
/// remove it. The loadout is saved to the server with the Save button.
class EquipCardsPage extends StatefulWidget {
  const EquipCardsPage({super.key});

  @override
  State<EquipCardsPage> createState() => _EquipCardsPageState();
}

class _EquipCardsPageState extends State<EquipCardsPage> {
  List<Map<String, dynamic>> _owned = [];
  final List<int> _equipped = []; // card ids, in slot order
  List<int> _saved = [];
  int _maxSlots = 4;

  bool _loading = true;
  bool _saving = false;
  String? _error;

  bool get _dirty =>
      _equipped.length != _saved.length ||
      Iterable.generate(_equipped.length)
          .any((i) => _equipped[i] != _saved[i]);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final results = await Future.wait([
        ApiService.getCardStorage(),
        ApiService.getEquippedCards(),
      ]);
      if (!mounted) return;
      final storage = results[0];
      final loadout = results[1];
      final equippedIds = (loadout['cards'] as List<dynamic>)
          .map((c) => c['card_id'] as int)
          .toList();
      setState(() {
        _owned = (storage['cards'] as List<dynamic>)
            .cast<Map<String, dynamic>>();
        _maxSlots = loadout['max_slots'] as int? ?? 4;
        _equipped
          ..clear()
          ..addAll(equippedIds);
        _saved = List.of(equippedIds);
        _error = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 401) {
        goToLoginScreen(context);
        return;
      }
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toggle(int cardId) {
    setState(() {
      if (_equipped.contains(cardId)) {
        _equipped.remove(cardId);
      } else if (_equipped.length < _maxSlots) {
        _equipped.add(cardId);
      }
    });
  }

  void _onCardTap(int cardId) {
    if (!_equipped.contains(cardId) && _equipped.length >= _maxSlots) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: Text('All $_maxSlots slots are full. Remove a card first.'),
        ));
      return;
    }
    _toggle(cardId);
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final result = await ApiService.setEquippedCards(_equipped);
      if (!mounted) return;
      final ids = (result['cards'] as List<dynamic>)
          .map((c) => c['card_id'] as int)
          .toList();
      setState(() => _saved = ids);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Loadout saved')),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 401) {
        goToLoginScreen(context);
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Map<String, dynamic>? _cardById(int id) {
    for (final c in _owned) {
      if (c['card_id'] == id) return c;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    Widget body;
    if (_loading) {
      body = const Center(child: CircularProgressIndicator());
    } else if (_error != null) {
      body = Center(child: Text(_error!, textAlign: TextAlign.center));
    } else {
      body = Column(
        children: [
          _buildSlots(context),
          const Divider(height: 1),
          Expanded(
            child: _owned.isEmpty
                ? const Center(
                    child: Text('No cards yet. Earn points and pull from the gacha!'),
                  )
                : _buildOwnedGrid(),
          ),
        ],
      );
    }

    return PopScope(
      canPop: !_dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final leave = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Discard changes?'),
            content: const Text('Your loadout changes have not been saved.'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Keep editing'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Discard'),
              ),
            ],
          ),
        );
        if (leave == true && context.mounted) Navigator.of(context).pop();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text('Equip cards (${_equipped.length}/$_maxSlots)'),
          actions: [
            TextButton(
              onPressed: _saving || !_dirty ? null : _save,
              child: _saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save'),
            ),
          ],
        ),
        body: body,
      ),
    );
  }

  Widget _buildSlots(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: List.generate(_maxSlots, (i) {
          final card = i < _equipped.length ? _cardById(_equipped[i]) : null;
          final color =
              card == null ? colors.outlineVariant : rarityColor(card['rarity']);
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: AspectRatio(
                aspectRatio: 0.75,
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: card == null ? null : () => _toggle(_equipped[i]),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: color, width: 2),
                      color: card == null
                          ? colors.surfaceContainerHighest
                          : color.withValues(alpha: 0.12),
                    ),
                    padding: const EdgeInsets.all(6),
                    child: card == null
                        ? Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.add, color: colors.onSurfaceVariant),
                              Text(
                                'Slot ${i + 1}',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: colors.onSurfaceVariant,
                                ),
                              ),
                            ],
                          )
                        : Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Expanded(
                                child: CardArt(
                                  card: card,
                                  color: color,
                                  iconSize: 24,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                card['name'] as String? ?? '',
                                maxLines: 2,
                                textAlign: TextAlign.center,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                  ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildOwnedGrid() {
    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 0.8,
      ),
      itemCount: _owned.length,
      itemBuilder: (context, i) {
        final c = _owned[i];
        final id = c['card_id'] as int;
        final rarity = c['rarity'] as String? ?? 'A';
        final color = rarityColor(rarity);
        final slotIndex = _equipped.indexOf(id);
        final isEquipped = slotIndex != -1;

        return Card(
          clipBehavior: Clip.antiAlias,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: color, width: isEquipped ? 3 : 1),
          ),
          child: InkWell(
            onTap: () => _onCardTap(id),
            child: Stack(
              children: [
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: Column(
                    children: [
                      Align(
                        alignment: Alignment.topLeft,
                        child: Text(
                          rarity,
                          style: TextStyle(
                            color: color,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: CardArt(card: c, color: color),
                        ),
                      ),
                      Text(
                        c['name'] as String? ?? '',
                        maxLines: 2,
                        textAlign: TextAlign.center,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                if (isEquipped)
                  Positioned(
                    top: 6,
                    right: 6,
                    child: CircleAvatar(
                      radius: 11,
                      backgroundColor: color,
                      child: Text(
                        '${slotIndex + 1}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// Short text for a card's benefits (passive and special), e.g.
/// "+15% points · +50 every 5 km total". Returns null for cards with no effect.
String? effectLabel(Map<String, dynamic> card) {
  final parts = [_passiveLabel(card), _specialLabel(card)].whereType<String>();
  return parts.isEmpty ? null : parts.join(' · ');
}

String? _passiveLabel(Map<String, dynamic> card) {
  final value = card['effect_value'] as int? ?? 0;
  switch (card['effect_type']) {
    case 'points_percent':
      return '+$value% points';
    case 'walk_points_percent':
      return '+$value% points on walks';
    case 'run_points_percent':
      return '+$value% points on runs';
    case 'flat_points':
      return '+$value points per run';
    default:
      return null;
  }
}

String? _specialLabel(Map<String, dynamic> card) {
  final value = card['special_value'] as int? ?? 0;
  final threshold = card['special_threshold'] as int? ?? 0;
  if (threshold <= 0) return null;
  switch (card['special_type']) {
    case 'distance_milestone':
      return '+$value every ${_distanceText(threshold)} total';
    case 'walk_distance':
      return '+$value per ${_distanceText(threshold)} walked';
    case 'run_distance':
      return '+$value per ${_distanceText(threshold)} run';
    case 'min_duration':
      return '+$value for runs of $threshold+ min';
    default:
      return null;
  }
}

String _distanceText(int meters) {
  if (meters % 1000 == 0) return '${meters ~/ 1000} km';
  return '$meters m';
}

/// Turns a Google Drive share link into a link to the image itself.
/// Drive links like .../file/d/<id>/view or ...?id=<id> open Google's
/// preview page, which can't be drawn as an image. Other links pass through.
String cardImageUrl(Object? raw) {
  final url = (raw as String? ?? '').trim();
  if (url.isEmpty) return '';
  final uri = Uri.tryParse(url);
  if (uri == null || uri.host != 'drive.google.com') return url;

  String? id = uri.queryParameters['id'];
  final segments = uri.pathSegments;
  final d = segments.indexOf('d');
  if (d != -1 && d + 1 < segments.length) id = segments[d + 1];

  return id == null ? url : 'https://lh3.googleusercontent.com/d/$id';
}

/// A card's art from its image_url, or the plain card icon when it has
/// none or the image fails to load.
class CardArt extends StatelessWidget {
  const CardArt({
    super.key,
    required this.card,
    required this.color,
    this.iconSize = 36,
  });

  final Map<String, dynamic> card;
  final Color color;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    final icon = Center(child: Icon(Icons.style, size: iconSize, color: color));
    final url = cardImageUrl(card['image_url']);
    if (url.isEmpty) return icon;

    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Image.network(
        url,
        fit: BoxFit.contain,
        // On web, hosts that block cross-site loading (e.g. Google Drive)
        // are shown with a plain <img> element instead.
        webHtmlElementStrategy: WebHtmlElementStrategy.fallback,
        loadingBuilder: (context, child, progress) => progress == null
            ? child
            : const Center(
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
        errorBuilder: (context, error, stack) => icon,
      ),
    );
  }
}

/// Shared rarity colours (also used by the Cards page).
Color rarityColor(Object? rarity) {
  switch (rarity) {
    case 'S':
      return Colors.amber.shade700;
    case 'A+':
      return Colors.purple;
    default:
      return Colors.blueGrey;
  }
}
