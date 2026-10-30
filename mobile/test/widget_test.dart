import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tini/api.dart';
import 'package:tini/main.dart';
import 'package:tini/screens/rating_screen.dart';

class _MemoryStorage extends FlutterSecureStorage {
  final data = <String, String>{};
  @override
  Future<String?> read({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async => data[key];
  @override
  Future<void> write({required String key, required String? value, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async {
    data[key] = value!;
  }
  @override
  Future<void> delete({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async {
    data.remove(key);
  }
}

Api _api(MockClientHandler handler, _MemoryStorage storage) =>
    Api(client: MockClient(handler), storage: storage);

void main() {
  test('login stores the session and sends it as Bearer', () async {
    final storage = _MemoryStorage();
    String? auth;
    final api = _api((req) async {
      if (req.url.path == '/auth/login') {
        return http.Response(jsonEncode({'token': 'T1'}), 200);
      }
      auth = req.headers['Authorization'];
      return http.Response(
          jsonEncode([{'service': 'spotify', 'external_user_id': 'u'}]), 200);
    }, storage);

    await api.login('a@b.co', 'x');
    expect(api.loggedIn, isTrue);
    expect(storage.data['session'], 'T1');
    final conns = await api.connections();
    expect(auth, 'Bearer T1');
    expect(conns.single.service, 'spotify');
  });

  test('error detail is surfaced and 401 clears the session', () async {
    final storage = _MemoryStorage()..data['session'] = 'OLD';
    final api = _api(
        (req) async => http.Response.bytes(utf8.encode(jsonEncode({'detail': 'Oturum geçersiz'})), 401),
        storage);
    await api.restore();
    expect(api.loggedIn, isTrue);
    await expectLater(
        api.connections(), throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Oturum geçersiz')));
    expect(api.loggedIn, isFalse);
    expect(storage.data.containsKey('session'), isFalse);
  });

  testWidgets('logged-out app shows the login form', (tester) async {
    await tester.pumpWidget(TiniApp(api: _api((r) async => http.Response('{}', 200), _MemoryStorage())));
    expect(find.text('Giriş yap'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
  });

  group('rating screen', () {
    // Sunucu sahtesi: kuyruk, oy listesi ve sayaç.
    ({Api api, List<Map<String, int>> votes, List<String> calls}) fake({
      int total = 0,
      List<Map<String, Object>>? items,
      int stale = 0,
    }) {
      final votes = <Map<String, int>>[];
      final calls = <String>[];
      final queue = [
        ...(items ??
            [
              {'track': 1, 'title': 'Alpha', 'artists': ['A']},
              {'track': 2, 'title': 'Beta', 'artists': ['B', 'C']},
              {'track': 3, 'title': 'Gamma', 'artists': ['D']},
              {'track': 4, 'title': 'Delta', 'artists': ['E']},
            ]),
      ];
      final api = _api((req) async {
        calls.add('${req.method} ${req.url.path}');
        switch (req.url.path) {
          case '/votes/history':
            return http.Response(jsonEncode({'total': total + votes.length, 'items': []}), 200);
          case '/votes/queue':
            final voted = votes.map((v) => v['track']).toSet();
            final rest = queue.where((i) => !voted.contains(i['track'])).toList();
            return http.Response.bytes(
                utf8.encode(jsonEncode({'remaining': rest.length, 'stale': stale, 'items': rest})),
                200);
          case '/votes':
            final b = jsonDecode(req.body) as Map;
            votes.add({'track': b['track'] as int, 'vote': b['vote'] as int});
            return http.Response('{}', 201);
          case '/library/import':
            return http.Response('{"imported": 3, "skipped": 0}', 200);
          case '/profile/rebuild':
            return http.Response('{"version": 1}', 201);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage()..data['session'] = 'T');
      return (api: api, votes: votes, calls: calls);
    }

    Future<void> open(WidgetTester tester, Api api) async {
      await api.restore();
      await tester.pumpWidget(MaterialApp(home: RatingScreen(api: api)));
      await tester.pumpAndSettle();
    }

    testWidgets('shows the first card and casts a button vote', (tester) async {
      final f = fake();
      await open(tester, f.api);
      expect(find.text('Alpha'), findsOneWidget);
      expect(find.text('Başlangıç turu: 0 / $tourVotes oy'), findsOneWidget);

      await tester.tap(find.text('6 · Amazing'));
      await tester.pumpAndSettle();

      expect(f.votes, [
        {'track': 1, 'vote': 6}
      ]);
      expect(find.text('Beta'), findsOneWidget);
      expect(find.text('B, C'), findsOneWidget);
      expect(find.text('Başlangıç turu: 1 / $tourVotes oy'), findsOneWidget);
    });

    testWidgets('swipe right votes Great, swipe left skips without a vote', (tester) async {
      final f = fake();
      await open(tester, f.api);

      await tester.drag(find.text('Alpha'), const Offset(600, 0));
      await tester.pumpAndSettle();
      expect(f.votes, [
        {'track': 1, 'vote': swipeRightVote}
      ]);

      await tester.drag(find.text('Beta'), const Offset(-600, 0));
      await tester.pumpAndSettle();
      expect(f.votes.length, 1);
      expect(find.text('Gamma'), findsOneWidget);
    });

    testWidgets('undo brings the card back and a new vote is a new event', (tester) async {
      final f = fake();
      await open(tester, f.api);

      await tester.tap(find.text('2 · Bad'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Geri al'));
      await tester.pumpAndSettle();
      expect(find.text('Alpha'), findsOneWidget);

      await tester.tap(find.text('5 · Great'));
      await tester.pumpAndSettle();
      expect(f.votes, [
        {'track': 1, 'vote': 2},
        {'track': 1, 'vote': 5},
      ]);
    });

    testWidgets('offers profile build after the tour and rebuilds', (tester) async {
      final f = fake(total: tourVotes - 1);
      await open(tester, f.api);
      expect(find.text('Profili kur'), findsNothing);

      await tester.tap(find.text('4 · Good'));
      await tester.pumpAndSettle();
      expect(find.text('Profili kur'), findsOneWidget);

      await tester.tap(find.text('Profili kur'));
      await tester.pumpAndSettle();
      expect(f.calls, contains('POST /profile/rebuild'));
      expect(find.text('Profil güncellendi'), findsOneWidget);
    });

    testWidgets('empty queue with stale metadata offers a library refresh', (tester) async {
      final f = fake(items: [], stale: 3);
      await open(tester, f.api);
      expect(find.textContaining('3 şarkının bilgisi eskidi'), findsOneWidget);

      await tester.tap(find.text('Kütüphaneyi yenile'));
      await tester.pumpAndSettle();
      expect(f.calls, contains('POST /library/import'));
    });
  });
}
