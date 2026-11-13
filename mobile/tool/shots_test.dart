// Tasarım önizlemesi: gerçek ekranları gömülü yazı tipiyle PNG'ye çizer.
// Çalıştır: flutter test tool/shots_test.dart  → ../docs/tasarim/*.png
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tini/api.dart';
import 'package:tini/screens/list_screen.dart';
import 'package:tini/screens/login_screen.dart';
import 'package:tini/screens/rating_screen.dart';
import 'package:tini/screens/shell.dart';
import 'package:tini/theme/cosmic_colors.dart';
import 'package:tini/theme/tokens.dart';
import 'package:tini/theme/transitions.dart';
import 'package:tini/widgets/studio.dart';

class _Mem extends FlutterSecureStorage {
  final data = <String, String>{'session': 'T'};
  @override
  Future<String?> read({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async => data[key];
  @override
  Future<void> write({required String key, required String? value, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async {}
  @override
  Future<void> delete({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async {}
}

ThemeData _theme(Brightness b) {
  final c = b == Brightness.dark ? TiniCosmicColors.dark : TiniCosmicColors.light;
  return ThemeData(
    colorSchemeSeed: Colors.deepPurple,
    brightness: b,
    useMaterial3: true,
    fontFamily: 'Inter',
    scaffoldBackgroundColor: c.scaffold,
    pageTransitionsTheme: tiniPageTransitions,
    textTheme: tiniTextTheme(ThemeData(brightness: b).textTheme, c),
    extensions: [c],
  );
}

void main() {
  final key = GlobalKey();
  Future<void> shot(WidgetTester t, Widget app, String name, {String dir = 'tasarim'}) async {
    t.view.physicalSize = const Size(390 * 3, 844 * 3);
    t.view.devicePixelRatio = 3;
    debugDisableShadows = false;
    addTearDown(() {
      t.view.reset();
      debugDisableShadows = true;
    });
    await t.pumpWidget(RepaintBoundary(key: key, child: app));
    await t.pumpAndSettle();
    await t.runAsync(() async {
      final b = key.currentContext!.findRenderObject() as RenderRepaintBoundary;
      final img = await b.toImage(pixelRatio: 1);
      final bytes = (await img.toByteData(format: ui.ImageByteFormat.png))!;
      final f = File('../docs/$dir/$name.png')..createSync(recursive: true);
      f.writeAsBytesSync(bytes.buffer.asUint8List());
    });
    debugDisableShadows = true;
  }

  setUpAll(() async {
    final l = FontLoader('Inter')
      ..addFont(Future.value(ByteData.view(File('assets/fonts/Inter.ttf').readAsBytesSync().buffer)));
    await l.load();
    final mi = FontLoader('MaterialIcons')
      ..addFont(Future.value(ByteData.view(
          File('C:/dev/flutter/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf').readAsBytesSync().buffer)));
    await mi.load();
  });

  Api api() => Api(
      client: MockClient((r) async {
        switch (r.url.path) {
          case '/votes/history':
            return http.Response('{"total": 12, "items": []}', 200);
          case '/votes/queue':
            return http.Response.bytes(
                utf8.encode('{"remaining": 9, "stale": 0, "items": [{"track": 1, "title": "Gece Yarısı", "artists": ["Gama", "Ekin"]}, {"track": 2, "title": "Beta", "artists": ["B"]}]}'),
                200);
        }
        return http.Response('{}', 200);
      }),
      storage: _Mem());

  for (final b in [Brightness.dark, Brightness.light]) {
    testWidgets('rating ${b.name}', (t) async {
      final a = api();
      await a.restore();
      await shot(t, MaterialApp(debugShowCheckedModeBanner: false, theme: _theme(b), home: Scaffold(body: AmbientBackground(child: SafeArea(child: RatingScreen(api: a))))), 'oyla-${b.name}');
    });
  }
  // UI-3 inceleme görüntüleri: kabuk (sekme çubuğu + Oyla / Keşfet).
  for (final b in [Brightness.dark, Brightness.light]) {
    testWidgets('shell ${b.name}', (t) async {
      final a = api();
      await a.restore();
      t.view.physicalSize = const Size(390 * 3, 844 * 3);
      t.view.devicePixelRatio = 3;
      addTearDown(t.view.reset);
      await t.pumpWidget(RepaintBoundary(
          key: key,
          child: MaterialApp(
              debugShowCheckedModeBanner: false,
              theme: _theme(b),
              home: AppShell(api: a, onLogout: () {}))));
      await t.pumpAndSettle();
      Future<void> save(String name) async {
        await t.runAsync(() async {
          final r = key.currentContext!.findRenderObject() as RenderRepaintBoundary;
          final img = await r.toImage(pixelRatio: 1);
          final bytes = (await img.toByteData(format: ui.ImageByteFormat.png))!;
          File('../docs/design/review/$name.png')
            ..createSync(recursive: true)
            ..writeAsBytesSync(bytes.buffer.asUint8List());
        });
      }

      await t.tap(find.byKey(const ValueKey('tab-1')));
      await t.pumpAndSettle();
      await save('ui3-oyla-${b.name}');
      await t.tap(find.byKey(const ValueKey('tab-0')));
      await t.pumpAndSettle();
      await save('ui3-kesfet-${b.name}');
    });
  }
  // UI-4 inceleme görüntüleri: Keşif listesi + Gerekçe paneli.
  for (final b in [Brightness.dark, Brightness.light]) {
    testWidgets('list ${b.name}', (t) async {
      final items = [
        for (final (i, n) in ['Gama', 'Ekin', 'Beta', 'Delta', 'Omega', 'Sigma'].indexed)
          {
            'position': i + 1,
            'name': n,
            'title': i == 5 ? null : 'Şarkı ${i + 1}',
            if (i == 4)
              'release': {'id': 1, 'title': 'Yeni Albüm', 'type': 'album', 'released': '2026-10-30'},
            'reasons': [
              {'seed_id': 10, 'seed_name': 'Çapa A', 'share': 0.5, 'is_anchor': true},
              {'seed_id': 11, 'seed_name': 'Çapa B', 'share': 0.3, 'is_anchor': false},
              {'seed_id': 12, 'seed_name': 'Çapa C', 'share': 0.2, 'is_anchor': false},
            ],
          },
      ];
      final a = Api(
          client: MockClient((r) async => r.url.path == '/lists/generate'
              ? http.Response.bytes(utf8.encode(jsonEncode({'id': 7, 'items': items})), 201)
              : http.Response('{}', 200)),
          storage: _Mem());
      await a.restore();
      t.view.physicalSize = const Size(390 * 3, 844 * 3);
      t.view.devicePixelRatio = 3;
      addTearDown(t.view.reset);
      await t.pumpWidget(RepaintBoundary(
          key: key,
          child: MaterialApp(
              debugShowCheckedModeBanner: false,
              theme: _theme(b),
              home: ListScreen(api: a))));
      await t.tap(find.text('Liste üret'));
      await t.pumpAndSettle();
      Future<void> save(String name) async {
        await t.runAsync(() async {
          final r = key.currentContext!.findRenderObject() as RenderRepaintBoundary;
          final img = await r.toImage(pixelRatio: 1);
          final bytes = (await img.toByteData(format: ui.ImageByteFormat.png))!;
          File('../docs/design/review/$name.png')
            ..createSync(recursive: true)
            ..writeAsBytesSync(bytes.buffer.asUint8List());
        });
      }

      await save('ui4-liste-${b.name}');
      await t.tap(find.text('Şarkı 1'));
      await t.pumpAndSettle();
      await save('ui4-gerekce-${b.name}');
    });
  }
  testWidgets('login dark', (t) async {
    final a = api();
    await shot(t, MaterialApp(debugShowCheckedModeBanner: false, theme: _theme(Brightness.dark), home: LoginScreen(api: a, onDone: () {})), 'giris-dark');
  });
}
