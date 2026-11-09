import 'dart:async';
import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:tini/api.dart';
import 'package:tini/queue_controller.dart';

QueueItem item(int t) => QueueItem(t, 'Parça $t', ['Sanatçı']);

/// Sıradaki yanıtı veren sahte sunucu; her yanıt bir `Completer` ile bekletilebilir.
class FakeBackend implements QueueBackend {
  final List<Future<VoteQueue> Function(List<int> recent)> script = [];
  final List<List<int>> recents = [];
  int calls = 0;
  int healthCalls = 0;
  int imports = 0;
  Future<bool> Function()? healthFn;

  @override
  Future<VoteQueue> voteQueue({required int seed, required List<int> recent}) {
    calls++;
    recents.add(List.of(recent));
    final next = script.isEmpty ? null : script.removeAt(0);
    if (next == null) return Future.value(VoteQueue(0, 0, []));
    return next(recent);
  }

  @override
  Future<bool> health() {
    healthCalls++;
    return healthFn == null ? Future.value(true) : healthFn!();
  }

  @override
  Future<void> importLibrary() async {
    imports++;
  }
}

VoteQueue q(List<int> tracks, {int stale = 0}) =>
    VoteQueue(tracks.length, stale, tracks.map(item).toList());

QueueController make(FakeBackend b, {void Function()? onUnauthorized}) => QueueController(
      b,
      seed: 1,
      random: math.Random(1),
      delay: (_) => Future<void>.value(),
      onUnauthorized: onUnauthorized,
    );

void main() {
  test('backoff 1,2,4... sn ve 30 sn tavan, jitter ±%20', () {
    final rng = math.Random(3);
    for (var a = 0; a < 12; a++) {
      final d = backoffFor(a, rng);
      final base = math.min(30000, 1000 * (1 << a));
      expect(d.inMilliseconds, lessThanOrEqualTo(30000));
      expect(d.inMilliseconds, greaterThanOrEqualTo(math.min((base * 0.8).floor(), 30000)));
    }
  });

  test('soğuk açılış: ilk doldurma kartları getirir, durum hazır', () async {
    final b = FakeBackend()..script.add((_) async => q([1, 2, 3]));
    final c = make(b);
    expect(c.status, QueueStatus.filling);
    await c.start();
    expect(c.status, QueueStatus.ready);
    expect(c.cards.map((e) => e.track), [1, 2, 3]);
  });

  test('yavaş yanıt sırasında art arda oy: kart bitmez, tek uçuş, tüketim sonrası yeniden kontrol',
      () async {
    final b = FakeBackend();
    final slow = Completer<VoteQueue>();
    b.script
      ..add((_) async => q([1, 2, 3, 4, 5, 6, 7])) // başlangıç: 7 kart (< 8)
      ..add((_) => slow.future) // yavaş doldurma
      ..add((_) async => q([20, 21, 22]));
    final c = make(b);
    await c.start();
    expect(c.cards.length, 7);
    // Art arda oy: her pop doldurmayı tetikler ama uçuş tek kalır.
    final first = c.pop();
    c.pop();
    c.pop();
    expect(first!.track, 1);
    expect(b.calls, 2, reason: 'başlangıç + tek uçuş');
    expect(c.cards.length, 4, reason: 'kartlar yanıt beklerken bitmedi');
    slow.complete(q([10, 11, 12]));
    await c.start(); // uçuşun bitmesini bekle
    // Uçuş sırasında 3 kart tüketildi ve ihtiyaç sürdüğü için ikinci istek atıldı.
    expect(b.calls, 3);
    expect(c.cards.map((e) => e.track), [4, 5, 6, 7, 10, 11, 12, 20, 21, 22]);
  });

  test('çakışan yanıt: yinelenen veya az önce oylanan kart eklenmez', () async {
    final b = FakeBackend()
      ..script.add((_) async => q([1, 2, 3]))
      ..script.add((_) async => q([1, 2, 3, 4])); // 1 oylandı, 2-3 kartlarda
    final c = make(b);
    await c.start();
    c.pop(); // 1 işlendi
    await c.start();
    expect(c.cards.map((e) => e.track), [2, 3, 4]);
    expect(b.recents.last, [1, 2, 3], reason: 'recent = son işlenen + bekleyen kartlar');
  });

  test('recent: son 4 işlenen + bekleyen kartlar (eskiden yeniye), en çok 20', () async {
    final b = FakeBackend()..script.add((_) async => q(List.generate(12, (i) => i + 1)));
    final c = make(b);
    await c.start();
    for (var i = 0; i < 6; i++) {
      c.pop();
    }
    expect(c.recent(), [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);

    final big = FakeBackend()..script.add((_) async => q(List.generate(30, (i) => i + 1)));
    final c2 = make(big);
    await c2.start();
    expect(c2.recent().length, 20);
    expect(c2.recent().last, 30, reason: 'kırpma baştan: en yeni parçalar kalır');
  });

  test('zaman aşımında kartlar varken sessiz deneme: durum hazır kalır', () async {
    final b = FakeBackend()
      ..script.add((_) async => q([1, 2, 3]))
      ..script.add((_) => Future.error(ApiException(0, 'zaman', kind: ApiFailure.timeout)))
      ..script.add((_) async => q([4, 5]));
    final c = make(b);
    final seen = <QueueStatus>[];
    c.addListener(() => seen.add(c.status));
    await c.start();
    c.pop(); // doldurmayı tetikler (2 kart < 8)
    await c.start();
    expect(seen.contains(QueueStatus.failed), isFalse);
    expect(seen.contains(QueueStatus.waking), isFalse);
    expect(c.status, QueueStatus.ready);
    expect(c.cards.map((e) => e.track), containsAll([4, 5]));
  });

  test('kartlar bittiyse zaman aşımı: uyanıyor, ısınma, sonra hazır', () async {
    final b = FakeBackend()
      ..script.add((_) => Future.error(ApiException(0, 'zaman', kind: ApiFailure.timeout)))
      ..script.add((_) async => q([1, 2]));
    final c = make(b);
    final seen = <QueueStatus>[];
    c.addListener(() => seen.add(c.status));
    await c.start();
    expect(seen, contains(QueueStatus.waking));
    expect(b.healthCalls, 1);
    expect(c.status, QueueStatus.ready);
    expect(c.cards.length, 2);
  });

  test('çevrimdışı: bekler, ağ dönünce kendiliğinden dolar', () async {
    final b = FakeBackend();
    for (var i = 0; i < 7; i++) {
      b.script.add((_) => Future.error(ApiException(0, 'yok', kind: ApiFailure.offline)));
    }
    b.script.add((_) async => q([1]));
    final c = make(b);
    final seen = <QueueStatus>[];
    c.addListener(() => seen.add(c.status));
    await c.start();
    expect(seen, contains(QueueStatus.offline));
    expect(c.status, QueueStatus.ready, reason: 'maxAttempts aşılsa da çevrimdışıyken vazgeçmez');
    expect(c.cards.map((e) => e.track), [1]);
  });

  test('kartlar bitti ve denemeler tükendi: hata durumu; Yeniden dene yalnız doldurur', () async {
    final b = FakeBackend();
    for (var i = 0; i < maxAttempts; i++) {
      b.script.add((_) => Future.error(ApiException(500, 'Hata 500')));
    }
    final c = make(b);
    await c.start();
    expect(c.status, QueueStatus.failed);
    expect(c.message, 'Hata 500');
    b.script.add((_) async => q([9]));
    await c.retry();
    expect(c.status, QueueStatus.ready);
    expect(b.imports, 0, reason: 'yeniden dene kütüphaneyi aktarmaz');
  });

  test('boş yanıtlar tükenince "tükendi"; kütüphaneyi yenile aktarır ve doldurur', () async {
    final b = FakeBackend(); // varsayılan: boş yanıt
    final c = make(b);
    await c.start();
    expect(c.status, QueueStatus.exhausted);
    b.script.add((_) async => q([5, 6]));
    await c.refreshLibrary();
    expect(b.imports, 1);
    expect(c.status, QueueStatus.ready);
    expect(c.cards.length, 2);
  });

  test('401: çıkış geri çağrısı tetiklenir ve döngü durur', () async {
    var out = 0;
    final b = FakeBackend()..script.add((_) => Future.error(ApiException(401, 'oturum')));
    final c = make(b, onUnauthorized: () => out++);
    await c.start();
    expect(out, 1);
    expect(b.calls, 1);
  });

  test('putBack: kayıt başarısızsa kart geri gelir ve recent içinde yinelenmez', () async {
    final b = FakeBackend()..script.add((_) async => q([1, 2, 3]));
    final c = make(b);
    await c.start();
    final it = c.pop()!;
    c.putBack(it);
    expect(c.current!.track, 1);
    expect(c.recent().where((t) => t == 1).length, 1);
  });

  test('kütüphane eskidiyse ve kuyruk kuruyorsa sessiz aktarım', () async {
    final b = FakeBackend()
      ..script.add((_) async => q([1], stale: 3))
      ..script.add((_) async => q([1, 2, 3]));
    final c = make(b);
    await c.start();
    expect(b.imports, 1);
    expect(c.cards.length, 3);
  });
}

