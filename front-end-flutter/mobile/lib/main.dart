
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:geolocator_android/geolocator_android.dart';
import 'package:pedometer/pedometer.dart';
import 'package:permission_handler/permission_handler.dart';

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
      home: const LocationPage(),
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
  Future<void> stopTracking() async {
    // Cancel watchdog
    gpsWatchdogTimer?.cancel();
    gpsWatchdogTimer = null;

    await positionStream?.cancel();
    await stepStream?.cancel();

    positionStream = null;
    stepStream = null;

    displayTimer?.cancel();
    displayTimer = null;

    int duration = DateTime.now()
        .difference(runStartTime!)
        .inSeconds;

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

    final duration = DateTime.now().difference(runStartTime!);

    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;

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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Running Game'),
        centerTitle: true,
      ),

      body: Center(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(24),

            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
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

                // Start / Stop button
                ElevatedButton.icon(
                  onPressed: isTracking
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
    );
  }
}
