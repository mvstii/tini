import 'package:flutter/foundation.dart';

/// Oy yazımlarını arka planda, **sırayla** gönderir (FIFO).
///
/// Kullanıcı bir kartı oylayınca ekran sunucu yanıtını beklemez; yazım bu kuyruğa girer ve
/// sonraki kart hemen oylanabilir. Tek sıralı akış, oyların gönderim sırasını korur (aynı
/// parçanın iki oyu birbirini ezmez) ve tek bir bağlantıyı meşgul tutar. Bir iş hata
/// verse de zincir kopmaz: işler kendi hatalarını yönetir (ör. kartı geri koymak).
class VoteSender extends ChangeNotifier {
  Future<void> _tail = Future.value();
  int _pending = 0;
  bool _disposed = false;

  /// Gönderilmemiş ya da sürmekte olan iş sayısı.
  int get pending => _pending;
  bool get busy => _pending > 0;

  /// [job]'u sıraya ekler; önceki işler bitince çalışır. İşin hatası dışarı sızmaz.
  Future<void> enqueue(Future<void> Function() job) {
    _pending++;
    _notify();
    final run = _tail.then((_) async {
      try {
        await job();
      } catch (_) {
        // İş hatasını kendisi ele alır; zincir kopmasın.
      } finally {
        _pending--;
        _notify();
      }
    });
    _tail = run;
    return run;
  }

  /// Şu ana dek sıraya girmiş tüm işler bitince tamamlanır.
  Future<void> drain() => _tail;

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
