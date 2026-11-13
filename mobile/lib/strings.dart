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
  static const previewUnavailable = 'Bu şarkı için önizleme yok';
  static String pendingVotesCard(int n) => '$n şarkı oyunu bekliyor';
  static const rate = 'Oyla';
  static const play = 'Çal';
  static const pause = 'Durdur';
  static const close = 'Kapat';
  static String pendingVotes(int n) => '$n bekleyen oy';
  static String tabSemantics(String label, int badge) =>
      badge > 0 ? '$label, $badge bekleyen' : label;
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

  // Keşif listesi ve Gerekçe paneli
  static const listTitle = 'Keşif listesi';
  static const listEmbeddedTitle = 'Sana özel öneriler';
  static String listForYou(int n) => 'Senin için · $n şarkı';
  static const generate = 'Liste üret';
  static const regenerate = 'Yeniden üret';
  static const listEmpty = 'Öneri çıkmadı.';
  static const noProfile = 'Önce oylayıp profilini kur.';
  static const unreachable = 'Sunucuya ulaşılamadı';
  static const retry = 'Yeniden dene';
  static const noAnchorReason = 'Bu öneri için çapa gerekçesi hesaplanamadı';
  static String reasonShort(String name, int pct) => 'Benzer: $name %$pct';
  static const whyTitle = 'Neden bu şarkı?';
  static String whySentence(int pct, int n) =>
      'Skorun %$pct oranında ${n == 1 ? 'bu şarkıdan' : 'bu $n şarkıdan'} geliyor';
  static const objectSimilarity = 'Bu benzerlik yanlış';
  static const objectionSaved = 'Geri bildirimin kaydedildi';
  static const openInSpotify = "Spotify'da aç";
  static const connectSpotifyFirst = "Önce Spotify'ı bağla.";
  static const spotifyOpenFailed = 'Spotify açılamadı. Uygulama kurulu mu?';
  static const reconnectSpotify =
      "Spotify'ı (yeniden) bağla; çalma listesi izni gerekebilir.";
  static const appleNotAvailable = 'Apple Music bağlantısı henüz yok';
  static const noPlayableTracks =
      'Bu listedeki öğelerin çalınabilir parçası bulunamadı.';
  // Profil
  static const profileTitle = 'Profil';
  static const settings = 'Bağlantılar ve ayarlar';
  static const you = 'Sen';
  static String levelLabel(int n) => 'Seviye $n';
  static String profileSummary(int votes, int amazing, int unheard) =>
      '$votes oy · $amazing Efsane · $unheard Dinlemedin';
  static const tasteModes = 'Zevk modların';
  static String modeName(int n) => 'Mod $n';
  static const modesEmpty = 'Zevk modların, profilin kurulunca burada görünür.';
  static const yourVotes = 'Oy dağılımın';
  static const calibrationDone =
      '30 oydan sonra puanların kendi ölçeğine göre ayarlanıyor';
  static String calibrationLeft(int n) => '$n oy daha verince ayarlanacak';
  static const avoidZone = 'Kaçınma bölgesi';
  static const avoidHard = 'Sert filtre';
  static const avoidSoft = 'Yumuşak ceza';
  static const avoidEmpty = 'Henüz kaçındığımız bir şey yok.';
  static const avoidHint = 'Öneriler bu sanatçılardan uzak tutulur.';
  static const recentVotes = 'Son oylananlar';
  static const noVotesYet = 'Henüz oy yok.';
  static const myLists = 'Listelerim';
  static const listenLater = 'Sonra dinle';
  static const myLikes = 'Beğendiklerim';
  static const appearance = 'Görünüm';
  static const themeSystem = 'Sistem';
  static const themeLight = 'Açık';
  static const themeDark = 'Koyu';
  static const logout = 'Çıkış';
  static const serverUnreachable = 'Sunucuya ulaşılamadı';
  static String trackFallback(int n) => 'Parça $n';

  static String savedToSpotify(int added, int skipped, String detail) =>
      "Spotify'a kaydedildi: $added parça${skipped > 0 ? ', $skipped öğe atlandı$detail' : ''}";
}
