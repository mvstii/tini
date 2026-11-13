import 'package:flutter/material.dart';

import 'api.dart';
import 'profile_photo.dart';
import 'screens/intro_screen.dart';
import 'screens/login_screen.dart';
import 'screens/shell.dart';
import 'theme/cosmic_colors.dart';
import 'theme/tini_tokens.dart';
import 'theme/tokens.dart';
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
      api.loadIntroSeen(),
      Future<void>.delayed(const Duration(milliseconds: 900)),
    ]);
    return TiniApp(
      api: api,
      themeMode: results[0] as ThemeMode,
      introSeen: results[1] as bool,
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<TiniApp>(
      future: _app,
      builder: (context, snap) => AnimatedSwitcher(
        duration: const Duration(milliseconds: 240),
        child: snap.data ??
            MaterialApp(
              key: const ValueKey('splash'),
              debugShowCheckedModeBanner: false,
              theme: ThemeData(
                colorSchemeSeed: Colors.deepPurple,
                useMaterial3: true,
                fontFamily: 'Inter',
                extensions: [TiniCosmicColors.light, TiniTokens.light],
              ),
              darkTheme: ThemeData(
                colorSchemeSeed: Colors.deepPurple,
                brightness: Brightness.dark,
                useMaterial3: true,
                fontFamily: 'Inter',
                extensions: [TiniCosmicColors.dark, TiniTokens.dark],
              ),
              home: const Scaffold(body: AmbientBackground(child: SplashScreen())),
            ),
      ),
    );
  }
}

class TiniApp extends StatefulWidget {
  const TiniApp({
    super.key,
    required this.api,
    this.themeMode = ThemeMode.system,
    this.introSeen = true,
  });
  final Api api;
  final ThemeMode themeMode;

  /// İlk açılış eğitimi görüldü mü (varsayılan true: testler ve eski çağrılar etkilenmez).
  final bool introSeen;

  @override
  State<TiniApp> createState() => _TiniAppState();
}

class _TiniAppState extends State<TiniApp> {
  late bool _loggedIn = widget.api.loggedIn;
  late ThemeMode _themeMode = widget.themeMode;
  late bool _introSeen = widget.introSeen;

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
        fontFamily: 'Inter',
        scaffoldBackgroundColor: c.scaffold,
        pageTransitionsTheme: tiniPageTransitions,
        textTheme: tiniTextTheme(ThemeData(brightness: b).textTheme, c),
        cardTheme: CardThemeData(
          color: c.card,
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(TiniShape.card)),
        ),
        dividerTheme: DividerThemeData(color: c.highlight.withValues(alpha: 0.5), space: 1),
        extensions: [c, b == Brightness.dark ? TiniTokens.dark : TiniTokens.light],
      );
    }

    return MaterialApp(
      title: 'Tını',
      theme: theme(Brightness.light),
      darkTheme: theme(Brightness.dark),
      themeMode: _themeMode,
      home: _loggedIn && !_introSeen
          ? IntroScreen(
              onDone: () {
                widget.api.saveIntroSeen();
                setState(() => _introSeen = true);
              },
            )
          : _loggedIn
          ? AppShell(
              api: widget.api,
              onLogout: () {
                // Kişisel veri: çıkışta, 401'de ve hesap silinirken yerel fotoğraf da gider.
                ProfilePhotoStore.clear();
                setState(() => _loggedIn = false);
              },
              themeMode: _themeMode,
              onThemeChanged: _setTheme,
            )
          : LoginScreen(api: widget.api, onDone: () => setState(() => _loggedIn = true)),
    );
  }
}
