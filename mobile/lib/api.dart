import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

/// Emülatörde 10.0.2.2 ana makineyi gösterir. Kapalı test APK'sı tünel adresiyle derlenir:
/// `--dart-define=API_BASE=https://<alan-adı>` (docs/DAGITIM.md).
const apiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');

/// Geri bildirimle sunucuya gönderilir; derlemede `--dart-define=APP_VERSION=...` ile verilir.
const appVersion = String.fromEnvironment('APP_VERSION', defaultValue: '1.0.0');

/// Render ücretsiz katmanı soğuk başlangıçta ~20 sn sürebilir; bundan uzun süren istek hataya çevrilir.
const requestTimeout = Duration(seconds: 45);

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
  QueueItem(this.track, this.title, this.artists, [this.image]);
  final int track;
  final String title;
  final List<String> artists;

  /// Albüm kapağı URL'si (yoksa null); sunucu kullanıcıya özel önbellekten verir.
  final String? image;

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
  ExportResult(this.added, this.skippedNames);
  final int added;
  final List<String> skippedNames;
  int get skipped => skippedNames.length;
}

class DailySong {
  DailySong(
      {required this.listId, required this.entry, required this.artists, this.image, this.track});
  final int listId;

  /// Parça kimliği; yalnızca parçası çözülmüş öğelerde var (yoksa oy verilemez).
  final int? track;
  final ListEntry entry;
  final List<String> artists;
  final String? image;
}

class ListEntry {
  ListEntry(this.position, this.name, this.title, this.reasons,
      {this.release, this.artistId, this.artistImage});
  final int position;

  /// Sanatçı kimliği ve (varsa) önbellekteki portre URL'si; fotoğraf sonradan doldurulabilir.
  final int? artistId;
  final String? artistImage;
  final String name;
  final String? title;
  final List<Reason> reasons;

  /// Yalnızca Taze liste öğelerinde: albüm düzeyinde yayın.
  final ReleaseInfo? release;

  /// Yayın öğeleri "yeni" yuvasıdır; diğerleri keşif.
  String get slot => release != null ? 'yeni' : 'keşif';
}

class ReleaseInfo {
  ReleaseInfo(this.title, this.type, this.released);
  final String title;
  final String type;
  final String released;
}

class NewTrack {
  NewTrack(this.deezerId, this.title, this.artist, this.release, this.released, {this.cover});
  final String? cover;
  final int deezerId;
  final String title;
  final String artist;
  final String release;
  final String released;
}

class NewRelease {
  NewRelease(this.title, this.type, this.released, this.artist, this.follow, {this.cover});
  final String? cover;
  final String title;
  final String type;
  final String released;
  final String artist;
  final String follow; // 'auto' | 'manual'
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

  static const _themeKey = 'theme';

  /// Kayıtlı tema tercihi; yoksa ya da okunamazsa sistemi izler.
  Future<ThemeMode> loadTheme() async {
    try {
      final v = await _storage.read(key: _themeKey);
      return ThemeMode.values.firstWhere((m) => m.name == v, orElse: () => ThemeMode.system);
    } catch (_) {
      return ThemeMode.system;
    }
  }

  Future<void> saveTheme(ThemeMode mode) async {
    try {
      await _storage.write(key: _themeKey, value: mode.name);
    } catch (_) {
      // Tercih saklanamazsa bu oturumda geçerli kalır.
    }
  }

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

  /// Hesabı ve tüm kişisel veriyi siler (parola onayıyla). Yanlış parola 403 döner;
  /// yerel oturum yalnızca silme başarılıysa temizlenir.
  Future<void> deleteAccount(String password) async {
    await _send('DELETE', '/me', {'password': password});
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
              e['track'] as int, e['title'] as String, (e['artists'] as List).cast<String>(),
              e['image'] as String?))
          .toList(),
    );
  }

  /// Oy silinmez; her çağrı yeni bir olaydır.
  Future<void> castVote(int track, int vote) =>
      _send('POST', '/votes', {'track': track, 'vote': vote});

  /// Sola kaydırma: Unheard olayı yazar (silinmez; 3 sunumda oy gelmezse zayıf negatif olur).
  Future<void> markUnheard(int track) => _send('POST', '/votes/unheard', {'track': track});

  Future<int> voteTotal() async {
    final body = await _send('GET', '/votes/history?limit=1');
    return body['total'] as int;
  }

  /// Uygulama içi geri bildirim: kind = bug | idea | other.
  Future<void> sendFeedback(String kind, String screen, String message) => _send('POST', '/feedback',
      {'kind': kind, 'screen': screen, 'app_version': appVersion, 'message': message});

  Future<void> rebuildProfile() => _send('POST', '/profile/rebuild');

  /// Oy geçmişi: parça başına güncel oy, yeniden eskiye.
  Future<List<HistoryItem>> voteHistory({int limit = 200}) async =>
      (await voteSummary(limit: limit)).items;

  /// Toplam güncel oy sayısı + geçmiş (en yeni [limit] parça).
  Future<({int total, List<HistoryItem> items})> voteSummary({int limit = 200}) async {
    final body = await _send('GET', '/votes/history?limit=$limit');
    final items = (body['items'] as List)
        .map((e) => HistoryItem(e['track'] as int, e['vote'] as int, e['title'] as String?,
            ((e['artists'] as List?) ?? const []).cast<String>()))
        .toList();
    return (total: body['total'] as int, items: items);
  }

  /// Listeyi servise özel çalma listesi olarak yazar; atlanan öğe sayısını döndürür.
  Future<ExportResult> exportList(int listId, {String service = 'spotify'}) async {
    final body = await _send('POST', '/lists/$listId/export/$service');
    final skipped = body['skipped'] as List;
    final names = (body['skipped_names'] as List?)?.cast<String>() ?? const <String>[];
    // Eski sunucu adları göndermezse sayı korunur.
    return ExportResult(
      body['added'] as int,
      names.length == skipped.length ? names : List<String>.filled(skipped.length, ''),
    );
  }

  /// Sanatçı portreleri (sunucu eksikleri doldurur). `pending` > 0 ise tekrar sorulmalı.
  Future<({Map<int, String?> images, int pending})> artistImages(List<int> ids) async {
    if (ids.isEmpty) return (images: <int, String?>{}, pending: 0);
    final body = await _send('GET', '/artists/images?ids=${ids.join(',')}');
    final raw = (body['images'] as Map).cast<String, dynamic>();
    return (
      images: {for (final e in raw.entries) int.parse(e.key): e.value as String?},
      pending: body['pending'] as int,
    );
  }

  /// 30 sn'lik önizleme URL'si (sunucu istek anında çözer, saklamaz); bulunamazsa null.
  Future<String?> previewUrl({int? artistId, int? trackId, int? deezerId}) async {
    final q = [
      if (artistId != null) 'artist_id=$artistId',
      if (trackId != null) 'track_id=$trackId',
      if (deezerId != null) 'deezer_id=$deezerId',
    ].join('&');
    final body = await _send('GET', '/preview?$q');
    return body['url'] as String?;
  }

  Future<DiscoveryList> generateList() => _generate('/lists/generate');

  /// Haftalık Taze liste: takip edilen sanatçıların yeni yayınları (albüm düzeyi).
  Future<DiscoveryList> generateFresh() => _generate('/lists/generate-fresh');

  /// "Yeni" akışı: takip edilen sanatçıların son yayınları, yeniden eskiye.
  Future<List<NewRelease>> newReleases() async {
    final body = await _send('GET', '/releases/new');
    return (body['items'] as List)
        .map((e) => NewRelease(e['title'] as String, e['type'] as String,
            e['released'] as String, (e['artist'] as String?) ?? '?', e['follow'] as String,
            cover: e['cover'] as String?))
        .toList();
  }

  /// "Bu hafta çıkanlar": takip edilen sanatçıların son günlerdeki yayınları, parça parça.
  Future<List<NewTrack>> newTracks() async {
    final body = await _send('GET', '/releases/new-tracks');
    return (body['items'] as List)
        .map((e) => NewTrack(e['deezer_id'] as int, e['title'] as String,
            (e['artist'] as String?) ?? '?', e['release'] as String, e['released'] as String,
            cover: e['cover'] as String?))
        .toList();
  }

  Future<DiscoveryList> _generate(String path) async {
    final body = await _send('POST', path);
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
                artistId: e['artist_id'] as int?,
                artistImage: e['artist_image'] as String?,
                release: e['release'] == null
                    ? null
                    : ReleaseInfo(e['release']['title'] as String, e['release']['type'] as String,
                        e['release']['released'] as String),
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

  /// Günün şarkısı; profil/liste yoksa (404, 409) null. Başlık ve kapak servis bağlı değilse boş gelir.
  Future<DailySong?> dailySong() async {
    final Map<String, dynamic> body;
    try {
      body = await _send('GET', '/recommend/daily');
    } on ApiException catch (e) {
      if (e.status == 404 || e.status == 409) return null;
      rethrow;
    }
    return DailySong(
      listId: body['list_id'] as int,
      track: body['track'] as int?,
      entry: ListEntry(
        body['position'] as int,
        (body['name'] as String?) ?? '?',
        body['title'] as String?,
        (body['reasons'] as List)
            .map((r) => Reason(r['seed_id'] as int, (r['seed_name'] as String?) ?? '?',
                (r['share'] as num).toDouble(), r['is_anchor'] as bool))
            .toList(),
        artistId: body['artist_id'] as int?,
        artistImage: body['artist_image'] as String?,
      ),
      artists: (body['artists'] as List?)?.cast<String>() ?? const <String>[],
      image: body['image'] as String?,
    );
  }

  Future<Map<String, dynamic>> _send(String method, String path, [Object? json]) async {
    final req = http.Request(method, Uri.parse('$apiBase$path'));
    if (_session != null) req.headers['Authorization'] = 'Bearer $_session';
    if (json != null) {
      req.headers['Content-Type'] = 'application/json';
      req.body = jsonEncode(json);
    }
    final http.Response res;
    try {
      res = await (() async => http.Response.fromStream(await _http.send(req)))()
          .timeout(requestTimeout);
    } on TimeoutException {
      throw ApiException(0, 'Sunucu yanıt vermedi (uyanıyor olabilir), biraz sonra tekrar dene');
    }
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
