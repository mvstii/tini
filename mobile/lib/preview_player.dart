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

/// `unavailable`: kaynakta önizleme yok (kalıcı). `error`: geçici hata (ağ/ses); yeniden denenebilir.
enum PreviewStatus { idle, loading, playing, unavailable, error }

/// Mini oynatıcıda gösterilen çalan parça bilgisi (yalnızca görüntü; çalmayı etkilemez).
class PreviewMeta {
  const PreviewMeta({required this.title, required this.artist, this.image, this.track, this.source});
  final String title;
  final String artist;
  final String? image;

  /// Parça kimliği biliniyorsa mini oynatıcı mevcut oyu gösterir.
  final int? track;
  final String? source;
}

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
  PreviewMeta? _meta;
  int _playId = 0;

  String? get key => _key;
  PreviewStatus get status => _status;
  PreviewMeta? get meta => _meta;

  /// Her çalma başlangıcında artar; ilerleme animasyonunu baştan başlatmak için anahtar.
  int get playId => _playId;
  PreviewStatus statusOf(String key) => _key == key ? _status : PreviewStatus.idle;

  void _set(String? key, PreviewStatus s) {
    if (s == PreviewStatus.playing) _playId++;
    _key = key;
    _status = s;
    if (key == null) _meta = null;
    notifyListeners();
  }

  /// Çalıyorsa durdurur; değilse `resolve` ile URL'yi bulup çalar.
  Future<void> toggle(String key, Future<String?> Function() resolve, {PreviewMeta? meta}) async {
    if (_key == key && _status != PreviewStatus.unavailable && _status != PreviewStatus.error) {
      return stop();
    }
    await backend.stop();
    _meta = meta;
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
      if (_key == key) _set(key, PreviewStatus.error);
    }
  }

  Future<void> stop() async {
    if (_key == null) return;
    _set(null, PreviewStatus.idle);
    await backend.stop();
  }
}
