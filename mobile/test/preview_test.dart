import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tini/preview_player.dart';

class _Fake implements PreviewBackend {
  final played = <String>[];
  int stops = 0;
  bool fail = false;
  VoidCallback? done;

  @override
  Future<void> play(String url, VoidCallback onDone) async {
    if (fail) throw Exception('boom');
    played.add(url);
    done = onDone;
  }

  @override
  Future<void> stop() async => stops++;
}

void main() {
  test('toggle plays, second toggle stops, only one key plays at a time', () async {
    final b = _Fake();
    final c = PreviewController(b);
    await c.toggle('a', () async => 'u1');
    expect(c.statusOf('a'), PreviewStatus.playing);
    await c.toggle('b', () async => 'u2');
    expect(c.statusOf('a'), PreviewStatus.idle);
    expect(c.statusOf('b'), PreviewStatus.playing);
    await c.toggle('b', () async => 'u2');
    expect(c.statusOf('b'), PreviewStatus.idle);
    expect(b.played, ['u1', 'u2']);
  });

  test('missing url or backend error marks unavailable; finished clip returns to idle', () async {
    final b = _Fake();
    final c = PreviewController(b);
    await c.toggle('a', () async => null);
    expect(c.statusOf('a'), PreviewStatus.unavailable);
    b.fail = true;
    await c.toggle('b', () async => 'u');
    expect(c.statusOf('b'), PreviewStatus.unavailable);
    b.fail = false;
    await c.toggle('c', () async => 'u');
    b.done!();
    expect(c.statusOf('c'), PreviewStatus.idle);
  });
}
