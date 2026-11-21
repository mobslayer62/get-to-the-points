import 'dart:async';

import 'package:flutter/material.dart';

import 'api_service.dart';

/// Runs the tutorial. The steps (text, what to highlight, what ends each
/// step) come from the server: backend/Database/tutorial_data.py.
///
/// Screens take part in two ways:
///  * wrap a widget in `TutorialTarget(id: ...)` so it can be highlighted
///  * call `TutorialController.instance.report('event')` when something
///    happens (a screen opened, a card equipped, ...)
class TutorialController extends ChangeNotifier {
  TutorialController._();
  static final TutorialController instance = TutorialController._();

  List<Map<String, dynamic>> _steps = [];
  int _index = 0;

  bool active = false;

  /// True while the player is on a real run during the run step.
  bool suspended = false;

  /// True while the run bonus is being claimed.
  bool busy = false;

  String starterCardName = 'NTHU Main Gate';
  int bonusPoints = 100;

  /// Result of the run step's bonus: {awarded, total_points, skipped}.
  /// [runBonusToken] changes each time, so the run screen can react once.
  Map<String, dynamic>? runBonus;
  int runBonusToken = 0;

  DateTime stepShownAt = DateTime.now();

  final Map<String, GlobalKey> _keys = {};

  GlobalKey keyFor(String id) =>
      _keys.putIfAbsent(id, () => GlobalKey(debugLabel: 'tutorial-$id'));

  Map<String, dynamic>? get step =>
      active && _index < _steps.length ? _steps[_index] : null;

  int get stepNumber => _index + 1;
  int get stepCount => _steps.length;
  bool get isLastStep => _index == _steps.length - 1;

  /// True if the current step ends when [event] is reported.
  bool isWaitingFor(String event) => step?['advance_on'] == event;

  Future<bool> start() async {
    if (active) return true;
    try {
      final data = await ApiService.getTutorial();
      _steps = (data['steps'] as List<dynamic>).cast<Map<String, dynamic>>();
      starterCardName = data['starter_card_name'] as String? ?? starterCardName;
      bonusPoints = data['bonus_points'] as int? ?? bonusPoints;
    } on ApiException {
      return false;
    }
    if (_steps.isEmpty) return false;
    _index = 0;
    active = true;
    suspended = false;
    busy = false;
    runBonus = null;
    stepShownAt = DateTime.now();
    notifyListeners();
    return true;
  }

  void next() {
    if (!active) return;
    _index++;
    stepShownAt = DateTime.now();
    if (_index >= _steps.length) {
      finish();
    } else {
      notifyListeners();
    }
  }

  void finish() {
    active = false;
    suspended = false;
    busy = false;
    notifyListeners();
  }

  /// Screens call this when something happens. Safe to call from
  /// initState or build: it runs after the current frame's work.
  void report(String event) {
    scheduleMicrotask(() => _handle(event));
  }

  void _handle(String event) {
    final s = step;
    if (s == null) return;

    if (s['mode'] == 'run') {
      switch (event) {
        case 'run_started':
          suspended = true;
          notifyListeners();
        case 'run_failed':
          suspended = false;
          notifyListeners();
        case 'run_saved':
          _claimRunBonus(skipped: false);
      }
      return;
    }

    if (s['advance_on'] == event) next();
  }

  /// "Skip run" on the run step.
  Future<void> skipRun() => _claimRunBonus(skipped: true);

  Future<void> _claimRunBonus({required bool skipped}) async {
    if (busy) return;
    busy = true;
    notifyListeners();

    Map<String, dynamic>? result;
    try {
      result = await ApiService.claimTutorialRunBonus();
    } on ApiException {
      result = null;
    }
    runBonus = {
      'awarded': result?['awarded'] ?? 0,
      'total_points': result?['total_points'],
      'skipped': skipped,
      'failed': result == null,
    };
    runBonusToken++;
    busy = false;
    suspended = false;
    next();
  }
}

/// Marks a widget the tutorial can highlight.
class TutorialTarget extends StatelessWidget {
  final String id;
  final Widget child;

  const TutorialTarget({super.key, required this.id, required this.child});

  @override
  Widget build(BuildContext context) {
    return KeyedSubtree(
      key: TutorialController.instance.keyFor(id),
      child: child,
    );
  }
}

/// Dark layer with a spotlight and the text box. Placed above every screen
/// (MaterialApp.builder). In "tap" and "run" steps only the spotlighted
/// area can be touched.
class TutorialOverlay extends StatefulWidget {
  const TutorialOverlay({super.key});

  @override
  State<TutorialOverlay> createState() => _TutorialOverlayState();
}

class _TutorialOverlayState extends State<TutorialOverlay> {
  final _tutorial = TutorialController.instance;
  Timer? _tracker;

  /// After this long without finding the target, show Next instead.
  static const _missingTargetGrace = Duration(milliseconds: 1500);

  @override
  void initState() {
    super.initState();
    _tutorial.addListener(_onChange);
  }

  @override
  void dispose() {
    _tutorial.removeListener(_onChange);
    _tracker?.cancel();
    super.dispose();
  }

  void _onChange() {
    if (!mounted) return;
    setState(() {});
    // While active, keep following the target (screens animate and scroll).
    if (_tutorial.active && _tracker == null) {
      _tracker = Timer.periodic(const Duration(milliseconds: 200), (_) {
        if (!mounted || !_tutorial.active) {
          _tracker?.cancel();
          _tracker = null;
          return;
        }
        setState(() {});
      });
    }
  }

  Rect? _targetRect(String? target, MediaQueryData media) {
    if (target == null) return null;
    if (target == 'back') {
      // The AppBar's back arrow, top-left under the status bar
      return Rect.fromLTWH(0, media.padding.top, 56, kToolbarHeight)
          .deflate(4);
    }
    final ctx = _tutorial.keyFor(target).currentContext;
    final box = ctx?.findRenderObject();
    if (box is! RenderBox || !box.attached || !box.hasSize) return null;
    final rect = box.localToGlobal(Offset.zero) & box.size;
    final screen = Offset.zero & media.size;
    if (!rect.overlaps(screen)) return null;
    return rect.inflate(6).intersect(screen);
  }

  @override
  Widget build(BuildContext context) {
    final step = _tutorial.step;
    if (step == null || _tutorial.suspended) return const SizedBox.shrink();

    final media = MediaQuery.of(context);
    final size = media.size;
    final mode = step['mode'] as String? ?? 'info';
    final target = step['target'] as String?;
    final hole = _targetRect(target, media);
    final canTouchHole = hole != null && (mode == 'tap' || mode == 'run');
    final targetMissing = target != null &&
        hole == null &&
        DateTime.now().difference(_tutorial.stepShownAt) > _missingTargetGrace;

    const dim = Color(0xB3000000);
    Widget blocker({Color color = dim}) => GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () {},
          child: ColoredBox(color: color),
        );

    final layers = <Widget>[];
    if (hole == null) {
      layers.add(Positioned.fill(child: blocker()));
    } else {
      layers.addAll([
        Positioned(left: 0, top: 0, right: 0, height: hole.top, child: blocker()),
        Positioned(left: 0, top: hole.bottom, right: 0, bottom: 0, child: blocker()),
        Positioned(left: 0, top: hole.top, width: hole.left, height: hole.height, child: blocker()),
        Positioned(left: hole.right, top: hole.top, right: 0, height: hole.height, child: blocker()),
        if (!canTouchHole)
          Positioned.fromRect(rect: hole, child: blocker(color: Colors.transparent)),
        Positioned.fromRect(
          rect: hole,
          child: IgnorePointer(
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.amber, width: 3),
              ),
            ),
          ),
        ),
      ]);
    }

    // Text box goes on the side away from the spotlight
    final box = _TextBox(
      step: step,
      number: _tutorial.stepNumber,
      count: _tutorial.stepCount,
      isLast: _tutorial.isLastStep,
      showNext: mode == 'info' || targetMissing,
      showSkipRun: mode == 'run',
      busy: _tutorial.busy,
      bonusPoints: _tutorial.bonusPoints,
      onNext: _tutorial.next,
      onSkipTutorial: _tutorial.finish,
      onSkipRun: _tutorial.skipRun,
    );
    if (hole == null) {
      layers.add(Positioned(left: 16, right: 16, top: size.height * 0.3, child: box));
    } else if (hole.center.dy > size.height / 2) {
      layers.add(Positioned(
          left: 16, right: 16, top: media.padding.top + kToolbarHeight + 8, child: box));
    } else {
      layers.add(Positioned(
          left: 16, right: 16, bottom: media.padding.bottom + 24, child: box));
    }

    return Material(
      type: MaterialType.transparency,
      child: Stack(children: layers),
    );
  }
}

class _TextBox extends StatelessWidget {
  final Map<String, dynamic> step;
  final int number;
  final int count;
  final bool isLast;
  final bool showNext;
  final bool showSkipRun;
  final bool busy;
  final int bonusPoints;
  final VoidCallback onNext;
  final VoidCallback onSkipTutorial;
  final VoidCallback onSkipRun;

  const _TextBox({
    required this.step,
    required this.number,
    required this.count,
    required this.isLast,
    required this.showNext,
    required this.showSkipRun,
    required this.busy,
    required this.bonusPoints,
    required this.onNext,
    required this.onSkipTutorial,
    required this.onSkipRun,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final mode = step['mode'];

    return Material(
      elevation: 8,
      color: colors.surface,
      borderRadius: BorderRadius.circular(16),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 8, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Step counter + Skip tutorial (top right)
            Row(
              children: [
                Text('Tutorial $number / $count',
                    style: TextStyle(fontSize: 12, color: colors.onSurfaceVariant)),
                const Spacer(),
                if (!isLast)
                  TextButton(
                    onPressed: busy ? null : onSkipTutorial,
                    child: const Text('Skip tutorial'),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Text(
                step['text'] as String? ?? '',
                style: const TextStyle(fontSize: 16, height: 1.4),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                if (mode == 'tap' && !showNext)
                  Expanded(
                    child: Text(
                      'Tap the highlighted button.',
                      style: TextStyle(
                        fontStyle: FontStyle.italic,
                        color: colors.primary,
                      ),
                    ),
                  )
                else
                  const Spacer(),
                if (busy)
                  const Padding(
                    padding: EdgeInsets.all(8),
                    child: SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                else if (showSkipRun)
                  OutlinedButton(
                    onPressed: onSkipRun,
                    child: Text('Skip run (+$bonusPoints)'),
                  ),
                if (showNext) ...[
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: onNext,
                    child: Text(isLast ? 'Finish' : 'Next'),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
