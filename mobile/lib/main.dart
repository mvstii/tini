import 'package:flutter/material.dart';

import 'api.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';

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
    ThemeData theme(Brightness b) => ThemeData(
        colorSchemeSeed: Colors.deepPurple, brightness: b, useMaterial3: true);
    return MaterialApp(
      title: 'Tını',
      theme: theme(Brightness.light),
      darkTheme: theme(Brightness.dark),
      themeMode: _themeMode,
      home: _loggedIn
          ? HomeScreen(
              api: widget.api,
              onLogout: () => setState(() => _loggedIn = false),
              themeMode: _themeMode,
              onThemeChanged: _setTheme,
            )
          : LoginScreen(api: widget.api, onDone: () => setState(() => _loggedIn = true)),
    );
  }
}
