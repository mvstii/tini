import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';

/// Ses çalma arka ucu; testte sahtesi verilir.
abstract class PreviewBackend {
  /// Çalmayı başlatır; kesit bitince `onDone` çağrılır. Hata olursa fırlatır.
  Future<void> play(String url, VoidCallback onDone);
  Future<void> stop();
}

class JustAudioBackend implements PreviewBackend {
  AudioPlayer? _player;
  StreamSubscription<ProcessingState>? _sub;

  @override
  Future<void> play(String url, VoidCallback onDone) async {
    final p = _player ??= AudioPlayer();
    await _sub?.cancel();
    _sub = p.processingStateStream.listen((s) {
      if (s == ProcessingState.completed) onDone();
    });
    await p.setUrl(url);
    // `play()` kesit bitene kadar dönmez; beklenirse durum "çalıyor"a hiç geçmez.
    unawaited(p.play());
  }

  @override
  Future<void> stop() async => _player?.stop();
}

enum PreviewStatus { idle, loading, playing, unavailable }

/// Aynı anda tek önizleme çalar. Kesitler yalnızca yayın olarak çalınır; dosya saklanmaz.
class PreviewController extends ChangeNotifier {
  PreviewController(this.backend);

  /// Uygulama genelinde paylaşılan örnek; testte `backend` sahteyle değiştirilir.
  static PreviewController instance = PreviewController(JustAudioBackend());

  /// Oylama ekranında kart değişince önizleme kendiliğinden çalsın mı (kullanıcı ayarı).
  static final ValueNotifier<bool> autoplay = ValueNotifier(false);

  final PreviewBackend backend;
  String? _key;
  PreviewStatus _status = PreviewStatus.idle;

  String? get key => _key;
  PreviewStatus statusOf(String key) => _key == key ? _status : PreviewStatus.idle;

  void _set(String? key, PreviewStatus s) {
    _key = key;
    _status = s;
    notifyListeners();
  }

  /// Çalıyorsa durdurur; değilse `resolve` ile URL'yi bulup çalar.
  Future<void> toggle(String key, Future<String?> Function() resolve) async {
    if (_key == key && _status != PreviewStatus.unavailable) return stop();
    await backend.stop();
    _set(key, PreviewStatus.loading);
    try {
      final url = await resolve();
      if (_key != key) return; // bu arada başka bir şey seçildi
      if (url == null) return _set(key, PreviewStatus.unavailable);
      await backend.play(url, () {
        if (_key == key) _set(null, PreviewStatus.idle);
      });
      if (_key == key && _status == PreviewStatus.loading) _set(key, PreviewStatus.playing);
    } catch (_) {
      if (_key == key) _set(key, PreviewStatus.unavailable);
    }
  }

  Future<void> stop() async {
    if (_key == null) return;
    _set(null, PreviewStatus.idle);
    await backend.stop();
  }
}
