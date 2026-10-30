import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

/// Emülatörde 10.0.2.2 ana makineyi gösterir; gerçek cihaz için
/// `--dart-define=API_BASE=http://<lan-ip>:8000` verilir.
const apiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');

class ApiException implements Exception {
  ApiException(this.status, this.message);
  final int status;
  final String message;
  @override
  String toString() => message;
}

class Connection {
  Connection(this.service, this.externalUserId);
  final String service;
  final String externalUserId;
}

class ImportResult {
  ImportResult(this.imported, this.skipped);
  final int imported;
  final int skipped;
}

class QueueItem {
  QueueItem(this.track, this.title, this.artists);
  final int track;
  final String title;
  final List<String> artists;

  String get artistLine => artists.join(', ');
}

class VoteQueue {
  VoteQueue(this.remaining, this.stale, this.items);
  final int remaining;
  final int stale;
  final List<QueueItem> items;
}

class Api {
  Api({http.Client? client, FlutterSecureStorage? storage})
      : _http = client ?? http.Client(),
        _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'session';
  final http.Client _http;
  final FlutterSecureStorage _storage;
  String? _session;

  bool get loggedIn => _session != null;

  Future<void> restore() async => _session = await _storage.read(key: _key);

  Future<void> register(String email, String password) => _auth('register', email, password);

  Future<void> login(String email, String password) => _auth('login', email, password);

  Future<void> _auth(String path, String email, String password) async {
    final body = await _send('POST', '/auth/$path', {'email': email, 'password': password});
    _session = body['token'] as String;
    await _storage.write(key: _key, value: _session);
  }

  Future<void> logout() async {
    try {
      await _send('POST', '/auth/logout');
    } on ApiException {
      // Sunucu oturumu zaten geçersizse yerel oturum yine de silinir.
    }
    _session = null;
    await _storage.delete(key: _key);
  }

  Future<List<Connection>> connections() async {
    final body = await _send('GET', '/connections');
    return (body['_list'] as List)
        .map((e) => Connection(e['service'] as String, e['external_user_id'] as String))
        .toList();
  }

  Future<String> spotifyAuthorizeUrl() async {
    final body = await _send('POST', '/connect/spotify/start');
    return body['authorize_url'] as String;
  }

  Future<ImportResult> importLibrary() async {
    final body = await _send('POST', '/library/import');
    return ImportResult(body['imported'] as int, body['skipped'] as int);
  }

  Future<VoteQueue> voteQueue({int seed = 0, int? limit}) async {
    final q = {'seed': '$seed', if (limit != null) 'limit': '$limit'};
    final body = await _send('GET', '/votes/queue?${Uri(queryParameters: q).query}');
    return VoteQueue(
      body['remaining'] as int,
      body['stale'] as int,
      (body['items'] as List)
          .map((e) => QueueItem(
              e['track'] as int, e['title'] as String, (e['artists'] as List).cast<String>()))
          .toList(),
    );
  }

  /// Oy silinmez; her çağrı yeni bir olaydır.
  Future<void> castVote(int track, int vote) =>
      _send('POST', '/votes', {'track': track, 'vote': vote});

  Future<int> voteTotal() async {
    final body = await _send('GET', '/votes/history?limit=1');
    return body['total'] as int;
  }

  Future<void> rebuildProfile() => _send('POST', '/profile/rebuild');

  Future<Map<String, dynamic>> _send(String method, String path, [Object? json]) async {
    final req = http.Request(method, Uri.parse('$apiBase$path'));
    if (_session != null) req.headers['Authorization'] = 'Bearer $_session';
    if (json != null) {
      req.headers['Content-Type'] = 'application/json';
      req.body = jsonEncode(json);
    }
    final res = await http.Response.fromStream(await _http.send(req));
    final text = utf8.decode(res.bodyBytes);
    if (res.statusCode >= 400) {
      var message = 'Hata ${res.statusCode}';
      try {
        final d = (jsonDecode(text) as Map)['detail'];
        if (d is String) message = d;
      } catch (_) {}
      if (res.statusCode == 401) {
        _session = null;
        await _storage.delete(key: _key);
      }
      throw ApiException(res.statusCode, message);
    }
    if (text.isEmpty) return {};
    final decoded = jsonDecode(text);
    return decoded is List ? {'_list': decoded} : decoded as Map<String, dynamic>;
  }
}
