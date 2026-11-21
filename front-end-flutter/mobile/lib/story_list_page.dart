import 'package:flutter/material.dart';

import 'api_service.dart';
import 'tutorial.dart';
import 'level_widgets.dart';
import 'login_page.dart';
import 'story_reader_page.dart';
import 'story_widgets.dart';

/// Story tab: a host character at the top, the level-up card, then the
/// chapter list. Lock rules and costs come from the server (progression.py).
class StoryListPage extends StatefulWidget {
  const StoryListPage({super.key});

  @override
  State<StoryListPage> createState() => _StoryListPageState();
}

class _StoryListPageState extends State<StoryListPage> {
  Map<String, dynamic>? _level;
  List<dynamic>? _chapters;
  String? _error;
  bool _levelingUp = false;

  @override
  void initState() {
    super.initState();
    TutorialController.instance.report('open_story');
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await ApiService.getStory();
      if (!mounted) return;
      setState(() {
        _level = data['level'] as Map<String, dynamic>?;
        _chapters = data['chapters'] as List<dynamic>? ?? [];
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

  Future<void> _openChapter(Map<String, dynamic> chapter) async {
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => StoryReaderPage(
        chapterId: chapter['id'] as String,
        title: chapter['title'] as String,
      ),
    ));
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    final chapters = _chapters;

    Widget body;
    if (_error != null) {
      body = Center(child: Text(_error!, textAlign: TextAlign.center));
    } else if (chapters == null || _level == null) {
      body = const Center(child: CircularProgressIndicator());
    } else {
      final host = chapters.isEmpty
          ? null
          : chapters.first['thumbnail'] as Map<String, dynamic>?;
      body = RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            _StoryHeader(host: host),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: LevelProgressCard(
                level: _level!,
                busy: _levelingUp,
                onLevelUp: _levelUp,
              ),
            ),
            for (final c in chapters)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                child: _ChapterCard(
                  chapter: c as Map<String, dynamic>,
                  onTap: () => _openChapter(c),
                ),
              ),
            const SizedBox(height: 16),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Story')),
      // Keep content above the phone's navigation bar
      body: SafeArea(top: false, child: body),
    );
  }
}

/// Top banner: the host character with a speech bubble.
class _StoryHeader extends StatelessWidget {
  final Map<String, dynamic>? host;

  const _StoryHeader({required this.host});

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
          if (host != null) PlaceholderSprite(character: host!, height: 170),
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
                  'Placeholder: pick a chapter to read!',
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

/// One row of the chapter list: thumbnail, title, Unlocked/Locked pill.
class _ChapterCard extends StatelessWidget {
  final Map<String, dynamic> chapter;
  final VoidCallback onTap;

  const _ChapterCard({required this.chapter, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final unlocked = chapter['unlocked'] == true;
    final completed = chapter['completed'] == true;
    final thumbnail = chapter['thumbnail'] as Map<String, dynamic>?;

    return Opacity(
      opacity: unlocked ? 1 : 0.6,
      child: Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: colors.outlineVariant),
        ),
        child: InkWell(
          onTap: unlocked ? onTap : null,
          child: SizedBox(
            height: 96,
            child: Row(
              children: [
                // Thumbnail with the NEW badge
                Stack(
                  children: [
                    Container(
                      width: 120,
                      color: colors.secondaryContainer,
                      alignment: Alignment.bottomCenter,
                      child: thumbnail == null
                          ? null
                          : ClipRect(
                              child: Align(
                                alignment: Alignment.topCenter,
                                heightFactor: 0.75,
                                child: PlaceholderSprite(
                                  character: thumbnail,
                                  height: 120,
                                ),
                              ),
                            ),
                    ),
                    if (unlocked && !completed)
                      Positioned(
                        top: 4,
                        left: 4,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.amber.shade600,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'NEW',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 11,
                            ),
                          ),
                        ),
                      ),
                    if (!unlocked)
                      const Positioned.fill(
                        child: Center(
                          child: Icon(Icons.lock, color: Colors.white, size: 32),
                        ),
                      ),
                  ],
                ),
                // Title and status
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(14, 10, 12, 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          chapter['title'] as String,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const Divider(height: 8),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 10, vertical: 3),
                              decoration: BoxDecoration(
                                color: colors.surfaceContainerHighest,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                unlocked ? 'Unlocked' : 'Locked',
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                            const SizedBox(width: 10),
                            if (!unlocked)
                              Text(
                                'Reach level ${chapter['required_level']}',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: colors.onSurfaceVariant,
                                ),
                              )
                            else if (completed)
                              const Row(
                                children: [
                                  Icon(Icons.check_circle,
                                      color: Colors.green, size: 18),
                                  SizedBox(width: 4),
                                  Text('Read'),
                                ],
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
      ),
    );
  }
}
