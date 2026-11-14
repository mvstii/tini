import 'package:flutter/foundation.dart';

import 'api.dart';

/// Oylama ekranının debug amaçlı zorlanan durumu (yalnızca `kDebugMode`).
enum UiState { normal, loading, queueFetching, error }

/// Başlangıç turu uzunluğu; bu kadar oydan sonra profil kurulabilir, öneriler açılır.
const tourVotes = 30;

/// Profil son kurulduğundan beri bu kadar oy verilince keşif listesi bayatlar; Öneriler
/// sekmesi açılınca profil yeniden kurulup liste yenilenir.
const listRefreshVotes = 10;

/// Oylama, Öneriler ve Profil ekranlarının paylaştığı tek durum. Sunucu tek gerçek
/// kaynaktır: [load] onu okur, oy/geri alma sonrası yerel kopya sunucunun yapacağıyla aynı
/// şekilde güncellenir (oy silinmez; aynı parçaya yeni oy öncekinin yerini alır).
class AppState extends ChangeNotifier {
  AppState(this.api);
  final Api api;

  int _serverTotal = 0;
  int _debugMin = 0;
  int unheardSession = 0;
  bool profileBuilt = false;
  bool loaded = false;
  UiState forced = UiState.normal;

  /// Profil son kurulduğundan beri verilen oy sayısı (kurulunca sıfırlanır).
  int votesSinceRebuild = 0;

  /// Öneriler sekmesi bu oturumda en az bir kez liste üretti mi (ilk üretimi ayrı akış yürütür).
  bool listGenerated = false;

  /// Profil, listenin üretildiği andan sonra yeniden kuruldu: liste profilin gerisinde.
  bool listBehind = false;

  /// Her profil kurulumunda artar; Profil sekmesi sunucudaki yeni profili bundan anlar.
  int profileRevision = 0;

  bool get profileNeedsRebuild => votesSinceRebuild >= listRefreshVotes;

  /// Öneriler sekmesindeki liste yenilenmeli (rozet bunu gösterir).
  bool get listNeedsRefresh =>
      unlocked && listGenerated && (profileNeedsRebuild || listBehind);

  /// Parça kimliği → güncel oy (sunucunun döndürdüğü son 200 parça + bu oturumdakiler).
  final Map<int, int> votes = {};

  /// Yeniden eskiye son oylananlar.
  final List<HistoryItem> recent = [];

  /// Profil ekranı için: debug "30 oy" düğmesi gerçek sayıyı değiştirmez, yalnızca kilidi açar.
  int get total => _serverTotal < _debugMin ? _debugMin : _serverTotal;
  bool get unlocked => total >= tourVotes;
  int get level => total ~/ tourVotes + 1;
  int get inLevel => total % tourVotes;

  Map<int, int> get counts {
    final c = {for (var i = 1; i <= 6; i++) i: 0};
    for (final v in votes.values) {
      c[v] = (c[v] ?? 0) + 1;
    }
    return c;
  }

  double? get average => votes.isEmpty ? null : votes.values.reduce((a, b) => a + b) / votes.length;

  Future<void> load() async {
    final s = await api.voteSummary();
    _serverTotal = s.total;
    votes
      ..clear()
      ..addEntries(s.items.map((i) => MapEntry(i.track, i.vote)));
    recent
      ..clear()
      ..addAll(s.items.take(20));
    loaded = true;
    notifyListeners();
  }

  void recordVote(QueueItem item, int vote) {
    if (!votes.containsKey(item.track)) _serverTotal++;
    votesSinceRebuild++;
    votes[item.track] = vote;
    recent.removeWhere((h) => h.track == item.track);
    recent.insert(0, HistoryItem(item.track, vote, item.title, item.artists, item.image));
    if (recent.length > 20) recent.removeLast();
    notifyListeners();
  }

  /// Oylama kuyruğunda bekleyen şarkı sayısı (tab çubuğundaki rozet); Oyla ekranı yazar.
  int pendingVotes = 0;

  void setPendingVotes(int n) {
    if (n == pendingVotes) return;
    pendingVotes = n;
    notifyListeners();
  }

  void recordUnheard() {
    unheardSession++;
    notifyListeners();
  }

  /// Profil ekranından oy değişikliği (sunucuya yazıldıktan sonra çağrılır).
  void recordChange(HistoryItem h, int vote) {
    votes[h.track] = vote;
    final i = recent.indexWhere((r) => r.track == h.track);
    if (i >= 0) recent[i] = HistoryItem(h.track, vote, h.title, h.artists, h.image);
    notifyListeners();
  }

  void markProfileBuilt() {
    profileBuilt = true;
    votesSinceRebuild = 0;
    listBehind = true;
    profileRevision++;
    notifyListeners();
  }

  /// Öneriler sekmesi güncel profille yeni bir liste üretti.
  void markListGenerated() {
    listGenerated = true;
    listBehind = false;
    notifyListeners();
  }

  void setForced(UiState s) {
    forced = s;
    notifyListeners();
  }

  /// Debug: oy sayısını 30'a çıkarmış gibi Öneriler kilidini açar (sunucuya oy yazmaz).
  void debugUnlock() {
    _debugMin = tourVotes;
    notifyListeners();
  }
}
