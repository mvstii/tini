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

  testWidgets('uses server mode names and falls back to Mod N when unnamed', (
    tester,
  ) async {
    await _pump(tester, (req) async {
      if (req.url.path == '/profile') {
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'vote_count': 40,
              'clusters': [
                {'id': 1, 'weight': 3.0, 'name': 'Trap', 'tags': ['Boom Bap'], 'artists': []},
                {'id': 2, 'weight': 1.0, 'name': null, 'tags': [], 'artists': []},
              ],
              'avoid': [],
            }),
          ),
          200,
        );
      }
      return http.Response('{}', 200);
    });
    expect(find.text('Trap'), findsOneWidget);
    expect(find.text('Mod 1'), findsNothing);
    expect(find.text('Mod 2'), findsOneWidget);
  });

  test('vote history carries the cached cover image', () async {
    final api = Api(
      client: MockClient(
        (req) async => http.Response(
          jsonEncode({
            'total': 2,
            'items': [
              {'track': 1, 'vote': 5, 'title': 'A', 'artists': ['X'], 'image': 'http://img/a.jpg'},
              {'track': 2, 'vote': 4, 'title': 'B', 'artists': [], 'image': null},
            ],
          }),
          200,
        ),
      ),
      storage: _Mem(),
    );
    await api.restore();
    final r = await api.voteSummary();
    expect(r.items.map((h) => h.image), ['http://img/a.jpg', null]);
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
    expect(find.byKey(const ValueKey('profile-error')), findsNothing);
    expect(find.text('Henüz kaçındığımız bir şey yok.'), findsOneWidget);
  });

  testWidgets('a failed profile load is shown as an error, not as "no profile", and retry recovers',
      (tester) async {
    var fail = true;
    await _pump(tester, (req) async {
      if (req.url.path == '/profile') {
        if (fail) return http.Response('{"detail":"Sunucu hatası"}', 500);
        return http.Response.bytes(
          utf8.encode(jsonEncode({
            'version': 7,
            'created_at': '2026-11-14T10:00:00+00:00',
            'vote_count': 40,
            'clusters': [
              {'id': 1, 'weight': 1.0, 'artists': []},
            ],
            'avoid': [],
          })),
          200,
        );
      }
      return http.Response('{}', 200);
    });
    expect(find.byKey(const ValueKey('profile-error')), findsOneWidget);
    expect(find.byKey(const ValueKey('modes-empty')), findsNothing);
    expect(find.byKey(const ValueKey('profile-stamp')), findsNothing);

    fail = false;
    await tester.tap(find.text('Yeniden dene'));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('profile-error')), findsNothing);
    expect(find.byKey(const ValueKey('mode-field')), findsOneWidget);
    expect(find.textContaining('Profil sürümü 7 · '), findsOneWidget);
  });

  testWidgets('profile without version metadata shows no stamp', (tester) async {
    await _pump(tester, (req) async {
      if (req.url.path == '/profile') {
        return http.Response.bytes(
          utf8.encode(jsonEncode({
            'vote_count': 40,
            'clusters': [
              {'id': 1, 'weight': 1.0, 'artists': []},
            ],
            'avoid': [],
          })),
          200,
        );
      }
      return http.Response('{}', 200);
    });
    expect(find.byKey(const ValueKey('mode-field')), findsOneWidget);
    expect(find.byKey(const ValueKey('profile-stamp')), findsNothing);
  });
}
