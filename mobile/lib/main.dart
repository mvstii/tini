import 'package:flutter/material.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/shell.dart';
import 'theme/cosmic_colors.dart';
import 'theme/transitions.dart';
import 'widgets/brand.dart';
import 'widgets/studio.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TiniBoot());
}

/// Açılış: oturum ve tema okunurken marka ekranı gösterilir (en az kısa bir an), sonra
/// uygulamaya yumuşakça geçilir.
class TiniBoot extends StatefulWidget {
  const TiniBoot({super.key});

  @override
  State<TiniBoot> createState() => _TiniBootState();
}

class _TiniBootState extends State<TiniBoot> {
  late final Future<TiniApp> _app = _load();

  Future<TiniApp> _load() async {
    final api = Api();
    final results = await Future.wait([
      () async {
        await api.restore();
        return await api.loadTheme();
      }(),
      Future<void>.delayed(const Duration(milliseconds: 900)),
    ]);
    return TiniApp(api: api, themeMode: results[0] as ThemeMode);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<TiniApp>(
      future: _app,
      builder: (context, snap) => AnimatedSwitcher(
        duration: const Duration(milliseconds: 400),
        child: snap.data ??
            MaterialApp(
              key: const ValueKey('splash'),
              debugShowCheckedModeBanner: false,
              theme: ThemeData(
                colorSchemeSeed: Colors.deepPurple,
                useMaterial3: true,
                fontFamily: 'PlusJakartaSans',
                extensions: [TiniCosmicColors.light],
              ),
              darkTheme: ThemeData(
                colorSchemeSeed: Colors.deepPurple,
                brightness: Brightness.dark,
                useMaterial3: true,
                fontFamily: 'PlusJakartaSans',
                extensions: [TiniCosmicColors.dark],
              ),
              home: const Scaffold(body: AmbientBackground(child: SplashScreen())),
            ),
      ),
    );
  }
}

class TiniApp extends StatefulWidget {
  const TiniApp({super.key, required this.api, this.themeMode = ThemeMode.system});
  final Api api;
  final ThemeMode themeMode;

  @override
  State<TiniApp> createState() => _TiniAppState();
}

class _TiniAppState extends State<TiniApp> {
  late bool _loggedIn = widget.api.loggedIn;
  late ThemeMode _themeMode = widget.themeMode;

  void _setTheme(ThemeMode mode) {
    setState(() => _themeMode = mode);
    widget.api.saveTheme(mode);
  }

  @override
  Widget build(BuildContext context) {
    ThemeData theme(Brightness b) {
      final c = b == Brightness.dark ? TiniCosmicColors.dark : TiniCosmicColors.light;
      return ThemeData(
        colorSchemeSeed: Colors.deepPurple,
        brightness: b,
        useMaterial3: true,
        fontFamily: 'PlusJakartaSans',
        scaffoldBackgroundColor: c.scaffold,
        pageTransitionsTheme: tiniPageTransitions,
        extensions: [c],
      );
    }

    return MaterialApp(
      title: 'Tını',
      theme: theme(Brightness.light),
      darkTheme: theme(Brightness.dark),
      themeMode: _themeMode,
      home: _loggedIn
          ? AppShell(
              api: widget.api,
              onLogout: () => setState(() => _loggedIn = false),
              themeMode: _themeMode,
              onThemeChanged: _setTheme,
            )
          : LoginScreen(api: widget.api, onDone: () => setState(() => _loggedIn = true)),
    );
  }
}
