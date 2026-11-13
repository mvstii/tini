import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tini/api.dart';
import 'package:tini/profile_photo.dart';

class _Mem extends FlutterSecureStorage {
  final _m = <String, String>{};
  @override
  Future<String?> read({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async => _m[key];
  @override
  Future<void> write({required String key, required String? value, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async {
    if (value != null) _m[key] = value;
  }
  @override
  Future<void> delete({required String key, iOptions, aOptions, lOptions, webOptions, mOptions, wOptions}) async => _m.remove(key);
}

final _jpeg = Uint8List.fromList([0xff, 0xd8, 0xff, 1, 2, 3]);

void main() {
  late Directory dir;

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('tini_photo');
    ProfilePhotoStore.dirOverride = dir;
  });
  tearDown(() async {
    ProfilePhotoStore.dirOverride = null;
    await dir.delete(recursive: true);
  });

  Api api(MockClientHandler h) => Api(client: MockClient(h), storage: _Mem());
  File local() => File('${dir.path}/profile_photo.jpg');
  File sidecar(String n) => File('${dir.path}/$n');

  test('upload sends raw JPEG and stores the returned etag', () async {
    await local().writeAsBytes(_jpeg);
    http.BaseRequest? seen;
    Uint8List? body;
    final a = api((req) async {
      seen = req;
      body = req.bodyBytes;
      return http.Response(jsonEncode({'etag': 'abc'}), 200);
    });
    await ProfilePhotoStore.upload(a);
    expect(seen!.method, 'PUT');
    expect(seen!.url.path, '/me/photo');
    expect(seen!.headers['Content-Type'], 'image/jpeg');
    expect(body, _jpeg);
    expect(await sidecar('profile_photo.etag').readAsString(), 'abc');
    expect(sidecar('profile_photo.pending').existsSync(), isFalse);
  });

  test('failed upload stays pending and is retried on the next sync', () async {
    await local().writeAsBytes(_jpeg);
    var online = false;
    final puts = <String>[];
    final a = api((req) async {
      if (!online) throw const SocketException('offline');
      if (req.method == 'PUT') {
        puts.add('put');
        return http.Response(jsonEncode({'etag': 'e1'}), 200);
      }
      return http.Response('', 304);
    });
    await ProfilePhotoStore.upload(a);
    expect(sidecar('profile_photo.pending').existsSync(), isTrue);
    online = true;
    final f = await ProfilePhotoStore.sync(a);
    expect(puts, ['put']);
    expect(f, isNotNull);
    expect(sidecar('profile_photo.pending').existsSync(), isFalse);
  });

  test('sync downloads the server photo (200) and keeps etag', () async {
    final a = api((req) async {
      expect(req.headers.containsKey('If-None-Match'), isFalse);
      return http.Response.bytes(_jpeg, 200, headers: {'etag': '"v1"'});
    });
    final f = await ProfilePhotoStore.sync(a);
    expect(await f!.readAsBytes(), _jpeg);
    expect(await sidecar('profile_photo.etag').readAsString(), 'v1');
  });

  test('sync sends If-None-Match and keeps local on 304', () async {
    await local().writeAsBytes(_jpeg);
    await sidecar('profile_photo.etag').writeAsString('v1');
    final a = api((req) async {
      expect(req.headers['If-None-Match'], '"v1"');
      return http.Response('', 304);
    });
    final f = await ProfilePhotoStore.sync(a);
    expect(await f!.readAsBytes(), _jpeg);
  });

  test('404 with a known etag removes the local copy (removed elsewhere)', () async {
    await local().writeAsBytes(_jpeg);
    await sidecar('profile_photo.etag').writeAsString('v1');
    final a = api((req) async => http.Response('{"detail":"yok"}', 404));
    expect(await ProfilePhotoStore.sync(a), isNull);
    expect(local().existsSync(), isFalse);
  });

  test('404 with a local photo never uploaded migrates it to the server', () async {
    await local().writeAsBytes(_jpeg);
    var put = false;
    final a = api((req) async {
      if (req.method == 'PUT') {
        put = true;
        return http.Response(jsonEncode({'etag': 'n1'}), 200);
      }
      return http.Response('{"detail":"yok"}', 404);
    });
    final f = await ProfilePhotoStore.sync(a);
    expect(put, isTrue);
    expect(f, isNotNull);
  });

  test('remove deletes locally and on the server; offline failure is retried', () async {
    await local().writeAsBytes(_jpeg);
    var online = false;
    var deletes = 0;
    final a = api((req) async {
      if (!online) throw const SocketException('offline');
      if (req.method == 'DELETE') {
        deletes++;
        return http.Response('', 204);
      }
      return http.Response('{"detail":"yok"}', 404);
    });
    await ProfilePhotoStore.remove(a);
    expect(local().existsSync(), isFalse);
    expect(sidecar('profile_photo.pending').existsSync(), isTrue);
    online = true;
    expect(await ProfilePhotoStore.sync(a), isNull);
    expect(deletes, 1);
    expect(sidecar('profile_photo.pending').existsSync(), isFalse);
  });

  test('server errors during sync are silent and keep the local photo', () async {
    await local().writeAsBytes(_jpeg);
    await sidecar('profile_photo.etag').writeAsString('v1');
    final a = api((req) async => http.Response('boom', 500));
    final f = await ProfilePhotoStore.sync(a);
    expect(f, isNotNull);
    expect(local().existsSync(), isTrue);
  });

  test('rejected upload (413) is not retried forever', () async {
    await local().writeAsBytes(_jpeg);
    final a = api((req) async => http.Response('{"detail":"büyük"}', 413));
    await ProfilePhotoStore.upload(a);
    expect(sidecar('profile_photo.pending').existsSync(), isFalse);
  });

  test('clear (logout) removes only local state', () async {
    await local().writeAsBytes(_jpeg);
    await sidecar('profile_photo.etag').writeAsString('v1');
    await ProfilePhotoStore.clear();
    expect(local().existsSync(), isFalse);
    expect(sidecar('profile_photo.etag').existsSync(), isFalse);
  });
}
