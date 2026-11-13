import 'dart:io';

import 'package:flutter/painting.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

/// Profil fotoğrafı: yalnızca cihazda, uygulama klasöründe tek dosya olarak durur.
/// Çıkışta ve hesap silinirken silinir. Eklenti yoksa (testler) sessizce boş döner.
abstract final class ProfilePhotoStore {
  static const _fileName = 'profile_photo.jpg';

  static Future<File> _file() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/$_fileName');
  }

  static Future<File?> load() async {
    try {
      final f = await _file();
      return await f.exists() ? f : null;
    } catch (_) {
      return null;
    }
  }

  /// Galeriden ya da kameradan bir kare seçer, 512 px'e küçültüp kaydeder.
  /// İptal edilirse ya da hata olursa null döner.
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

  static Future<void> clear() async {
    try {
      final f = await _file();
      if (await f.exists()) await f.delete();
    } catch (_) {}
  }
}
