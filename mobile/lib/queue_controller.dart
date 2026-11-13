import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';

import 'api.dart';

/// Kalan kart bu sayının altına inince arka planda doldurulur.
const prefetchBelow = 8;

/// Sunucuya `recent` olarak gönderilen son işlenen (oy/atla/sonra) parça sayısı.
const recentHandledCount = 4;

/// `recent` en çok bu kadar kimlik taşır (sunucu `queue_recent_max` ile aynı).
const recentMax = 20;

/// Art arda bu kadar başarısız/boş denemeden sonra vazgeçilir (çevrimdışı hariç).
const maxAttempts = 5;

const backoffCap = Duration(seconds: 30);

/// "Tükendi" ekranında kullanıcı beklemeden, sunucu tarafı doldurma yetişsin diye ara ara
/// sessizce yeniden bakılır (en çok [slowPollMax] kez).
const slowPollEvery = Duration(seconds: 45);
const slowPollMax = 4;

/// Kütüphane sessiz yenileme aralığı (kuyruk kuruyorsa ve parçaların bilgisi eskiyse).
const autoRefreshEvery = Duration(minutes: 10);

/// Kullanıcının gördüğü durum (ekran yalnızca bunu çizer).
enum QueueStatus { ready, filling, waking, offline, exhausted, failed }

/// 1, 2, 4, … sn; en çok [backoffCap]; ±%20 jitter. `attempt` 0'dan başlar.
Duration backoffFor(int attempt, math.Random rng) {
  final base = math.min(backoffCap.inMilliseconds, 1000 * (1 << math.min(attempt, 10)));
  final jittered = (base * (0.8 + 0.4 * rng.nextDouble())).round();
  return Duration(milliseconds: math.min(jittered, backoffCap.inMilliseconds));
}

/// Denetleyicinin sunucudan ihtiyacı olan en küçük yüzey (testte sahtelenir).
abstract class QueueBackend {
  Future<VoteQueue> voteQueue({required int seed, required List<int> recent});
  Future<bool> health();
  Future<void> importLibrary();
}

class ApiQueueBackend implements QueueBackend {
  ApiQueueBackend(this._api);
  final Api _api;

  @override
  Future<VoteQueue> voteQueue({required int seed, required List<int> recent}) =>
      _api.voteQueue(seed: seed, recent: recent);

  @override
  Future<bool> health() => _api.health();

  @override
  Future<void> importLibrary() async {
    await _api.importLibrary();
  }
}

/// Oylama kuyruğunun tek sahibi: kartlar, tek uçuşlu doldurma, yeniden kontrol, geri çekilme.
///
/// Ekran `pop`/`putBack` ile kart tüketir; doldurma kendiliğinden tetiklenir. Hatada kartlar
/// varken sessizce yeniden dener; kartlar bittiyse duruma göre "uyanıyor", "çevrimdışı",
/// "tükendi" veya "hata" gösterilir.
class QueueController extends ChangeNotifier {
  QueueController(
    this._backend, {
    int? seed,
    math.Random? random,
    DateTime Function()? now,
    Future<void> Function(Duration)? delay,
    this.onUnauthorized,
    Duration slowPoll = slowPollEvery,
  })  : _slowEvery = slowPoll,
        _seed = seed ?? DateTime.now().millisecondsSinceEpoch % 100000,
        _rng = random ?? math.Random(),
        _now = now ?? DateTime.now,
        // ignore: prefer_initializing_formals
        _delay = delay;


  final QueueBackend _backend;
  final math.Random _rng;
  final DateTime Function() _now;
  final Future<void> Function(Duration)? _delay; // testte sahtelenir; yoksa iptal edilebilir Timer
  final void Function()? onUnauthorized;
  final Duration _slowEvery;
  Timer? _slowTimer;
  int _slowPolls = 0;

  final List<QueueItem> _cards = [];
  final Set<int> _handled = {}; // oylanan/atlanan/sonra'ya eklenen (yanıtlardan süzülür)
  final List<int> _recentHandled = []; // son işlenenler, eskiden yeniye
  int _seed;
  int _attempts = 0;
  int _consumed = 0; // uçuş sırasında tüketilen kart sayısı (yeniden kontrol için)
  int _stale = 0;
  bool _gaveUp = false;
  bool _disposed = false;
  DateTime? _lastAutoRefresh;
  Future<void>? _flight;
  Completer<void>? _kick;
  Timer? _timer;
  QueueStatus _status = QueueStatus.filling;
  String? _message;

  List<QueueItem> get cards => List.unmodifiable(_cards);
  QueueItem? get current => _cards.isEmpty ? null : _cards.first;
  QueueStatus get status => _status;
  String? get message => _message;
  int get stale => _stale;
  bool get inFlight => _flight != null;

  /// Sunucunun bildiği "istemcide zaten var" listesi: son işlenenler + bekleyen kartlar.
  List<int> recent() {
    final all = [..._recentHandled, ..._cards.map((c) => c.track)];
    return all.length <= recentMax ? all : all.sublist(all.length - recentMax);
  }

  /// İlk doldurma (ekran açılışı). Uçuş bitince döner.
  Future<void> start() {
    _slowPolls = 0;
    _attempts = 0;
    _gaveUp = false;
    return _run();
  }

  /// Üstteki kartı alır (oylama/atlama/sonra) ve gerekirse doldurmayı başlatır.
  QueueItem? pop() {
    if (_cards.isEmpty) return null;
    final item = _cards.removeAt(0);
    _handled.add(item.track);
    _recentHandled.add(item.track);
    if (_recentHandled.length > recentHandledCount) _recentHandled.removeAt(0);
    _consumed++;
    _gaveUp = false;
    _attempts = 0;
    _notify();
    _pump();
    return item;
  }

  /// Kayıt başarısızsa veya geri alınırsa kart en üste döner.
  void putBack(QueueItem item) {
    _handled.remove(item.track);
    _recentHandled.remove(item.track);
    if (_cards.every((c) => c.track != item.track)) _cards.insert(0, item);
    _notify();
  }

  /// "Yeniden dene": yalnızca doldurmayı yeniden çalıştırır.
  Future<void> retry() {
    _slowPolls = 0;
    _attempts = 0;
    _gaveUp = false;
    _message = null;
    if (_cards.isEmpty) _set(QueueStatus.filling);
    _wake();
    return _run();
  }

  /// "Kütüphaneyi yenile": aktarımı çalıştırır, ardından doldurur.
  Future<void> refreshLibrary() async {
    _slowPolls = 0;
    _attempts = 0;
    _gaveUp = false;
    if (_cards.isEmpty) _set(QueueStatus.filling);
    try {
      await _backend.importLibrary();
    } on ApiException catch (e) {
      if (e.status == 401) {
        onUnauthorized?.call();
        return;
      }
      _fail(e.message);
      return;
    } catch (_) {
      _fail('Sunucuya ulaşılamadı');
      return;
    }
    await _run();
  }

  void _pump() {
    if (!_gaveUp && _cards.length < prefetchBelow) unawaited(_run());
  }

  Future<void> _run() {
    if (_disposed) return Future.value();
    return _flight ??= _loop().whenComplete(() {
      _flight = null;
    });
  }

  Future<void> _loop() async {
    var again = true;
    while (again && !_disposed) {
      again = await _step();
    }
    if (!_disposed && _cards.isNotEmpty && _status != QueueStatus.ready) {
      _set(QueueStatus.ready);
    }
  }

  /// Bir deneme. Döndürdüğü değer: döngü sürsün mü.
  Future<bool> _step() async {
    _consumed = 0;
    if (_cards.isEmpty &&
        _status != QueueStatus.waking &&
        _status != QueueStatus.offline &&
        _status != QueueStatus.exhausted) {
      _set(QueueStatus.filling);
    }
    try {
      final added = await _fetch();
      if (_disposed) return false;
      if (added > 0) {
        _attempts = 0;
        _slowPolls = 0;
        _gaveUp = false;
        _message = null;
        _set(QueueStatus.ready);
        // Uçuş sırasında kartlar tüketildiyse ve ihtiyaç sürüyorsa bir kez daha; kart kalmadıysa
        // döngü durmaz (aksi halde ekran "hazır" ama kartsız takılırdı).
        return _cards.isEmpty || (_consumed > 0 && _cards.length < prefetchBelow);
      }
      _attempts++;
      if (_cards.isNotEmpty) {
        _set(QueueStatus.ready);
        _gaveUp = _attempts >= maxAttempts;
        if (_gaveUp) return false;
        await _sleep(backoffFor(_attempts - 1, _rng));
        return !_disposed && _cards.length < prefetchBelow;
      }
      if (_attempts >= maxAttempts) {
        _gaveUp = true;
        _set(QueueStatus.exhausted);
        _scheduleSlowPoll();
        return false;
      }
      await _sleep(backoffFor(_attempts - 1, _rng));
      return true;
    } on ApiException catch (e) {
      if (e.status == 401) {
        onUnauthorized?.call();
        return false;
      }
      return _onError(e);
    } catch (_) {
      return _onError(ApiException(0, 'Sunucuya ulaşılamadı', kind: ApiFailure.offline));
    }
  }

  Future<bool> _onError(ApiException e) async {
    if (_disposed) return false;
    _attempts++;
    _message = e.message;
    if (_cards.isNotEmpty) {
      // Kartlar varken kullanıcı hata görmez; geri çekilmeyle sessizce denenir.
      if (_attempts >= maxAttempts) {
        _gaveUp = true;
        return false;
      }
      await _sleep(backoffFor(_attempts - 1, _rng));
      return !_disposed && _cards.length < prefetchBelow;
    }
    if (e.kind == ApiFailure.offline) {
      _set(QueueStatus.offline); // ağ dönene kadar sınırsız (geri çekilmeli) dene
      await _sleep(backoffFor(math.min(_attempts - 1, 5), _rng));
      return true;
    }
    if (_attempts >= maxAttempts) {
      _gaveUp = true;
      _fail(e.message);
      return false;
    }
    if (e.kind == ApiFailure.timeout || e.kind == ApiFailure.server) {
      _set(QueueStatus.waking); // Render soğuk başlangıç: önce ısıt
      try {
        await _backend.health();
      } catch (_) {
        await _sleep(backoffFor(_attempts - 1, _rng));
      }
    } else {
      await _sleep(backoffFor(_attempts - 1, _rng));
    }
    return !_disposed;
  }

  Future<int> _fetch() async {
    var q = await _backend.voteQueue(seed: _seed, recent: recent());
    _seed++;
    // Önbellek TTL'i dolan parçalar kuyruktan düşer; kuyruk kuruyorsa kütüphaneyi sessizce
    // yenile (10 dk'da en çok bir kez; başarısızsa elle düğme kalır).
    final last = _lastAutoRefresh;
    if (q.stale > 0 &&
        _cards.length + q.items.length < prefetchBelow &&
        (last == null || _now().difference(last) > autoRefreshEvery)) {
      _lastAutoRefresh = _now();
      try {
        await _backend.importLibrary();
        q = await _backend.voteQueue(seed: _seed, recent: recent());
      } on ApiException catch (e) {
        if (e.status == 401) rethrow;
      } catch (_) {}
    }
    if (_disposed) return 0;
    _stale = q.stale;
    // Sunucu, oy kaydedilmeden önce başlayan bir istekte az önce işlenen parçayı da dönebilir.
    final seen = {..._cards.map((c) => c.track)};
    var added = 0;
    for (final item in q.items) {
      if (_handled.contains(item.track) || !seen.add(item.track)) continue;
      _cards.add(item);
      added++;
    }
    if (added > 0) _notify();
    return added;
  }

  void _scheduleSlowPoll() {
    _slowTimer?.cancel();
    if (_disposed || _slowPolls >= slowPollMax) return;
    _slowTimer = Timer(_slowEvery, () {
      if (_disposed || _cards.isNotEmpty || _flight != null) return;
      _slowPolls++;
      _attempts = maxAttempts - 1; // tek sessiz deneme; boşsa yine "tükendi"
      _gaveUp = false;
      unawaited(_run());
    });
  }

  Future<void> _sleep(Duration d) {
    final kick = _kick = Completer<void>();
    final injected = _delay;
    if (injected != null) {
      return Future.any([injected(d), kick.future]).whenComplete(() => _kick = null);
    }
    // Ekran kapanınca veya "Yeniden dene"de zamanlayıcı iptal edilir (bekleyen Timer kalmaz).
    _timer = Timer(d, _wake);
    return kick.future.whenComplete(() {
      _timer?.cancel();
      _timer = null;
      _kick = null;
    });
  }

  void _wake() {
    final k = _kick;
    if (k != null && !k.isCompleted) k.complete();
  }

  void _fail(String message) {
    _message = message;
    _set(QueueStatus.failed);
  }

  void _set(QueueStatus s) {
    if (_status == s) return;
    _status = s;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _slowTimer?.cancel();
    _wake();
    super.dispose();
  }
}
