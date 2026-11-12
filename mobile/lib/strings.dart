/// Arayüz metinleri: tek Türkçe kaynak. Yeni ekranlar ve bileşenler metni buradan alır.
abstract final class TiniStrings {
  // Oy skalası (1–6), her yerde aynı.
  static const voteN1 = 'Berbat';
  static const voteN2 = 'Kötü';
  static const voteN3 = 'İdare eder';
  static const voteN4 = 'İyi';
  static const voteN5 = 'Çok iyi';
  static const voteN6 = 'Efsane';
  static const voteLabels = [voteN1, voteN2, voteN3, voteN4, voteN5, voteN6];
  static const skip = 'Dinlemedim · Geç';

  // Sekmeler
  static const tabDiscover = 'Keşfet';
  static const tabRate = 'Oyla';
  static const tabLists = 'Listeler';
  static const tabProfile = 'Profil';

  // Kaydetme (listeler çalınmaz, kaydedilir)
  static const saveApple = "Apple Music'e kaydet";
  static const saveSpotify = "Spotify'a kaydet";
  static const saving = 'Kaydediliyor…';
  static const saved = 'Kaydedildi';
  static const connectService = 'Bağla';
}
