import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'activity_history_page.dart';
import 'api_service.dart';
import 'cards_page.dart';
import 'coming_soon_page.dart';
import 'gacha_page.dart';
import 'level_page.dart';
import 'login_page.dart';
import 'main.dart';
import 'profile_page.dart';
import 'story_list_page.dart';
import 'tutorial.dart';

/// Main menu. All numbers shown here come from GET /api/home/.
class MainMenuPage extends StatefulWidget {
  /// True right after sign-up: the tutorial starts by itself.
  final bool startTutorial;

  const MainMenuPage({super.key, this.startTutorial = false});

  @override
  State<MainMenuPage> createState() => _MainMenuPageState();
}

class _MainMenuPageState extends State<MainMenuPage> {
  Map<String, dynamic>? _home;
  String? _error;
  bool _loading = true;
  bool _tutorialAutoStarted = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _startTutorial() async {
    final ok = await TutorialController.instance.start();
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not load the tutorial. Try again later.')),
      );
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final home = await ApiService.getHome();
      if (!mounted) return;
      setState(() => _home = home);
      if (widget.startTutorial && !_tutorialAutoStarted) {
        _tutorialAutoStarted = true;
        _startTutorial();
      }
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

  /// Opens a screen, then refreshes the menu when the player comes back
  /// (points or cards may have changed).
  Future<void> _open(Widget page) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));
    TutorialController.instance.report('home');
    if (mounted) _load();
  }

  void _comingSoon(String feature, IconData icon) {
    _open(ComingSoonPage(feature: feature, icon: icon));
  }

  Future<void> _confirmExit() async {
    final exit = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Exit the game?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Exit'),
          ),
        ],
      ),
    );
    if (exit == true) {
      await SystemNavigator.pop();
    }
  }

  String get _statsSubtitle {
    final recent = _home?['recent_sessions'] as List<dynamic>?;
    if (recent == null) return '...';
    if (recent.isEmpty) return 'No runs yet';
    final meters = double.tryParse(recent.first['distance'].toString()) ?? 0;
    return 'Last run: ${(meters / 1000).toStringAsFixed(2)} km';
  }

  String get _storySubtitle {
    final story = _home?['story'] as Map<String, dynamic>?;
    if (story == null) return '...';
    final next = story['next_to_read'] as String?;
    if (next != null) return next;
    return '${story['unlocked']} / ${story['total']} unlocked';
  }

  String get _gachaSubtitle {
    final gacha = _home?['gacha'] as Map<String, dynamic>?;
    if (gacha == null) return '...';
    return 'S within ${gacha['pulls_until_pity']} captures';
  }

  String get _cardsSubtitle {
    final cards = _home?['cards'] as Map<String, dynamic>?;
    if (cards == null) return '...';
    return '${cards['unique_owned']} / ${cards['catalog_size']}';
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final username = _home?['username'] as String? ?? ApiService.username ?? '';
    final points = _home?['total_points'];
    final level = (_home?['level'] as Map<String, dynamic>?)?['level'];

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
            children: [
              // ----- Header: title + profile button with points -----
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Get to the Points',
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: colors.primary,
                              ),
                        ),
                        if (username.isNotEmpty)
                          Text('Welcome back, $username'),
                        if (level != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            // Tap to open the Level tab
                            child: TutorialTarget(
                              id: 'home_level',
                              child: ActionChip(
                              visualDensity: VisualDensity.compact,
                              avatar: const Icon(Icons.trending_up, size: 18),
                              label: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text('Level $level'),
                                  const Icon(Icons.chevron_right, size: 18),
                                ],
                              ),
                              onPressed: () => _open(const LevelPage()),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                  Column(
                    children: [
                      TutorialTarget(
                        id: 'home_profile',
                        child: InkWell(
                        customBorder: const CircleBorder(),
                        onTap: () => _open(const ProfilePage()),
                        child: CircleAvatar(
                          radius: 28,
                          backgroundColor: colors.primaryContainer,
                          child: Text(
                            username.isEmpty ? '?' : username[0].toUpperCase(),
                            style: TextStyle(
                              fontSize: 24,
                              color: colors.onPrimaryContainer,
                            ),
                          ),
                        ),
                      ),
                      ),
                      const SizedBox(height: 6),
                      TutorialTarget(
                        id: 'home_points',
                        child: Row(
                        children: [
                          const Icon(Icons.stars, size: 18, color: Colors.amber),
                          const SizedBox(width: 4),
                          Text(
                            points == null ? '...' : '$points',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                      ),
                    ],
                  ),
                ],
              ),

              if (_error != null) ...[
                const SizedBox(height: 12),
                Card(
                  color: colors.errorContainer,
                  child: ListTile(
                    title: Text(
                      _error!,
                      style: TextStyle(color: colors.onErrorContainer),
                    ),
                    trailing: TextButton(
                      onPressed: _load,
                      child: const Text('Retry'),
                    ),
                  ),
                ),
              ],

              if (_loading && _home == null)
                const Padding(
                  padding: EdgeInsets.only(top: 12),
                  child: LinearProgressIndicator(),
                ),

              const SizedBox(height: 24),

              // ----- Start tracking -----
              TutorialTarget(
                id: 'home_start_run',
                child: SizedBox(
                height: 96,
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  onPressed: () => _open(const LocationPage()),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Image.asset('assets/logo/app_mark.png', height: 48),
                      const SizedBox(width: 16),
                      const Text('Start Tracking', style: TextStyle(fontSize: 24)),
                    ],
                  ),
                ),
              ),
              ),

              const SizedBox(height: 16),

              // ----- 2 x 2 grid -----
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.2,
                children: [
                  _MenuTile(
                    tutorialId: 'home_stats',
                    icon: Icons.bar_chart,
                    title: 'Stats',
                    subtitle: _statsSubtitle,
                    onTap: () => _open(const ActivityHistoryPage()),
                  ),
                  _MenuTile(
                    tutorialId: 'home_story',
                    icon: Icons.menu_book,
                    title: 'Story',
                    subtitle: _storySubtitle,
                    onTap: () => _open(const StoryListPage()),
                  ),
                  _MenuTile(
                    tutorialId: 'home_cards',
                    icon: Icons.style,
                    title: 'Cards',
                    subtitle: _cardsSubtitle,
                    onTap: () => _open(const CardsPage()),
                  ),
                  _MenuTile(
                    tutorialId: 'home_capture',
                    icon: Icons.camera_alt,
                    title: 'Capture',
                    subtitle: _gachaSubtitle,
                    onTap: () => _open(const GachaPage()),
                  ),
                ],
              ),

              const SizedBox(height: 16),

              // ----- Exit -----
              Center(
                child: TextButton.icon(
                  onPressed: _confirmExit,
                  icon: const Icon(Icons.exit_to_app),
                  label: const Text('Exit game'),
                ),
              ),
              Center(
                child: TextButton.icon(
                  onPressed: _startTutorial,
                  icon: const Icon(Icons.school_outlined, size: 18),
                  label: const Text('Tutorial'),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    textStyle: const TextStyle(fontSize: 13),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),

      // ----- Bottom bar -----
      bottomNavigationBar: NavigationBar(
        selectedIndex: 0,
        onDestinationSelected: (index) {
          switch (index) {
            case 1:
              _comingSoon('Party', Icons.groups);
            case 2:
              _comingSoon('Quests', Icons.explore);
            case 3:
              _open(const ProfilePage());
          }
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.groups), label: 'Party'),
          NavigationDestination(icon: Icon(Icons.explore), label: 'Quests'),
          NavigationDestination(icon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  final String tutorialId;
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _MenuTile({
    required this.tutorialId,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return TutorialTarget(
      id: tutorialId,
      child: Card(
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: colors.outlineVariant),
      ),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Icon(icon, size: 32, color: colors.primary),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: colors.onSurfaceVariant),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    ),
    );
  }
}
