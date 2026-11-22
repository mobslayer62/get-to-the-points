import 'dart:async';

import 'package:flutter/material.dart';

import 'api_service.dart';
import 'equip_cards_page.dart' show CardArt, rarityColor;
import 'story_widgets.dart';

/// Visual-novel reader. Characters stand on screen while they are in the
/// scene (the server sends who is on stage for every line); whoever is
/// speaking is highlighted and the others are dimmed. The current place is
/// shown at the top of the stage.
/// Tap anywhere: if the line is still typing, show it all; otherwise go to
/// the next line. The last tap marks the chapter as read.
class StoryReaderPage extends StatefulWidget {
  final String chapterId;
  final String title;

  const StoryReaderPage({
    super.key,
    required this.chapterId,
    required this.title,
  });

  @override
  State<StoryReaderPage> createState() => _StoryReaderPageState();
}

class _StoryReaderPageState extends State<StoryReaderPage> {
  static const _typingSpeed = Duration(milliseconds: 25);

  List<dynamic>? _lines;
  List<dynamic> _cast = [];
  String? _error;
  int _index = 0;
  int _visibleChars = 0;
  bool _finished = false;
  List<Map<String, dynamic>> _rewards = [];
  Timer? _typer;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _typer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final data = await ApiService.getChapter(widget.chapterId);
      if (!mounted) return;
      setState(() {
        _cast = data['cast'] as List<dynamic>? ?? [];
        _lines = data['lines'] as List<dynamic>? ?? [];
      });
      _startTyping();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Map<String, dynamic> get _line => _lines![_index] as Map<String, dynamic>;
  String get _currentText => (_line['text'] as String?) ?? '';
  String get _speakerKey => (_line['speaker'] as String?) ?? '';
  bool get _isTyping => _visibleChars < _currentText.length;
  String get _scene => (_line['scene'] as String?) ?? '';

  /// Whether a cast member is on stage for the current line.
  /// Older chapters without "on_stage" show the whole cast.
  bool _isOnStage(dynamic member) {
    final onStage = _line['on_stage'] as List<dynamic>?;
    return onStage == null || onStage.contains(member['key']);
  }

  Map<String, dynamic>? get _speaker {
    for (final member in _cast) {
      if (member['key'] == _speakerKey) return member as Map<String, dynamic>;
    }
    return null;
  }

  void _startTyping() {
    _typer?.cancel();
    if (_lines == null || _lines!.isEmpty) return;
    setState(() => _visibleChars = 0);
    _typer = Timer.periodic(_typingSpeed, (timer) {
      if (!mounted || !_isTyping) {
        timer.cancel();
        return;
      }
      setState(() => _visibleChars++);
    });
  }

  void _onTap() {
    final lines = _lines;
    if (lines == null || lines.isEmpty || _finished) return;

    if (_isTyping) {
      _typer?.cancel();
      setState(() => _visibleChars = _currentText.length);
    } else if (_index < lines.length - 1) {
      setState(() => _index++);
      _startTyping();
    } else {
      _finish();
    }
  }

  Future<void> _finish() async {
    setState(() => _finished = true);
    try {
      final result = await ApiService.completeChapter(widget.chapterId);
      if (!mounted) return;
      setState(() {
        _rewards = (result['rewards'] as List<dynamic>? ?? [])
            .cast<Map<String, dynamic>>();
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Progress not saved: ${e.message}')),
      );
    }
  }

  Alignment _alignmentFor(String? position) {
    switch (position) {
      case 'left':
        return const Alignment(-0.75, 1);
      case 'right':
        return const Alignment(0.75, 1);
      default:
        return const Alignment(0, 1);
    }
  }

  @override
  Widget build(BuildContext context) {
    final lines = _lines;

    Widget content;
    if (_error != null) {
      content = Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_error!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white)),
        ),
      );
    } else if (lines == null) {
      content = const Center(child: CircularProgressIndicator());
    } else if (_finished) {
      content = _EndPanel(title: widget.title, rewards: _rewards);
    } else if (lines.isEmpty) {
      content = const Center(
        child: Text('This chapter is empty.',
            style: TextStyle(color: Colors.white)),
      );
    } else {
      final speaker = _speaker;
      content = GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _onTap,
        child: Column(
          children: [
            // ----- Stage: background + characters -----
            Expanded(
              child: LayoutBuilder(builder: (context, stage) {
              // Sprites fill most of the stage, up to 260 px tall.
              final spriteHeight =
                  (stage.maxHeight * 0.9).clamp(80.0, 260.0).toDouble();
              return Stack(
                children: [
                  // Where the scene takes place
                  if (_scene.isNotEmpty)
                    Positioned(
                      top: 8,
                      left: 16,
                      right: 16,
                      child: Center(child: _SceneLabel(scene: _scene)),
                    ),
                  // Characters fade in when they enter and out when they leave
                  for (final member in _cast)
                    Align(
                      alignment: _alignmentFor(member['position'] as String?),
                      child: AnimatedOpacity(
                        duration: const Duration(milliseconds: 250),
                        opacity: _isOnStage(member) ? 1 : 0,
                        child: AnimatedScale(
                          duration: const Duration(milliseconds: 200),
                          scale: member['key'] == _speakerKey ? 1.05 : 1.0,
                          alignment: Alignment.bottomCenter,
                          child: PlaceholderSprite(
                            character: member as Map<String, dynamic>,
                            height: spriteHeight,
                            dimmed: member['key'] != _speakerKey,
                          ),
                        ),
                      ),
                    ),
                ],
              );
              }),
            ),
            // ----- Dialogue box -----
            _DialogueBox(
              speakerName: speaker?['name'] as String? ?? '',
              speakerColor: colorFromHex(speaker?['color'] as String?,
                  fallback: Theme.of(context).colorScheme.primary),
              text: _currentText.substring(0, _visibleChars),
              showNextHint: !_isTyping,
              progress: '${_index + 1} / ${lines.length}',
            ),
          ],
        ),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF2B3A4A),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.white,
        title: Text(widget.title),
        leading: IconButton(
          tooltip: 'Close',
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(child: content),
    );
  }
}

/// Small pill at the top of the stage naming the current place.
class _SceneLabel extends StatelessWidget {
  final String scene;

  const _SceneLabel({required this.scene});

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 300),
      child: Container(
        key: ValueKey(scene),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.black26,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.place, size: 16, color: Colors.white70),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                scene,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: Colors.white70, fontSize: 14),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DialogueBox extends StatelessWidget {
  final String speakerName;
  final Color speakerColor;
  final String text;
  final bool showNextHint;
  final String progress;

  const _DialogueBox({
    required this.speakerName,
    required this.speakerColor,
    required this.text,
    required this.showNextHint,
    required this.progress,
  });

  @override
  Widget build(BuildContext context) {
    final isNarration = speakerName.isEmpty;

    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 160),
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: speakerColor, width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isNarration)
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: speakerColor,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                speakerName,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          Text(
            text,
            style: TextStyle(
              fontSize: 17,
              height: 1.4,
              color: Colors.black87,
              fontStyle: isNarration ? FontStyle.italic : FontStyle.normal,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Text(progress,
                  style: const TextStyle(fontSize: 12, color: Colors.black45)),
              const Spacer(),
              if (showNextHint)
                Icon(Icons.arrow_drop_down, color: speakerColor, size: 28),
            ],
          ),
        ],
      ),
    );
  }
}

class _EndPanel extends StatelessWidget {
  final String title;

  final List<Map<String, dynamic>> rewards;

  const _EndPanel({required this.title, this.rewards = const []});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.auto_stories, size: 72, color: Colors.white),
            const SizedBox(height: 16),
            Text(
              '$title complete',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 22, color: Colors.white),
            ),
            // First-time chapter rewards (e.g. a support card)
            for (final reward in rewards) ...[
              const SizedBox(height: 20),
              const Text(
                'You received a support card!',
                style: TextStyle(color: Colors.amber, fontSize: 16),
              ),
              const SizedBox(height: 8),
              Container(
                width: 160,
                height: 200,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: rarityColor(reward['rarity']), width: 3),
                ),
                child: Column(
                  children: [
                    Expanded(
                      child: CardArt(
                        card: reward,
                        color: rarityColor(reward['rarity']),
                        iconSize: 56,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      reward['name'] as String? ?? '',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.black87,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 24),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Back to story'),
            ),
          ],
        ),
      ),
    );
  }
}
