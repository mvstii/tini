import 'dart:async';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tini/api.dart';

class _Mem extends FlutterSecureStorage {
  _Mem([Map<String, String>? seed]) : _m = {...?seed};
  final Map<String, String> _m;
  bool failRead = false;
  @override
  Future<String?> read({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async {
    if (failRead) throw StateError('keystore bozuk');
    return _m[key];
  }

  @override
  Future<void> write({required String key, required String? value, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async {
    if (value != null) _m[key] = value;
  }

  @override
  Future<void> delete({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async => _m.remove(key);
}

http.Response _ok() => http.Response('{"status":"ok"}', 200);

void main() {
  setUp(() => getRetryDelay = Duration.zero);
  tearDown(() => getRetryDelay = const Duration(seconds: 2));

  test('GET is retried once after a timeout', () async {
    var calls = 0;
    final api = Api(
      client: MockClient((_) async {
        calls++;
        if (calls == 1) throw TimeoutException('uyuyor');
        return _ok();
      }),
      storage: _Mem(),
    );
    await api.health();
    expect(calls, 2);
  });

  test('GET is retried once after 503 and gives up after the second', () async {
    var calls = 0;
    final api = Api(
      client: MockClient((_) async {
        calls++;
        return http.Response('{}', 503);
      }),
      storage: _Mem(),
    );
    await expectLater(api.health(), throwsA(isA<ApiException>()));
    expect(calls, 2);
  });

  test('non-GET requests are never retried', () async {
    var calls = 0;
    final api = Api(
      client: MockClient((_) async {
        calls++;
        throw TimeoutException('uyuyor');
      }),
      storage: _Mem(),
    );
    await expectLater(
      api.deleteAccount('x'),
      throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiFailure.timeout)),
    );
    expect(calls, 1);
  });

  test('queue request is not retried by the transport (controller has its own backoff)', () async {
    var calls = 0;
    final api = Api(
      client: MockClient((_) async {
        calls++;
        return http.Response('{}', 503);
      }),
      storage: _Mem(),
    );
    await expectLater(api.voteQueue(), throwsA(isA<ApiException>()));
    expect(calls, 1);
  });

  test('restore survives a broken keystore and starts logged out', () async {
    final mem = _Mem({'session': 'tok'})..failRead = true;
    final api = Api(client: MockClient((_) async => _ok()), storage: mem);
    await api.restore();
    expect(api.loggedIn, isFalse);
  });

  test('401 clears the session and fires onUnauthorized once', () async {
    final api = Api(
      client: MockClient((_) async => http.Response('{"detail":"Oturum geçersiz"}', 401)),
      storage: _Mem({'session': 'tok'}),
    );
    await api.restore();
    expect(api.loggedIn, isTrue);
    var fired = 0;
    api.onUnauthorized = () => fired++;
    await expectLater(api.health(), throwsA(isA<ApiException>()));
    expect(api.loggedIn, isFalse);
    expect(fired, 1);
  });

  test('warmUp swallows errors', () async {
    final api = Api(
      client: MockClient((_) async => throw const FormatException('x')),
      storage: _Mem(),
    );
    await api.warmUp();
  });

  test('release builds reject a non-https API base', () {
    expect(apiBaseProblem('http://10.0.2.2:8000', release: true), isNotNull);
    expect(apiBaseProblem('https://tini-74he.onrender.com', release: true), isNull);
    expect(apiBaseProblem('http://10.0.2.2:8000', release: false), isNull);
  });
}
