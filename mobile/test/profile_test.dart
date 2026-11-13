import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tini/api.dart';
import 'package:tini/app_state.dart';
import 'package:tini/screens/profile_screen.dart';
import 'package:tini/theme/cosmic_colors.dart';
import 'package:tini/theme/tini_tokens.dart';

class _Mem extends FlutterSecureStorage {
  @override
  Future<String?> read({
    required String key,
    iOptions,
    aOptions,
    lOptions,
    webOptions,
    mOptions,
    wOptions,
  }) async => 'T';
}

Future<void> _pump(WidgetTester tester, MockClientHandler h) async {
  tester.view.physicalSize = const Size(390, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final api = Api(client: MockClient(h), storage: _Mem());
  await api.restore();
  final state = AppState(api);
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(extensions: [TiniCosmicColors.dark, TiniTokens.dark]),
      home: ProfileScreen(api: api, state: state, onLogout: () {}),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows modes from cluster weights and the avoidance counts', (
    tester,
  ) async {
    await _pump(tester, (req) async {
      if (req.url.path == '/profile') {
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'vote_count': 40,
              'clusters': [
                {'id': 1, 'weight': 3.0, 'artists': []},
                {'id': 2, 'weight': 1.0, 'artists': []},
              ],
              'avoid': [
                {'artist_id': 1, 'strength': 1.0, 'hard': true},
                {'artist_id': 2, 'strength': 0.4, 'hard': false},
                {'artist_id': 3, 'strength': 0.4, 'hard': false},
              ],
            }),
          ),
          200,
        );
      }
      return http.Response('{}', 200);
    });
    expect(find.byKey(const ValueKey('mode-field')), findsOneWidget);
    expect(find.text('Mod 1'), findsOneWidget);
    expect(find.text('%75'), findsOneWidget);
    expect(find.text('%25'), findsOneWidget);
    expect(
      find.textContaining('Sert filtre', findRichText: true),
      findsOneWidget,
    );
    expect(
      find.textContaining('Yumuşak ceza ×2', findRichText: true),
      findsOneWidget,
    );
    expect(find.text('0 oy · 0 Efsane · 0 Dinlemedin'), findsOneWidget);
    expect(find.text('30 oy daha verince ayarlanacak'), findsOneWidget);
  });

  testWidgets('without a profile the mode and avoidance sections are empty', (
    tester,
  ) async {
    await _pump(
      tester,
      (req) async => req.url.path == '/profile'
          ? http.Response('{"detail":"Henüz profil üretilmedi"}', 404)
          : http.Response('{}', 200),
    );
    expect(find.byKey(const ValueKey('modes-empty')), findsOneWidget);
    expect(find.text('Henüz kaçındığımız bir şey yok.'), findsOneWidget);
  });
}
