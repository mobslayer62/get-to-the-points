import 'package:flutter/material.dart';

/// Placeholder for features that are not built yet.
class ComingSoonPage extends StatelessWidget {
  final String feature;
  final IconData icon;

  const ComingSoonPage({super.key, required this.feature, required this.icon});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text(feature)),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 72, color: colors.primary),
            const SizedBox(height: 16),
            Text(
              '$feature is coming soon',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
        ),
      ),
    );
  }
}
