import 'package:flutter/material.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/shell.dart';
import 'theme/cosmic_colors.dart';
import 'theme/transitions.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final api = Api();
  await api.restore();
  runApp(TiniApp(api: api, themeMode: await api.loadTheme()));
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
