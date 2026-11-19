
import 'dart:async';
import 'api_service.dart';
import 'login_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:geolocator_android/geolocator_android.dart';
import 'package:pedometer/pedometer.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:uuid/uuid.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Running Game',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.green),
        useMaterial3: true,
      ),
      home: const LoginPage(),
    );
  }
}

class LocationPage extends StatefulWidget {
  const LocationPage({super.key});

  @override
  State<LocationPage> createState() => _LocationPageState();
}

class _LocationPageState extends State<LocationPage> {
  Timer? displayTimer;
  Timer? gpsWatchdogTimer;

  int elapsedSeconds = 0;

  // GPS variables
  Position? previousPosition;
  StreamSubscription<Position>? positionStream;

  double totalDistance = 0;

  // GPS debugging variables
  int gpsUpdateCount = 0;
  String gpsDebugMessage = 'GPS not started';

  // Step counter variables
  StreamSubscription<StepCount>? stepStream;

  int totalSteps = 0;
  int stepBaseline = 0;

  bool stepCounterAvailable = false;
  String stepMessage = 'Step counter not started';

  // Running session variables
  DateTime? runStartTime;

  bool isTracking = false;

  String statusMessage = 'Ready to run';

  // ----- Backend submission -----
  // Player's point balance from the server
  int? totalPoints;

  // A finished run that has not been accepted by the server yet.
  // The session id is kept so retrying never awards points twice.
  String? pendingSessionId;
  double pendingDistance = 0;
  int pendingSteps = 0;
  int pendingDuration = 0;

  bool isSubmitting = false;
  String? submitError;
  Map<String, dynamic>? lastResult;

  @override
  void initState() {
    super.initState();
    loadStats();
  }

  Future<void> loadStats() async {
    try {
      final stats = await ApiService.getStats();
      if (!mounted) return;
      setState(() => totalPoints = stats['total_points'] as int?);
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 401) {
        goToLogin();
      } else {
        setState(() => submitError = e.message);
      }
    }
  }

  Future<void> submitRun() async {
    final sessionId = pendingSessionId;
    if (sessionId == null) return;

    setState(() {
      isSubmitting = true;
      submitError = null;
      statusMessage = 'Saving your run...';
    });

    try {
      final result = await ApiService.finishSession(
        sessionId: sessionId,
        distanceMeters: pendingDistance,
        steps: pendingSteps,
        durationSeconds: pendingDuration,
      );
      if (!mounted) return;
      setState(() {
        lastResult = result;
        totalPoints = result['total_points'] as int?;
        pendingSessionId = null;
        statusMessage = 'Run saved!';
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        if (e.statusCode == 400) {
          // The server rejected this run; retrying won't help.
          pendingSessionId = null;
          submitError = 'Run not accepted: ${e.message}';
        } else {
          // Network/server problem: keep the run so it can be retried.
          submitError = e.message;
        }
        statusMessage = 'Run not saved';
      });
    } finally {
      if (mounted) setState(() => isSubmitting = false);
    }
  }

  void discardPendingRun() {
    setState(() {
      pendingSessionId = null;
      submitError = null;
      statusMessage = 'Ready to run';
    });
  }

  void goToLogin() => goToLoginScreen(context);

  // Start step counter
  Future<bool> startStepCounter() async {
    try {
      if (defaultTargetPlatform == TargetPlatform.android) {
        final permission =
            await Permission.activityRecognition.request();

        if (!permission.isGranted) {
          stepMessage = 'Step permission denied';
          return false;
        }
      }

      final Stream<StepCount> stream = Pedometer.stepCountStream;

      final completer = Completer<int>();

      await stepStream?.cancel();

      stepStream = stream.listen(
        (StepCount event) {
          if (!completer.isCompleted) {
            stepBaseline = event.steps;
            totalSteps = 0;

            completer.complete(event.steps);
          } else if (isTracking) {
            final difference = event.steps - stepBaseline;

            totalSteps = difference > 0 ? difference : 0;
          }

          if (mounted) {
            setState(() {
              stepCounterAvailable = true;
            });
          }
        },
        onError: (error) {
          stepMessage = 'Step sensor error: $error';

          if (!completer.isCompleted) {
            completer.completeError(error);
          }

          if (mounted) {
            setState(() {
              stepCounterAvailable = false;
            });
          }
        },
      );

      await completer.future.timeout(
        const Duration(seconds: 10),
      );

      stepMessage = 'Step counter active';

      return true;
    } catch (e) {
      await stepStream?.cancel();
      stepStream = null;

      stepMessage = 'Step counter unavailable: $e';

      return false;
    }
  }

  // Start GPS tracking
  Future<void> startTracking() async {
    gpsWatchdogTimer?.cancel();
    gpsWatchdogTimer = null;

    setState(() {
      lastResult = null;
      submitError = null;
      statusMessage = 'Preparing tracking...';
      gpsUpdateCount = 0;
      totalDistance = 0;
      gpsDebugMessage = 'Waiting for GPS updates...';
    });

    try {
      // Check location services
      bool serviceEnabled =
          await Geolocator.isLocationServiceEnabled();

      if (!serviceEnabled) {
        throw Exception('Please enable GPS.');
      }

      // Check location permission
      LocationPermission permission =
          await Geolocator.checkPermission();

      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        throw Exception('Location permission denied.');
      }

      // Start step counter
      bool stepAvailable = false;

      if (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS) {
        stepAvailable = await startStepCounter();
      } else {
        stepMessage = 'Step counter requires a mobile device';
      }

      // Configure GPS settings
      final LocationSettings locationSettings;

      if (defaultTargetPlatform == TargetPlatform.android) {
        locationSettings = AndroidSettings(
          accuracy: LocationAccuracy.best,
          distanceFilter: 0,
          intervalDuration: const Duration(seconds: 3),

          // Use Android's traditional LocationManager
          forceLocationManager: true,

          // Report an error if no location arrives
          // within 30 seconds.
          timeLimit: const Duration(seconds: 30),
        );
      } else {
        locationSettings = const LocationSettings(
          accuracy: LocationAccuracy.best,
          distanceFilter: 0,
          timeLimit: Duration(seconds: 30),
        );
      }

      // Get initial GPS position
      if (mounted) {
        setState(() {
          statusMessage = 'Getting initial GPS position...';
          gpsDebugMessage = 'Acquiring GPS position...';
        });
      }

      Position initialPosition =
          await Geolocator.getCurrentPosition(
        locationSettings: locationSettings,
      );

      previousPosition = initialPosition;

      // Reset session values
      totalDistance = 0;
      totalSteps = 0;

      runStartTime = DateTime.now();

      setState(() {
        isTracking = true;
        elapsedSeconds = 0;

        displayTimer?.cancel();

        displayTimer = Timer.periodic(
          const Duration(seconds: 1),
          (timer) {
            if (mounted && isTracking) {
              setState(() {
                elapsedSeconds++;
              });
            }
          },
        );

        statusMessage = stepAvailable
            ? 'Tracking your run...'
            : 'GPS tracking active. Step counter unavailable.';

        gpsDebugMessage =
            'Initial GPS position acquired\n'
            'Accuracy: ${initialPosition.accuracy.toStringAsFixed(1)} m\n'
            'Preparing GPS listener...';
      });

      // Prepare GPS watchdog
      int waitSeconds = 0;

      setState(() {
        gpsDebugMessage =
            'GPS LISTENER ATTACHING\n'
            'Waiting for first location update...';
      });

      // Independent timer to monitor the GPS stream
      gpsWatchdogTimer = Timer.periodic(
        const Duration(seconds: 1),
        (timer) {
          if (!mounted ||
              !isTracking ||
              gpsUpdateCount > 0) {
            timer.cancel();
            gpsWatchdogTimer = null;
            return;
          }

          waitSeconds++;

          setState(() {
            gpsDebugMessage =
                'GPS LISTENER ATTACHED\n'
                'No location update received\n'
                'Waiting: $waitSeconds seconds';
          });
        },
      );

      // Listen to continuous GPS updates
      positionStream = Geolocator.getPositionStream(
        locationSettings: locationSettings,
      ).listen(
        (Position currentPosition) {
          // A location update has arrived
          gpsUpdateCount++;

          // Stop watchdog after first update
          gpsWatchdogTimer?.cancel();
          gpsWatchdogTimer = null;

          print(
            'GPS UPDATE: ${currentPosition.latitude}, '
            '${currentPosition.longitude}',
          );

          print(
            'GPS ACCURACY: ${currentPosition.accuracy} meters',
          );

          // Check GPS accuracy
          if (currentPosition.accuracy > 60) {
            if (mounted) {
              setState(() {
                gpsDebugMessage =
                    'GPS SIGNAL WEAK\n'
                    'Accuracy: ${currentPosition.accuracy.toStringAsFixed(1)} m\n'
                    'Updates: $gpsUpdateCount\n'
                    'Reading rejected';
              });
            }

            return;
          }

          // Calculate distance
          if (previousPosition != null) {
            double distance = Geolocator.distanceBetween(
              previousPosition!.latitude,
              previousPosition!.longitude,
              currentPosition.latitude,
              currentPosition.longitude,
            );

            totalDistance += distance;
          }

          previousPosition = currentPosition;

          // Update phone display
          if (mounted) {
            setState(() {
              gpsDebugMessage =
                  'GPS SIGNAL OK\n'
                  'Accuracy: ${currentPosition.accuracy.toStringAsFixed(1)} m\n'
                  'Updates: $gpsUpdateCount\n'
                  'Distance: ${totalDistance.toStringAsFixed(1)} m';
            });
          }
        },
        onError: (error) {
          gpsWatchdogTimer?.cancel();
          gpsWatchdogTimer = null;

          if (mounted) {
            setState(() {
              gpsDebugMessage =
                  'GPS STREAM ERROR:\n$error';

              statusMessage = 'GPS tracking error: $error';
            });
          }
        },
        onDone: () {
          gpsWatchdogTimer?.cancel();
          gpsWatchdogTimer = null;

          if (mounted &&
              isTracking &&
              !gpsDebugMessage.startsWith('GPS STREAM ERROR')) {
            setState(() {
              gpsDebugMessage =
                  'GPS STREAM CLOSED\n'
                  'Updates received: $gpsUpdateCount';
            });
          }
        },
      );
    } catch (e) {
      gpsWatchdogTimer?.cancel();
      gpsWatchdogTimer = null;

      await positionStream?.cancel();
      await stepStream?.cancel();

      positionStream = null;
      stepStream = null;

      if (mounted) {
        setState(() {
          isTracking = false;
          statusMessage = 'Error: $e';
          gpsDebugMessage = 'GPS FAILED:\n$e';
        });
      }
    }
  }

  // Stop tracking
  Future<void> stopTracking({bool submit = true}) async {
    // Cancel watchdog
    gpsWatchdogTimer?.cancel();
    gpsWatchdogTimer = null;

    await positionStream?.cancel();
    await stepStream?.cancel();

    positionStream = null;
    stepStream = null;

    displayTimer?.cancel();
    displayTimer = null;

    int duration = runStartTime == null
        ? 0
        : DateTime.now().difference(runStartTime!).inSeconds;

    setState(() {
      isTracking = false;
      statusMessage = 'Run completed!';

      gpsDebugMessage =
          'GPS tracking stopped\n'
          'Updates received: $gpsUpdateCount';
    });

    print('Distance: $totalDistance meters');
    print('Steps: $totalSteps');
    print('Duration: $duration seconds');

    if (!submit) return;

    // Keep the run (and a fixed session id) until the server accepts it.
    pendingSessionId = const Uuid().v4();
    pendingDistance = totalDistance;
    pendingSteps = totalSteps;
    pendingDuration = duration;

    await submitRun();
  }

  // Distance in kilometers
  String get distanceInKm {
    return (totalDistance / 1000).toStringAsFixed(2);
  }

  // Running timer
  String get elapsedTime {
    if (runStartTime == null) {
      return '00:00';
    }

    final minutes = elapsedSeconds ~/ 60;
    final seconds = elapsedSeconds % 60;

    return '${minutes.toString().padLeft(2, '0')}:'
        '${seconds.toString().padLeft(2, '0')}';
  }

  @override
  void dispose() {
    displayTimer?.cancel();
    gpsWatchdogTimer?.cancel();
    positionStream?.cancel();
    stepStream?.cancel();

    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Leaving this screen mid-run (or with an unsaved run) would lose it.
    final canLeave = !isTracking && !isSubmitting && pendingSessionId == null;

    return PopScope(
      canPop: canLeave,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Stop the run, or save or discard it, before leaving.'),
            ),
          );
        }
      },
      child: Scaffold(
      appBar: AppBar(
        title: const Text('Run'),
        centerTitle: true,
      ),

      body: Center(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(24),

            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Point balance
                Chip(
                  avatar: const Icon(Icons.stars, color: Colors.amber),
                  label: Text(
                    totalPoints == null ? 'Points: ...' : 'Points: $totalPoints',
                    style: const TextStyle(fontSize: 18),
                  ),
                ),

                const SizedBox(height: 10),

                const Icon(
                  Icons.directions_run,
                  size: 70,
                  color: Colors.green,
                ),

                const SizedBox(height: 25),

                // Distance
                const Text(
                  'Distance Travelled',
                  style: TextStyle(fontSize: 18),
                ),

                Text(
                  '$distanceInKm km',
                  style: const TextStyle(
                    fontSize: 40,
                    fontWeight: FontWeight.bold,
                  ),
                ),

                const SizedBox(height: 15),

                // GPS Debug Panel
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Column(
                    children: [
                      const Text(
                        'GPS DEBUG',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),

                      const SizedBox(height: 5),

                      Text(
                        gpsDebugMessage,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 13),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 20),

                // Step counter
                const Icon(
                  Icons.directions_walk,
                  size: 35,
                  color: Colors.green,
                ),

                Text(
                  '$totalSteps steps',
                  style: const TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                  ),
                ),

                Text(
                  stepMessage,
                  style: const TextStyle(fontSize: 12),
                ),

                const SizedBox(height: 20),

                // Timer
                Text(
                  'Time: $elapsedTime',
                  style: const TextStyle(fontSize: 20),
                ),

                const SizedBox(height: 20),

                Text(
                  statusMessage,
                  textAlign: TextAlign.center,
                ),

                const SizedBox(height: 25),

                // Reward from the server
                if (lastResult != null)
                  Card(
                    color: Colors.green.shade50,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        children: [
                          Text(
                            '+${lastResult!['points_earned']} points',
                            style: const TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.bold,
                              color: Colors.green,
                            ),
                          ),
                          Text('for ${lastResult!['session_distance']} m'),
                          if (lastResult!['already_processed'] == true)
                            const Text('(this run was already saved)'),
                        ],
                      ),
                    ),
                  ),

                // Submission error with retry
                if (submitError != null)
                  Card(
                    color: Colors.red.shade50,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        children: [
                          Text(
                            submitError!,
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Colors.red.shade900),
                          ),
                          if (pendingSessionId != null)
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                TextButton(
                                  onPressed: isSubmitting ? null : submitRun,
                                  child: const Text('Retry'),
                                ),
                                TextButton(
                                  onPressed:
                                      isSubmitting ? null : discardPendingRun,
                                  child: const Text('Discard run'),
                                ),
                              ],
                            ),
                        ],
                      ),
                    ),
                  ),

                if (isSubmitting)
                  const Padding(
                    padding: EdgeInsets.all(8),
                    child: CircularProgressIndicator(),
                  ),

                const SizedBox(height: 10),

                // Start / Stop button
                // (disabled while a finished run is waiting to be saved)
                ElevatedButton.icon(
                  onPressed: isSubmitting || (!isTracking && pendingSessionId != null)
                      ? null
                      : isTracking
                          ? stopTracking
                          : startTracking,

                  icon: Icon(
                    isTracking
                        ? Icons.stop
                        : Icons.play_arrow,
                  ),

                  label: Text(
                    isTracking
                        ? 'Stop Run'
                        : 'Start Run',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
    );
  }
}
