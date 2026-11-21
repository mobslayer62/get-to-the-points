import 'package:flutter/material.dart';

/// Parses "#RRGGBB" from the server into a Color.
Color colorFromHex(String? hex, {Color fallback = Colors.grey}) {
  if (hex == null) return fallback;
  final clean = hex.replaceFirst('#', '');
  final value = int.tryParse(clean, radix: 16);
  if (value == null || clean.length != 6) return fallback;
  return Color(0xFF000000 | value);
}

/// Placeholder character art: a coloured head-and-body silhouette with the
/// character's letter on it. Replace with real sprite images later
/// (the server already sends an empty "sprite" field for that).
class PlaceholderSprite extends StatelessWidget {
  final Map<String, dynamic> character;
  final double height;
  final bool dimmed;

  const PlaceholderSprite({
    super.key,
    required this.character,
    required this.height,
    this.dimmed = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = colorFromHex(character['color'] as String?);
    final name = (character['name'] as String?) ?? '?';
    final letter = name.trim().isEmpty ? '?' : name.trim().split(' ').last[0];
    final head = height * 0.3;

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200),
      opacity: dimmed ? 0.45 : 1,
      child: SizedBox(
        height: height,
        width: height * 0.55,
        child: Column(
          children: [
            Container(
              width: head,
              height: head,
              decoration: BoxDecoration(
                color: color,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 3),
              ),
            ),
            SizedBox(height: height * 0.02),
            Expanded(
              child: Container(
                width: height * 0.5,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: color,
                  border: Border.all(color: Colors.white, width: 3),
                  borderRadius: BorderRadius.vertical(
                    top: Radius.circular(height * 0.2),
                  ),
                ),
                child: Text(
                  letter,
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: height * 0.15,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
