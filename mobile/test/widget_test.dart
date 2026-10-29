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

  testWidgets('rating screen is empty for now', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RatingScreen()));
    expect(find.textContaining('Oylanacak şarkı yok'), findsOneWidget);
  });
}
