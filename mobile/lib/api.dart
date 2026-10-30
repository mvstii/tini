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

class Reason {
  Reason(this.seedId, this.seedName, this.share, this.isAnchor);
  final int seedId;
  final String seedName;
  final double share;
  final bool isAnchor;
}

class HistoryItem {
  HistoryItem(this.track, this.vote, this.title, this.artists);
  final int track;
  final int vote;
  final String? title;
  final List<String> artists;
}

class ExportResult {
  ExportResult(this.added, this.skipped);
  final int added;
  final int skipped;
}

class ListEntry {
  ListEntry(this.position, this.name, this.title, this.reasons);
  final int position;
  final String name;
  final String? title;
  final List<Reason> reasons;

  /// Faz 4'te tek slot tipi var.
  String get slot => 'keşif';
}

class DiscoveryList {
  DiscoveryList(this.id, this.items);
  final int id;
  final List<ListEntry> items;
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

  /// Oy geçmişi: parça başına güncel oy, yeniden eskiye.
  Future<List<HistoryItem>> voteHistory({int limit = 200}) async {
    final body = await _send('GET', '/votes/history?limit=$limit');
    return (body['items'] as List)
        .map((e) => HistoryItem(e['track'] as int, e['vote'] as int, e['title'] as String?,
            ((e['artists'] as List?) ?? const []).cast<String>()))
        .toList();
  }

  /// Listeyi servise özel çalma listesi olarak yazar; atlanan öğe sayısını döndürür.
  Future<ExportResult> exportList(int listId, {String service = 'spotify'}) async {
    final body = await _send('POST', '/lists/$listId/export/$service');
    return ExportResult(body['added'] as int, (body['skipped'] as List).length);
  }

  Future<DiscoveryList> generateList() async {
    final body = await _send('POST', '/lists/generate');
    return DiscoveryList(
      body['id'] as int,
      (body['items'] as List)
          .map((e) => ListEntry(
                e['position'] as int,
                (e['name'] as String?) ?? '?',
                e['title'] as String?,
                (e['reasons'] as List)
                    .map((r) => Reason(r['seed_id'] as int, (r['seed_name'] as String?) ?? '?',
                        (r['share'] as num).toDouble(), r['is_anchor'] as bool))
                    .toList(),
              ))
          .toList(),
    );
  }

  /// Gerekçe itirazı; yalnızca kayıt (algoritmaya etkisi Faz 5). seedId boşsa tüm gerekçe.
  Future<void> reasonFeedback(int listId, int position, {int? seedId}) => _send(
      'POST', '/lists/$listId/items/$position/feedback', {'kind': 'wrong_reason', 'seed_id': seedId});

  /// Öğeyi servis uygulamasında açan bağlantı (parça bulunamazsa sanatçı araması).
  Future<String> openUrl(int listId, int position) async {
    final body = await _send('GET', '/lists/$listId/items/$position/open');
    return body['url'] as String;
  }

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
