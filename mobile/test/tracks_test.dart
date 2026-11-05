import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tini/api.dart';
import 'package:tini/screens/tracks_screen.dart';

class _Mem extends FlutterSecureStorage {
  final data = <String, String>{'session': 'T'};
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

Future<Api> _api(Future<http.Response> Function(http.Request) h) async {
  final api = Api(client: MockClient(h), storage: _Mem());
  await api.restore();
  return api;
}

http.Response _json(Object o, [int code = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(o)), code);

void main() {
  testWidgets('later list shows titles, removes an item and exports', (tester) async {
    final calls = <String>[];
    var items = [
      {'track': 1, 'title': 'Şarkı Bir', 'artists': ['A'], 'image': null},
      {'track': 2, 'title': 'Şarkı İki', 'artists': ['B'], 'image': null},
    ];
    final api = await _api((r) async {
      calls.add('${r.method} ${r.url.path}');
      if (r.method == 'GET' && r.url.path == '/later') return _json({'items': items});
      if (r.method == 'DELETE') {
        items = items.where((e) => '/later/${e['track']}' != r.url.path).toList();
        return http.Response('', 204);
      }
      if (r.url.path == '/later/export/spotify') {
        return _json({'playlist_id': 'PL', 'added': 2, 'skipped': []}, 201);
      }
      return _json({});
    });
    await tester.pumpWidget(MaterialApp(home: LaterScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('Şarkı Bir'), findsOneWidget);

    await tester.tap(find.byType(PopupMenuButton<String>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Listeden çıkar'));
    await tester.pumpAndSettle();
    expect(find.text('Şarkı Bir'), findsNothing);
    expect(calls, contains('DELETE /later/1'));

    await tester.tap(find.text('Spotify’a aktar'));
    await tester.pumpAndSettle();
    expect(calls, contains('POST /later/export/spotify'));
    expect(find.textContaining('2 şarkı'), findsOneWidget);
  });

  testWidgets('empty later list explains how to fill it', (tester) async {
    final api = await _api((r) async => _json({'items': []}));
    await tester.pumpWidget(MaterialApp(home: LaterScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.textContaining('sağa kaydırınca'), findsOneWidget);
  });

  testWidgets('search debounces, shows results and opens the track page', (tester) async {
    final queries = <String>[];
    final api = await _api((r) async {
      if (r.url.path == '/search') {
        queries.add(r.url.queryParameters['q']!);
        return _json({
          'items': [
            {'track': 7, 'title': 'Kuzu Kuzu', 'artists': ['Tarkan'], 'image': null}
          ]
        });
      }
      if (r.url.path == '/tracks/7/comments') {
        return _json({
          'track': {'track': 7, 'title': 'Kuzu Kuzu', 'artists': ['Tarkan'], 'image': null},
          'items': []
        });
      }
      return _json({});
    });
    await tester.pumpWidget(MaterialApp(home: SearchScreen(api: api)));
    await tester.enterText(find.byKey(const ValueKey('search-field')), 'ta');
    await tester.enterText(find.byKey(const ValueKey('search-field')), 'tark');
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pumpAndSettle();
    expect(queries, ['tark']); // ara yazımlar sunucuya gitmez
    expect(find.text('Kuzu Kuzu'), findsOneWidget);

    await tester.tap(find.text('Kuzu Kuzu'));
    await tester.pumpAndSettle();
    expect(find.text('Henüz yorum yok. İlk yorumu sen yaz.'), findsOneWidget);
    expect(find.byKey(const ValueKey('track-open-spotify')), findsOneWidget);
  });

  testWidgets('track page posts a comment and lists own comments with menu', (tester) async {
    final posted = <String>[];
    var comments = <Map<String, Object?>>[];
    final api = await _api((r) async {
      if (r.method == 'POST' && r.url.path == '/tracks/7/comments') {
        final body = (jsonDecode(r.body) as Map)['body'] as String;
        posted.add(body);
        comments = [
          {
            'id': 1, 'author': 'Tını #ab12', 'body': body, 'mine': true,
            'created_at': '2026-11-05T10:00:00+00:00', 'edited_at': null,
          }
        ];
        return _json({}, 201);
      }
      if (r.url.path == '/tracks/7/comments') {
        return _json({
          'track': {'track': 7, 'title': 'Kuzu Kuzu', 'artists': ['Tarkan'], 'image': null},
          'items': comments,
        });
      }
      return _json({});
    });
    await tester.pumpWidget(MaterialApp(
        home: TrackScreen(api: api, card: TrackCard(7, 'Kuzu Kuzu', ['Tarkan']))));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('comment-field')), '  Efsane  ');
    await tester.tap(find.byKey(const ValueKey('comment-send')));
    await tester.pumpAndSettle();
    expect(posted, ['Efsane']);
    expect(find.text('Efsane'), findsOneWidget);
    expect(find.textContaining('Sen · 05.11.2026'), findsOneWidget);
    expect(find.byType(PopupMenuButton<String>), findsOneWidget);
  });

  testWidgets('tapping a later row votes only that track and drops it from the list',
      (tester) async {
    final calls = <String>[];
    final api = await _api((r) async {
      calls.add('${r.method} ${r.url.path}');
      if (r.method == 'GET' && r.url.path == '/later') {
        return _json({
          'items': [
            {'track': 1, 'title': 'Şarkı Bir', 'artists': ['A'], 'image': null, 'liked': false},
            {'track': 2, 'title': 'Şarkı İki', 'artists': ['B'], 'image': null, 'liked': false},
          ]
        });
      }
      if (r.method == 'POST' && r.url.path == '/votes') {
        expect(jsonDecode(r.body), {'track': 1, 'vote': 5});
        return _json({}, 201);
      }
      return r.method == 'DELETE' ? http.Response('', 204) : _json({});
    });
    await tester.pumpWidget(MaterialApp(home: LaterScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Şarkı Bir'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('vote-5')));
    await tester.pumpAndSettle();

    expect(calls, containsAll(['POST /votes', 'DELETE /later/1']));
    expect(find.text('Şarkı Bir'), findsNothing);
    expect(find.text('Şarkı İki'), findsOneWidget);
    expect(find.textContaining('Oylandı'), findsOneWidget);
  });

  testWidgets('heart toggles a like on and off without voting', (tester) async {
    final calls = <String>[];
    final api = await _api((r) async {
      calls.add('${r.method} ${r.url.path}');
      if (r.method == 'GET' && r.url.path == '/later') {
        return _json({
          'items': [
            {'track': 7, 'title': 'Kalpli', 'artists': ['A'], 'image': null, 'liked': false},
          ]
        });
      }
      return r.method == 'DELETE' ? http.Response('', 204) : _json({}, 201);
    });
    await tester.pumpWidget(MaterialApp(home: LaterScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.favorite_rounded), findsNothing);

    await tester.tap(find.byKey(const ValueKey('like-7')));
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.favorite_rounded), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('like-7')));
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.favorite_rounded), findsNothing);

    expect(calls, containsAllInOrder(['POST /likes', 'DELETE /likes/7']));
    expect(calls, isNot(contains('POST /votes')));
  });

  testWidgets('likes screen lists liked tracks and unliking removes the row', (tester) async {
    final api = await _api((r) async {
      if (r.method == 'GET' && r.url.path == '/likes') {
        return _json({
          'items': [
            {'track': 3, 'title': 'Sevilen', 'artists': ['A'], 'image': null, 'liked': true},
          ]
        });
      }
      return r.method == 'DELETE' ? http.Response('', 204) : _json({});
    });
    await tester.pumpWidget(MaterialApp(home: LaterScreen(api: api, likes: true)));
    await tester.pumpAndSettle();
    expect(find.text('Beğendiklerim'), findsOneWidget);
    expect(find.text('Sevilen'), findsOneWidget);
    expect(find.byIcon(Icons.favorite_rounded), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('like-3')));
    await tester.pumpAndSettle();
    expect(find.text('Sevilen'), findsNothing);
  });
}
