import 'dart:io';

import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter/painting.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

import 'api.dart';

/// Profil fotoğrafı: sunucudaki kopya asıl kayıttır (`/me/photo`), cihazdaki dosya önbellektir.
/// Seçim önce yerele yazılır, sonra yüklenir; yükleme/silme başarısız olursa bir sonraki
/// profil açılışında yeniden denenir. Çıkışta yalnızca yerel kopya silinir (sunucudaki kalır);
/// hesap silinince sunucu zaten hepsini siler. Ağ hataları sessizdir. Eklenti yoksa (testler)
/// sessizce boş döner.
abstract final class ProfilePhotoStore {
  static const _fileName = 'profile_photo.jpg';
  static const _etagName = 'profile_photo.etag';
  static const _pendingName = 'profile_photo.pending';

  /// Yalnızca testler: eklenti yerine bu klasör kullanılır.
  @visibleForTesting
  static Directory? dirOverride;

  static Future<File> _named(String name) async {
    final dir = dirOverride ?? await getApplicationDocumentsDirectory();
    return File('${dir.path}/$name');
  }

  static Future<File> _file() => _named(_fileName);

  static Future<File?> load() async {
    try {
      final f = await _file();
      return await f.exists() ? f : null;
    } catch (_) {
      return null;
    }
  }

  /// Galeriden ya da kameradan bir kare seçer, 512 px'e küçültüp yerele kaydeder.
  /// İptal edilirse ya da hata olursa null döner. Sunucuya yükleme [upload] ile yapılır.
  static Future<File?> pick(ImageSource source) async {
    try {
      final x = await ImagePicker().pickImage(
        source: source,
        maxWidth: 512,
        maxHeight: 512,
        imageQuality: 85,
      );
      if (x == null) return null;
      final target = await _file();
      await File(x.path).copy(target.path);
      // Önbellekteki eski kare yeni dosyayla karışmasın.
      imageCache.evict(FileImage(target));
      return target;
    } catch (_) {
      return null;
    }
  }

  /// Yerel kareyi sunucuya yükler; başarısız olursa "bekleyen yükleme" işaretler.
  static Future<void> upload(Api api) async {
    await _setPending('put');
    await _flushPending(api);
  }

  /// Yerel kopyayı siler ve sunucudakini de kaldırır; başarısızsa bir sonraki açılışta tekrar dener.
  static Future<void> remove(Api api) async {
    await clear();
    await _setPending('delete');
    await _flushPending(api);
  }

  /// Profil açılışında: bekleyen işi bitirir, sonra sunucudaki kareyle yereli eşitler.
  /// Döner: ekranda gösterilecek yerel dosya (yoksa null). Ağ hatasında yereli olduğu gibi bırakır.
  static Future<File?> sync(Api api) async {
    try {
      await _flushPending(api);
      if (await _pending() != null) return await load(); // hâlâ çevrimdışı; yerel hâli göster
      final local = await load();
      final etag = local == null ? null : await _readEtag();
      final r = await api.getPhoto(etag: etag);
      switch (r.state) {
        case PhotoState.notModified:
          return local;
        case PhotoState.gone:
          if (local == null) return null;
          if (etag == null) {
            // Sunucu eşitlemesinden önce seçilmiş yerel kare: sunucuya taşı.
            await upload(api);
            return await load();
          }
          await clear(); // başka cihazdan kaldırılmış
          return null;
        case PhotoState.ok:
          final f = await _file();
          await f.writeAsBytes(r.bytes!, flush: true);
          await (await _named(_etagName)).writeAsString(r.etag!);
          imageCache.evict(FileImage(f));
          return f;
      }
    } catch (_) {
      return await load();
    }
  }

  /// Yalnızca yerel kopyayı (ve eşitleme durumunu) siler; sunucuya dokunmaz.
  static Future<void> clear() async {
    for (final n in [_fileName, _etagName, _pendingName]) {
      try {
        final f = await _named(n);
        if (await f.exists()) await f.delete();
      } catch (_) {}
    }
  }

  static Future<void> _setPending(String op) async {
    try {
      await (await _named(_pendingName)).writeAsString(op);
    } catch (_) {}
  }

  static Future<String?> _pending() async {
    try {
      final f = await _named(_pendingName);
      return await f.exists() ? await f.readAsString() : null;
    } catch (_) {
      return null;
    }
  }

  static Future<String?> _readEtag() async {
    try {
      final f = await _named(_etagName);
      return await f.exists() ? await f.readAsString() : null;
    } catch (_) {
      return null;
    }
  }

  static Future<void> _flushPending(Api api) async {
    final op = await _pending();
    if (op == null) return;
    try {
      if (op == 'put') {
        final f = await load();
        if (f == null) {
          await _clearPending();
          return;
        }
        final etag = await api.putPhoto(await f.readAsBytes());
        await (await _named(_etagName)).writeAsString(etag);
      } else {
        await api.deletePhoto();
      }
      await _clearPending();
    } on ApiException catch (e) {
      // 4xx (413/415/400) tekrar denemekle düzelmez; 401/429/ağ hatası ise sonra denenir.
      if (e.status >= 400 && e.status < 500 && e.status != 401 && e.status != 429) {
        await _clearPending();
      }
    } catch (_) {}
  }

  static Future<void> _clearPending() async {
    try {
      final f = await _named(_pendingName);
      if (await f.exists()) await f.delete();
    } catch (_) {}
  }
}
