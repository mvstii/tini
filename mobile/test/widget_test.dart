import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tini/api.dart';
import 'package:tini/preview_player.dart';
import 'package:tini/app_state.dart';
import 'package:tini/screens/discover_screen.dart';
import 'package:tini/main.dart';
import 'package:tini/screens/feedback_screen.dart';
import 'package:tini/screens/fresh_screen.dart';
import 'package:tini/screens/home_screen.dart';
import 'package:tini/screens/list_screen.dart';
import 'package:tini/screens/rating_screen.dart';
import 'package:tini/screens/shell.dart';
import 'package:tini/widgets/artist_avatar.dart';

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
  test('deleteAccount sends the password and clears the session only on success', () async {
    final storage = _MemoryStorage()..data['session'] = 'T1';
    Map? sent;
    var status = 403;
    final api = _api((req) async {
      expect(req.method, 'DELETE');
      expect(req.url.path, '/me');
      sent = jsonDecode(req.body) as Map;
      return http.Response(status == 204 ? '' : jsonEncode({'detail': 'wrong password'}), status);
    }, storage);
    await api.restore();

    await expectLater(api.deleteAccount('yanlis'), throwsA(isA<ApiException>()));
    expect(sent, {'password': 'yanlis'});
    expect(api.loggedIn, isTrue, reason: '403 oturumu düşürmemeli');

    status = 204;
    await api.deleteAccount('dogru');
    expect(api.loggedIn, isFalse);
    expect(storage.data, isEmpty);
  });

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

  test('theme preference is stored and defaults to system', () async {
    final storage = _MemoryStorage();
    final api = _api((r) async => http.Response('{}', 200), storage);
    expect(await api.loadTheme(), ThemeMode.system);
    await api.saveTheme(ThemeMode.dark);
    expect(await api.loadTheme(), ThemeMode.dark);
    storage.data['theme'] = 'bozuk';
    expect(await api.loadTheme(), ThemeMode.system);
  });

  testWidgets('logged-out app shows the login form', (tester) async {
    await tester.pumpWidget(TiniApp(api: _api((r) async => http.Response('{}', 200), _MemoryStorage())));
    expect(find.text('Giriş yap'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
  });

  group('rating screen', () {
    // Sunucu sahtesi: kuyruk, oy listesi ve sayaç.
    ({Api api, List<Map<String, int>> votes, List<String> calls, List<Map> bodies}) fake({
      int total = 0,
      List<Map<String, Object>>? items,
      int stale = 0,
      Duration delay = Duration.zero,
    }) {
      final votes = <Map<String, int>>[];
      final calls = <String>[];
      final bodies = <Map>[]; // /votes ve /votes/unheard gövdeleri (kaynak alanı için)
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
        if (req.method == 'POST' && req.url.path.startsWith('/votes')) {
          bodies.add(jsonDecode(req.body) as Map);
          await Future<void>.delayed(delay);
        }
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
      return (api: api, votes: votes, calls: calls, bodies: bodies);
    }

    Future<void> open(WidgetTester tester, Api api) async {
      await api.restore();
      await tester.pumpWidget(MaterialApp(home: RatingScreen(api: api)));
      await tester.pumpAndSettle();
    }

    testWidgets('card shows cover when present and a placeholder when absent', (tester) async {
      final f = fake(items: [
        {'track': 1, 'title': 'Alpha', 'artists': ['A'], 'image': 'https://i/cover.jpg'},
        {'track': 2, 'title': 'Beta', 'artists': ['B']},
      ]);
      await open(tester, f.api);
      // Test ortamında ağ yoktur: görsel yüklenemese de kart çökmeden yer tutucuya düşer.
      expect(find.byType(Image), findsOneWidget);
      expect(find.text('Alpha'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('vote-6')));
      await tester.pumpAndSettle();
      expect(find.text('Beta'), findsOneWidget);
      expect(find.byType(Image), findsNothing);
      expect(find.byIcon(Icons.music_note_rounded), findsOneWidget); // gradyan yer tutucu
    });

    testWidgets('autoplay on plays each new top card; off plays nothing', (tester) async {
      addTearDown(() => PreviewController.autoplay.value = false);
      final f = fake();
      await open(tester, f.api);
      expect(f.calls.where((c) => c.contains('/preview')), isEmpty); // kapalıyken çalmaz

      await tester.tap(find.byKey(const ValueKey('toggle-autoplay')));
      await tester.pumpAndSettle();
      expect(PreviewController.autoplay.value, isTrue);
      await tester.tap(find.byKey(const ValueKey('vote-6')));
      await tester.pumpAndSettle();
      // Açar açmaz Alpha, oydan sonra Beta için önizleme otomatik istendi.
      expect(f.calls.where((c) => c == 'GET /preview'), hasLength(2));
    });

    testWidgets('shows the first card and casts a button vote', (tester) async {
      final f = fake();
      await open(tester, f.api);
      expect(find.text('Alpha'), findsOneWidget);
      expect(find.text('Başlangıç Turu · 0 / $tourVotes'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('vote-6')));
      await tester.pumpAndSettle();

      expect(f.votes, [
        {'track': 1, 'vote': 6}
      ]);
      expect(find.text('Beta'), findsOneWidget);
      expect(find.text('B, C'), findsOneWidget);
      expect(find.text('Başlangıç Turu · 1 / $tourVotes'), findsOneWidget);
    });

    testWidgets('vote and unheard carry the card source (library when absent)', (tester) async {
      final f = fake(items: [
        {'track': 1, 'title': 'Alpha', 'artists': ['A'], 'source': 'probe'},
        {'track': 2, 'title': 'Beta', 'artists': ['B']},
      ]);
      await open(tester, f.api);

      await tester.tap(find.byKey(const ValueKey('vote-5')));
      await tester.pumpAndSettle();
      await tester.drag(find.text('Beta'), const Offset(-600, 0));
      await tester.pumpAndSettle();

      expect(f.bodies, [
        {'track': 1, 'vote': 5, 'source': 'probe'},
        {'track': 2, 'source': 'library'},
      ]);
    });

    testWidgets('swipe right adds to listen-later (no vote), swipe left skips', (tester) async {
      final f = fake();
      await open(tester, f.api);

      await tester.drag(find.text('Alpha'), const Offset(600, 0));
      await tester.pumpAndSettle();
      expect(f.votes, isEmpty);
      expect(f.calls, contains('POST /later'));
      expect(find.text('Sonra dinle listesine eklendi'), findsOneWidget);

      await tester.drag(find.text('Beta'), const Offset(-600, 0));
      await tester.pumpAndSettle();
      expect(f.votes, isEmpty);
      expect(f.calls, contains('POST /votes/unheard'));
      expect(find.text('Gamma'), findsOneWidget);
    });

    testWidgets('swipe with a slow server removes the card at once (no Dismissible error)',
        (tester) async {
      final f = fake(delay: const Duration(seconds: 1));
      await open(tester, f.api);

      await tester.drag(find.text('Alpha'), const Offset(-600, 0));
      await tester.pump(const Duration(milliseconds: 500)); // sunucu henüz yanıtlamadı
      await tester.pump(const Duration(milliseconds: 500));
      expect(tester.takeException(), isNull);
      expect(find.text('Alpha'), findsNothing);
      await tester.pumpAndSettle(const Duration(seconds: 2));
      expect(f.calls, contains('POST /votes/unheard'));
      expect(find.text('Beta'), findsOneWidget);
    });

    testWidgets('undo brings the card back and a new vote is a new event', (tester) async {
      final f = fake();
      await open(tester, f.api);

      await tester.tap(find.byKey(const ValueKey('vote-2')));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Geri al'));
      await tester.pumpAndSettle();
      expect(find.text('Alpha'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('vote-5')));
      await tester.pumpAndSettle();
      expect(f.votes, [
        {'track': 1, 'vote': 2},
        {'track': 1, 'vote': 5},
      ]);
      // Aynı parçaya yeni oy sayacı artırmaz (sunucu da parça başına güncel oyu sayar).
      expect(find.text('Başlangıç Turu · 1 / $tourVotes'), findsOneWidget);
    });

    testWidgets('undo of a re-vote writes the previous vote as a new event', (tester) async {
      final f = fake();
      await open(tester, f.api);

      await tester.tap(find.byKey(const ValueKey('vote-2')));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Geri al')); // ilk oyda önceki oy yok: sunucuya yazılmaz
      await tester.pumpAndSettle();
      expect(f.votes, [
        {'track': 1, 'vote': 2},
      ]);

      await tester.tap(find.byKey(const ValueKey('vote-5')));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Geri al')); // önceki oy (2) yeni olay olarak geri yazılır
      await tester.pumpAndSettle();
      expect(f.votes, [
        {'track': 1, 'vote': 2},
        {'track': 1, 'vote': 5},
        {'track': 1, 'vote': 2},
      ]);
      expect(find.text('Alpha'), findsOneWidget); // kart yine kuyruğun başında
    });

    testWidgets('offers profile build after the tour and rebuilds', (tester) async {
      final f = fake(total: tourVotes - 1);
      await open(tester, f.api);
      expect(find.text('Profili Kur'), findsNothing);

      await tester.tap(find.byKey(const ValueKey('vote-4')));
      await tester.pumpAndSettle();
      expect(find.text('Profili Kur'), findsOneWidget);

      await tester.tap(find.text('Profili Kur'));
      await tester.pumpAndSettle();
      expect(f.calls, contains('POST /profile/rebuild'));
      expect(find.byType(ListScreen), findsOneWidget); // profil kurulunca keşif listesine geçer
    });

    testWidgets('progress bar levels up and refills after each tour', (tester) async {
      final f = fake(total: tourVotes - 1);
      await open(tester, f.api);
      await tester.tap(find.byKey(const ValueKey('vote-4')));
      await tester.pumpAndSettle();
      expect(find.text('Seviye 2 · 0 / $tourVotes · Toplam $tourVotes'), findsOneWidget);
      expect(tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator)).value,
          0.0);
    });

    testWidgets('rapid votes never show the empty state while the queue refills', (tester) async {
      final items = [
        for (var i = 1; i <= 9; i++) {'track': i, 'title': 'T$i', 'artists': ['A$i']},
      ];
      final f = fake(items: items);
      await open(tester, f.api);
      for (var i = 1; i <= 8; i++) {
        // Son parça oylanınca boş durum meşrudur; ondan önce hiç görünmemeli.
        await tester.tap(find.byKey(const ValueKey('vote-4')));
        await tester.pump(); // beklemeden art arda
        await tester.pump(const Duration(milliseconds: 10));
        expect(find.text('Yeniden dene'), findsNothing);
      }
      await tester.pumpAndSettle();
      expect(f.votes.length, 8);
    });

    testWidgets('empty queue with stale metadata offers a library refresh', (tester) async {
      final f = fake(items: [], stale: 3);
      await open(tester, f.api);
      // Kuyruk eskiyen önbellek yüzünden kuruyunca kütüphane kullanıcı dokunmadan yenilenir.
      expect(f.calls.where((c) => c == 'POST /library/import').length, 1);
      // Yenileme sonrası hâlâ eskiyse elle düğme yedek olarak kalır (tekrar denemez).
      expect(find.textContaining('3 şarkının bilgisi eskidi'), findsOneWidget);

      await tester.tap(find.text('Kütüphaneyi yenile'));
      await tester.pumpAndSettle();
      expect(f.calls, contains('POST /library/import'));
    });
  });

  group('fresh screen', () {
    final feedJson = {
      'total': 1,
      'items': [
        {'release_id': 1, 'title': 'Yeni Albüm', 'type': 'album', 'released': '2026-10-30',
         'artist_id': 5, 'artist': 'Sanatçı X', 'follow': 'auto'},
      ],
    };
    final freshJson = {
      'id': 9,
      'items': [
        {
          'position': 1,
          'name': 'Sanatçı X',
          'title': null,
          'release': {'id': 1, 'title': 'Yeni Albüm', 'type': 'album', 'released': '2026-10-30'},
          'reasons': [
            {'seed_id': 10, 'seed_name': 'Seed A', 'share': 1.0, 'is_anchor': true},
          ],
        }
      ],
    };

    testWidgets('shows the feed on open and generates the fresh list', (tester) async {
      final api = _api((req) async {
        if (req.url.path == '/releases/new') {
          return http.Response.bytes(utf8.encode(jsonEncode(feedJson)), 200);
        }
        if (req.url.path == '/lists/generate-fresh') {
          return http.Response.bytes(utf8.encode(jsonEncode(freshJson)), 201);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: FreshScreen(api: api)));
      await tester.pumpAndSettle();
      expect(find.text('Yeni Albüm'), findsOneWidget);
      expect(find.textContaining('Sanatçı X · album · 2026-10-30'), findsOneWidget);

      await tester.tap(find.text('Taze liste üret'));
      await tester.pumpAndSettle();
      expect(find.text('1. Yeni Albüm'), findsOneWidget);
      expect(find.textContaining('★ Seed A %100'), findsOneWidget);
    });

    testWidgets('no new releases shows a hint', (tester) async {
      final api = _api((req) async {
        if (req.url.path == '/lists/generate-fresh') {
          return http.Response.bytes(utf8.encode(jsonEncode({'detail': 'yok'})), 409);
        }
        return http.Response(jsonEncode({'items': [], 'total': 0}), 200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: FreshScreen(api: api)));
      await tester.pumpAndSettle();
      expect(find.text('Henüz yeni yayın yok.'), findsOneWidget);
      await tester.tap(find.text('Taze liste üret'));
      await tester.pumpAndSettle();
      expect(find.text('Takip ettiğin sanatçıların yeni yayını yok.'), findsOneWidget);
    });
  });

  group('list screen', () {
    final listJson = {
      'id': 7,
      'items': [
        {
          'position': 1,
          'name': 'Beta',
          'title': null,
          'reasons': [
            {'seed_id': 10, 'seed_name': 'Seed A', 'share': 0.6, 'is_anchor': true},
            {'seed_id': 11, 'seed_name': 'Seed B', 'share': 0.4, 'is_anchor': false},
          ],
        }
      ],
    };

    testWidgets('shows a release item in the main list as "yeni"', (tester) async {
      final withRelease = {
        'id': 8,
        'items': [
          {
            'position': 1,
            'name': 'Gama',
            'title': null,
            'release': {'id': 1, 'title': 'Yeni Albüm', 'type': 'album', 'released': '2026-10-30'},
            'reasons': [
              {'seed_id': 10, 'seed_name': 'Seed A', 'share': 1.0, 'is_anchor': true},
            ],
          }
        ],
      };
      final api = _api((req) async =>
          http.Response.bytes(utf8.encode(jsonEncode(withRelease)), 201), _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: ListScreen(api: api)));
      await tester.tap(find.text('Liste üret'));
      await tester.pumpAndSettle();
      expect(find.text('yeni'), findsOneWidget);
      expect(find.text('Yeni Albüm · album · 2026-10-30'), findsOneWidget);
    });

    testWidgets('ArtistAvatar shows the initial when there is no photo', (tester) async {
      await tester.pumpWidget(const MaterialApp(home: Scaffold(body: ArtistAvatar(name: 'gama'))));
      expect(find.text('G'), findsOneWidget);
      expect(find.byType(Image), findsNothing);
    });

    testWidgets('list asks for missing artist photos until none are pending', (tester) async {
      final calls = <String>[];
      final json = {
        'id': 9,
        'items': [
          for (final (i, id) in [10, 11].indexed)
            {
              'position': i + 1,
              'name': 'Sanatçı$id',
              'artist_id': id,
              'artist_image': null,
              'title': null,
              'reasons': [
                {'seed_id': 1, 'seed_name': 'Seed', 'share': 1.0, 'is_anchor': true},
              ],
            }
        ],
      };
      final api = _api((req) async {
        if (req.url.path == '/lists/generate') {
          return http.Response.bytes(utf8.encode(jsonEncode(json)), 201);
        }
        calls.add(req.url.queryParameters['ids']!);
        final first = calls.length == 1;
        return http.Response(
            jsonEncode({
              'images': first ? {'10': 'http://img/10.jpg'} : {'11': null},
              'pending': first ? 1 : 0,
            }),
            200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: ListScreen(api: api)));
      await tester.tap(find.text('Liste üret'));
      await tester.pumpAndSettle();
      expect(calls, ['10,11', '11']);
      // 11'in fotoğrafı yok; 10'unki testte yüklenemez: ikisi de baş harf yer tutucuya düşer.
      expect(find.text('S'), findsNWidgets(2));
    });

    test('reasonText orders by share and marks anchors', () {
      final e = ListEntry(1, 'X', null, [
        Reason(2, 'Low', 0.1, false),
        Reason(1, 'High', 0.9, true),
      ]);
      expect(reasonText(e), 'Sevdiğin sanatçılara benzediği için: ★ High %90, Low %10');
    });

    testWidgets('generates, shows reasons and records an objection', (tester) async {
      Object? feedback;
      final api = _api((req) async {
        if (req.url.path == '/lists/generate') {
          return http.Response.bytes(utf8.encode(jsonEncode(listJson)), 201);
        }
        if (req.url.path == '/lists/7/items/1/feedback') {
          feedback = jsonDecode(req.body);
          return http.Response('{}', 201);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: ListScreen(api: api)));

      await tester.tap(find.text('Liste üret'));
      await tester.pumpAndSettle();
      expect(find.text('1. Beta'), findsOneWidget);
      expect(find.text('keşif'), findsNothing); // varsayılan etiket gösterilmez
      expect(find.text('NEDEN SANA?'), findsOneWidget);
      expect(find.textContaining('Seed A', findRichText: true), findsOneWidget);
      expect(find.textContaining('%60', findRichText: true), findsOneWidget);

      await tester.tap(find.text('Bu gerekçe yanlış'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Seed B').last);
      await tester.pumpAndSettle();
      expect(feedback, {'kind': 'wrong_reason', 'seed_id': 11});
      expect(find.text('Geri bildirimin kaydedildi'), findsOneWidget);
    });

    testWidgets('opens the item in Spotify via the resolved link', (tester) async {
      String? launched;
      final api = _api((req) async {
        if (req.url.path == '/lists/generate') {
          return http.Response.bytes(utf8.encode(jsonEncode(listJson)), 201);
        }
        if (req.url.path == '/lists/7/items/1/open') {
          return http.Response('{"kind": "track", "url": "spotify:track:T1"}', 200);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(
        home: ListScreen(api: api, launch: (u) async {
          launched = u;
          return true;
        }),
      ));
      await tester.tap(find.text('Liste üret'));
      await tester.pumpAndSettle();
      await tester.tap(find.text("Spotify'da aç"));
      await tester.pumpAndSettle();
      expect(launched, 'spotify:track:T1');
    });

    testWidgets('shows a hint when the service is not connected', (tester) async {
      final api = _api((req) async {
        if (req.url.path == '/lists/generate') {
          return http.Response.bytes(utf8.encode(jsonEncode(listJson)), 201);
        }
        return http.Response.bytes(utf8.encode('{"detail": "Servis bağlı değil"}'), 409);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: ListScreen(api: api)));
      await tester.tap(find.text('Liste üret'));
      await tester.pumpAndSettle();
      await tester.tap(find.text("Spotify'da aç"));
      await tester.pumpAndSettle();
      expect(find.text("Önce Spotify'ı bağla."), findsOneWidget);
    });

    testWidgets('no profile yet shows a hint', (tester) async {
      final api = _api((req) async => http.Response('{"detail": "x"}', 404), _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: ListScreen(api: api)));
      await tester.tap(find.text('Liste üret'));
      await tester.pumpAndSettle();
      expect(find.text('Önce oylayıp profilini kur.'), findsOneWidget);
    });

    testWidgets('saves the list to Spotify and reports skipped items', (tester) async {
      var exported = false;
      final api = _api((req) async {
        if (req.url.path == '/lists/generate') {
          return http.Response.bytes(utf8.encode(jsonEncode(listJson)), 201);
        }
        if (req.url.path == '/lists/7/export/spotify') {
          exported = true;
          return http.Response('{"playlist_id": "PL1", "added": 3, "skipped": [2, 5], "skipped_names": ["Child Rebel Soldier", "Foo"]}', 201);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: ListScreen(api: api)));
      expect(find.text("Spotify'a kaydet"), findsNothing);
      await tester.tap(find.text('Liste üret'));
      await tester.pumpAndSettle();
      await tester.tap(find.text("Spotify'a kaydet"));
      await tester.pumpAndSettle();
      expect(exported, isTrue);
      expect(
        find.text("Spotify'a kaydedildi: 3 parça, 2 öğe atlandı (Child Rebel Soldier, Foo)"),
        findsOneWidget,
      );
    });
  });

  group('feedback screen', () {
    testWidgets('sends kind, version and message', (tester) async {
      Map<String, dynamic>? sent;
      final api = _api((req) async {
        if (req.url.path == '/feedback' && req.method == 'POST') {
          sent = jsonDecode(req.body) as Map<String, dynamic>;
          return http.Response('{"id": 1}', 201);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: FeedbackScreen(api: api)));
      await tester.tap(find.text('Öneri'));
      await tester.enterText(find.byType(TextField), 'Kapak olsun');
      await tester.tap(find.text('Gönder'));
      await tester.pumpAndSettle();
      expect(sent,
          {'kind': 'idea', 'screen': 'home', 'app_version': appVersion, 'message': 'Kapak olsun'});
      expect(find.text('Teşekkürler, iletildi.'), findsOneWidget);
    });

    testWidgets('rejects a too short message without calling the server', (tester) async {
      var calls = 0;
      final api = _api((req) async {
        calls++;
        return http.Response('{}', 200);
      }, _MemoryStorage());
      await tester.pumpWidget(MaterialApp(home: FeedbackScreen(api: api)));
      await tester.enterText(find.byType(TextField), 'a');
      await tester.tap(find.text('Gönder'));
      await tester.pumpAndSettle();
      expect(find.text('En az 3 karakter yaz'), findsOneWidget);
      expect(calls, 0);
    });
  });
  group('daily song', () {
    Api daily(int status, [Map<String, Object?>? body]) => _api((req) async {
          if (req.url.path == '/recommend/daily') {
            return http.Response.bytes(utf8.encode(jsonEncode(body ?? {'detail': 'x'})), status);
          }
          if (req.url.path == '/lists/7/items/3/open') {
            return http.Response(jsonEncode({'kind': 'track', 'url': 'spotify:track:T1'}), 200);
          }
          if (req.url.path == '/connect') return http.Response('[]', 200);
          return http.Response('[]', 200);
        }, _MemoryStorage()..data['session'] = 'T');

    final song = {
      'list_id': 7,
      'position': 3,
      'name': 'Sanatçı',
      'title': 'Şarkı Adı',
      'artists': ['Sanatçı', 'Konuk'],
      'image': null,
      'reasons': [
        {'seed_id': 1, 'seed_name': 'Seed', 'share': 0.6, 'is_anchor': true},
      ],
    };

    testWidgets('card shows title, artists and the reason, and opens the song', (tester) async {
      final api = daily(200, song);
      await api.restore();
      final opened = <String>[];
      await tester.pumpWidget(MaterialApp(
          home: HomeScreen(api: api, onLogout: () {}, launch: (u) async {
            opened.add(u);
            return true;
          })));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Günün şarkısı'), 200);
      expect(find.text('Şarkı Adı'), findsOneWidget);
      expect(find.text('Sanatçı, Konuk'), findsOneWidget);
      expect(find.textContaining('★ Seed %60'), findsOneWidget);

      await tester.tap(find.text('Şarkı Adı'));
      await tester.pumpAndSettle();
      expect(opened, ['spotify:track:T1']);
    });

    testWidgets('card is hidden when there is no profile yet', (tester) async {
      final api = daily(404);
      await api.restore();
      await tester.pumpWidget(MaterialApp(home: HomeScreen(api: api, onLogout: () {})));
      await tester.pumpAndSettle();
      expect(find.text('Günün şarkısı'), findsNothing);
      expect(find.text('Yeni çıkanlar'), findsOneWidget);
    });
  });

  group('discover screen', () {
    final dailyJson = {
      'list_id': 7,
      'position': 3,
      'track': 11,
      'name': 'Sanatçı',
      'title': 'Şarkı Adı',
      'artists': ['Sanatçı'],
      'image': null,
      'reasons': [
        {'seed_id': 1, 'seed_name': 'Seed', 'share': 0.6, 'is_anchor': true},
      ],
    };
    final castVotes = <Map>[];
    final feedJson = {
      'total': 3,
      'items': [
        for (var i = 1; i <= 3; i++)
          {'release_id': i, 'title': 'Albüm $i', 'type': 'album', 'released': '2026-10-30',
           'artist_id': i, 'artist': 'Sanatçı $i', 'follow': 'auto'},
      ],
    };

    Future<(Api, AppState)> setup(
        {bool hasDaily = true, bool hasFeed = true, bool hasTracks = false}) async {
      final api = _api((req) async {
        if (req.url.path == '/releases/new-tracks' && hasTracks) {
          return http.Response.bytes(
              utf8.encode(jsonEncode({
                'releases': 1,
                'items': [
                  {'deezer_id': 77, 'title': 'Yeni Parça', 'artist': 'Sanatçı X',
                   'release': 'Albüm X', 'type': 'Album', 'released': '2026-10-30'},
                ],
              })),
              200);
        }
        if (req.url.path == '/recommend/daily') {
          return hasDaily
              ? http.Response.bytes(utf8.encode(jsonEncode(dailyJson)), 200)
              : http.Response.bytes(utf8.encode('{"detail":"Henüz profil üretilmedi"}'), 404);
        }
        if (req.url.path == '/releases/new') {
          return http.Response.bytes(
              utf8.encode(jsonEncode(hasFeed ? feedJson : {'total': 0, 'items': []})), 200);
        }
        if (req.url.path == '/lists/7/items/3/open') {
          return http.Response(jsonEncode({'kind': 'track', 'url': 'spotify:track:T1'}), 200);
        }
        if (req.method == 'POST' && req.url.path == '/votes') {
          castVotes.add(jsonDecode(req.body) as Map);
          return http.Response('{}', 201);
        }
        return http.Response('{"total":0,"items":[]}', 200);
      }, _MemoryStorage()..data['session'] = 'T');
      await api.restore();
      return (api, AppState(api));
    }

    Widget host(Api api, AppState s, {VoidCallback? rate, VoidCallback? profile, List<String>? opened}) =>
        MaterialApp(
          home: Scaffold(
            body: DiscoverScreen(
              api: api,
              state: s,
              onLogout: () {},
              onOpenRating: rate ?? () {},
              onOpenProfile: profile ?? () {},
              launch: (u) async {
                opened?.add(u);
                return true;
              },
            ),
          ),
        );

    testWidgets('lists this week\'s new tracks with a play button, hidden when empty', (tester) async {
      tester.view.physicalSize = const Size(360, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      var (api, s) = await setup(hasTracks: true);
      await tester.pumpWidget(host(api, s));
      await tester.pumpAndSettle();
      expect(find.text('BU HAFTA ÇIKANLAR'), findsOneWidget);
      expect(find.text('Yeni Parça'), findsOneWidget);
      expect(find.byKey(const ValueKey('new-track-77')), findsOneWidget);

      await tester.pumpWidget(const SizedBox()); // eski State atılsın
      (api, s) = await setup();
      await tester.pumpWidget(host(api, s));
      await tester.pumpAndSettle();
      expect(find.text('BU HAFTA ÇIKANLAR'), findsNothing);
    });

    testWidgets('shows the hero with the real reason and opens the song', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final (api, s) = await setup();
      final opened = <String>[];
      var rated = 0;
      await tester.pumpWidget(host(api, s, opened: opened, rate: () => rated++));
      await tester.pumpAndSettle();
      expect(find.text('Keşfet'), findsOneWidget);
      expect(find.text('Şarkı Adı'), findsOneWidget);
      expect(find.textContaining('★ Seed %60'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('daily-vote-5')));
      await tester.pumpAndSettle();
      expect(castVotes, [
        {'track': 11, 'vote': 5}
      ]);
      expect(s.votes[11], 5);
      expect(find.text('Oyun kaydedildi: 5 · Çok iyi'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('daily-open')));
      await tester.pumpAndSettle();
      expect(opened, ['spotify:track:T1']);
      await tester.tap(find.byKey(const ValueKey('daily-rate')));
      expect(rated, 1);
      expect(tester.takeException(), isNull);
    });

    testWidgets('no profile hides the hero; no releases shows a hint', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final (api, s) = await setup(hasDaily: false, hasFeed: false);
      await tester.pumpWidget(host(api, s));
      await tester.pumpAndSettle();
      expect(find.text('GÜNÜN ŞARKISI'), findsNothing);
      expect(find.text('Günün şarkısı için önce oylayıp profilini kur.'), findsOneWidget);
      expect(find.text('Henüz yeni yayın yok.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('shuffle keeps all releases and the level badge opens the profile', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final (api, s) = await setup();
      var profile = 0;
      await tester.pumpWidget(host(api, s, profile: () => profile++));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('level-badge')));
      expect(profile, 1);
      await tester.scrollUntilVisible(find.byKey(const ValueKey('shuffle')), 200,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(find.byKey(const ValueKey('shuffle')));
      await tester.pumpAndSettle();
      for (final n in [1, 2, 3]) {
        expect(find.textContaining('Albüm $n', skipOffstage: false), findsWidgets);
      }
      expect(tester.takeException(), isNull);
    });

    test('relativeDate', () {
      final now = DateTime(2026, 11, 3);
      expect(relativeDate('2026-11-03', now), 'Bugün');
      expect(relativeDate('2026-11-02', now), 'Dün');
      expect(relativeDate('2026-10-30', now), '4 gün önce');
      expect(relativeDate('2026-10-24', now), 'Geçen hafta');
      expect(relativeDate('2026-01-01', now), '2026-01-01');
    });
  });

  group('app shell', () {
    testWidgets('fits 360x640 and locked recommendations unlock at $tourVotes votes',
        (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final api = _api((req) async {
        switch (req.url.path) {
          case '/votes/history':
            return http.Response(jsonEncode({'total': 0, 'items': []}), 200);
          case '/votes/queue':
            return http.Response.bytes(
                utf8.encode(jsonEncode({
                  'remaining': 1,
                  'stale': 0,
                  'items': [
                    {'track': 1, 'title': 'Alpha', 'artists': ['A']},
                  ],
                })),
                200);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage()..data['session'] = 'T');
      await api.restore();
      await tester.pumpWidget(MaterialApp(home: AppShell(api: api, onLogout: () {})));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);

      await tester.tap(find.byKey(const ValueKey('tab-0')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('level-badge')), findsOneWidget);
      expect(tester.takeException(), isNull);

      await tester.tap(find.byKey(const ValueKey('tab-2')));
      await tester.pumpAndSettle();
      expect(find.text('Oylamaya Devam Et'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('tab-3')));
      await tester.pumpAndSettle();
      expect(find.text('OY DAĞILIMI'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('30 votes unlock recommendations, show the dot, and profile counts follow',
        (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final votes = <Map<String, int>>[];
      final queue = [
        for (var i = 1; i <= 40; i++)
          {'track': i, 'title': 'Song $i', 'artists': ['Art $i']},
      ];
      final api = _api((req) async {
        switch (req.url.path) {
          case '/votes/history':
            return http.Response.bytes(
                utf8.encode(jsonEncode({
                  'total': votes.length,
                  'items': [
                    for (final v in votes.reversed)
                      {'track': v['track'], 'title': 'Song ${v['track']}', 'artists': ['Art'], 'vote': v['vote']},
                  ],
                })),
                200);
          case '/votes/queue':
            final voted = votes.map((v) => v['track']).toSet();
            final rest = queue.where((i) => !voted.contains(i['track'])).toList();
            return http.Response.bytes(
                utf8.encode(jsonEncode({'remaining': rest.length, 'stale': 0, 'items': rest})),
                200);
          case '/votes':
            final b = jsonDecode(req.body) as Map;
            votes.add({'track': b['track'] as int, 'vote': b['vote'] as int});
            return http.Response('{}', 201);
        }
        return http.Response('{}', 200);
      }, _MemoryStorage()..data['session'] = 'T');
      await api.restore();
      await tester.pumpWidget(MaterialApp(home: AppShell(api: api, onLogout: () {})));
      await tester.pumpAndSettle();

      for (var i = 0; i < tourVotes; i++) {
        await tester.tap(find.byKey(ValueKey('vote-${i < 20 ? 6 : 3}')));
        await tester.pumpAndSettle();
      }
      expect(tester.takeException(), isNull);
      expect(find.text('Profili Kur'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('tab-2')));
      await tester.pumpAndSettle();
      expect(find.text('Oylamaya Devam Et'), findsNothing);

      await tester.tap(find.byKey(const ValueKey('tab-3')));
      await tester.pumpAndSettle();
      expect(tester.widget<Text>(find.byKey(const ValueKey('count-6'))).data, '20');
      expect(tester.widget<Text>(find.byKey(const ValueKey('count-3'))).data, '10');
      expect(find.text('Seviye 2'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}
