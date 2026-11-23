import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:tini/vote_sender.dart';

void main() {
  test('enqueue çağıranı beklemez; işler sırayla çalışır', () async {
    final s = VoteSender();
    final log = <String>[];
    final gate = Completer<void>();

    unawaited(s.enqueue(() async {
      log.add('a:start');
      await gate.future; // yavaş sunucu
      log.add('a:end');
    }));
    unawaited(s.enqueue(() async => log.add('b')));

    // Çağıran hemen döndü; ikinci iş birinciyi geçemez.
    await Future<void>.delayed(Duration.zero);
    expect(log, ['a:start']);
    expect(s.busy, isTrue);
    expect(s.pending, 2);

    gate.complete();
    await s.drain();
    expect(log, ['a:start', 'a:end', 'b']);
    expect(s.busy, isFalse);
  });

  test('bir işin hatası zinciri koparmaz', () async {
    final s = VoteSender();
    var ran = false;
    unawaited(s.enqueue(() async => throw StateError('boom')));
    unawaited(s.enqueue(() async => ran = true));
    await s.drain();
    expect(ran, isTrue);
    expect(s.pending, 0);
  });

  test('değişimde dinleyiciler haberdar edilir; dispose sonrası sessiz', () async {
    final s = VoteSender();
    var n = 0;
    s.addListener(() => n++);
    unawaited(s.enqueue(() async {}));
    await s.drain();
    expect(n, 2); // girdi + bitti
    s.dispose();
  });
}
