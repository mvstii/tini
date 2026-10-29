import 'package:flutter/material.dart';

import 'api.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final api = Api();
  await api.restore();
  runApp(TiniApp(api: api));
}

class TiniApp extends StatefulWidget {
  const TiniApp({super.key, required this.api});
  final Api api;

  @override
  State<TiniApp> createState() => _TiniAppState();
}

class _TiniAppState extends State<TiniApp> {
  late bool _loggedIn = widget.api.loggedIn;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Tını',
      theme: ThemeData(colorSchemeSeed: Colors.deepPurple, useMaterial3: true),
      home: _loggedIn
          ? HomeScreen(api: widget.api, onLogout: () => setState(() => _loggedIn = false))
          : LoginScreen(api: widget.api, onDone: () => setState(() => _loggedIn = true)),
    );
  }
}
