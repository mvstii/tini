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

  // Bileşenler
  static const unheardAdd = 'keşif havuzuna ekle';
  static const unheardAdded = 'keşif havuzunda';
  static const newBadge = 'YENİ';
  static const predictionPrefix = 'Tahmin';
  static const slotFit = 'Sana uyan';
  static const slotUnheard = 'Dinlemediğin';
  static const slotExplore = 'Keşif';
  static const slotFresh = 'Taze';
  static String fitPercent(int p) => '%$p';
  static String voteSemantics(int v, String label) => '$v, $label';
  static const play = 'Çal';
  static const pause = 'Durdur';
  static const close = 'Kapat';
  static String pendingVotes(int n) => '$n bekleyen oy';
  static String tabSemantics(String label, int badge) => badge > 0 ? '$label, $badge bekleyen' : label;
  static const clipSemantics = '30 sn önizleme';
  static String shareOfTaste(int p) => "zevkinin %$p'i";
  static const votesChartTitle = 'Oy dağılımı';
  static const serviceNotConnected = 'bağlı değil';
  static const connectApple = "Apple Music'i bağla";
  static const connectSpotify = "Spotify'ı bağla";
  static const fitSuffix = 'uyum';
  static const anchorUnit = 'çapa';
  static const gaveSuffix = 'verdin';
  static String gaveVote(int v) => '$v $gaveSuffix';
  static String commonTagCount(String tag, int n) => '$tag ×$n';
}
