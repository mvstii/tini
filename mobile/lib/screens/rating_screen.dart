import 'dart:async';

import 'package:flutter/semantics.dart' show CustomSemanticsAction;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../app_state.dart';
import '../preview_player.dart';
import '../queue_controller.dart';
import '../strings.dart';
import '../theme/cosmic_colors.dart';
import '../theme/tini_tokens.dart';
import '../widgets/info_sheet.dart';
import '../widgets/like_button.dart';
import '../widgets/preview_widgets.dart';
import '../ui/components/components.dart';
import '../widgets/studio.dart';
import 'list_screen.dart';
import 'tracks_screen.dart';

export '../app_state.dart' show tourVotes;

/// Sağa kaydırma parçayı "Sonra dinle" listesine ekler (oy değildir, profili etkilemez); sola
/// kaydırma "Unheard" olayı yazar. Oy vermek için kartın altındaki kademe düğmeleri kullanılır.

/// Parça Spotify'da aranır: uygulama kuruluysa uygulamada, değilse web'de açılır.
Future<void> openInSpotify(String title, String artist) async {
  final q = Uri.encodeComponent('$title $artist'.trim());
  try {
    if (await launchUrl(
      Uri.parse('spotify:search:$q'),
      mode: LaunchMode.externalApplication,
    )) {
      return;
    }
  } catch (_) {}
  try {
    await launchUrl(
      Uri.parse('https://open.spotify.com/search/$q'),
      mode: LaunchMode.externalApplication,
    );
  } catch (_) {}
}

/// Sunucudaki (İngilizce) kademe adları; geçmiş ekranı kullanır.
const voteLabels = <int, String>{
  1: 'Awful',
  2: 'Bad',
  3: 'Meh',
  4: 'Good',
  5: 'Great',
  6: 'Amazing',
};

const _tabular = [FontFeature.tabularFigures()];

class RatingScreen extends StatefulWidget {
  const RatingScreen({
    super.key,
    required this.api,
    this.state,
    this.onLogout,
    this.onOpenRecommendations,
    this.bottomInset = 0,
  });
  final Api api;

  /// Kabuk tarafından paylaşılan durum; verilmezse ekran kendi durumunu kurar.
  final AppState? state;
  final VoidCallback? onLogout;

  /// Profil kurulunca çağrılır (kabukta Öneriler sekmesi); yoksa keşif listesi açılır.
  final VoidCallback? onOpenRecommendations;

  /// Alttaki yüzen menünün kapladığı yükseklik.
  final double bottomInset;

  @override
  State<RatingScreen> createState() => _RatingScreenState();
}

/// Geri alınabilir tek adım. Oy olayı silinmez; geri alınan kart yeniden gösterilir ve
/// verilecek yeni oy, yeni bir olay olarak öncekinin yerini alır.
class _Step {
  _Step(this.item, this.vote, {this.later = false, this.prevVote});
  final QueueItem item;
  final int? vote; // null: Unheard (later değilse)
  final bool later; // "Sonra dinle" listesine eklendi

  /// Bu adımdan önceki güncel oy (bilinmiyorsa null). Geri alınca yeni bir olay olarak yazılır.
  final int? prevVote;
}

class _RatingScreenState extends State<RatingScreen> {
  late final AppState _state = widget.state ?? AppState(widget.api);
  // Kuyruğun tek sahibi: kartlar, doldurma, geri çekilme (tohum denetleyicide).
  late final QueueController _queue = QueueController(
    ApiQueueBackend(widget.api),
    onUnauthorized: _logout,
  );
  final List<_Step> _history = [];
  bool _loading = true; // oturum durumu (_state.load) yükleniyor
  bool _busy = false;
  bool _peekPending = true;
  String? _error;
  int? _autoplayed; // otomatik çalma en son bu parça için tetiklendi

  QueueItem? get _current => _queue.current;

  @override
  void initState() {
    super.initState();
    _state.addListener(_onState);
    _queue.addListener(_onState);
    PreviewController.autoplay.addListener(_onState);
    _loadAutoplay();
    _init();
  }

  void _logout() {
    if (!mounted) return;
    if (Navigator.of(context).canPop()) Navigator.of(context).pop();
    widget.onLogout?.call();
  }

  static const _autoplayKey = 'preview_autoplay';

  Future<void> _loadAutoplay() async {
    try {
      final v = await const FlutterSecureStorage().read(key: _autoplayKey);
      PreviewController.autoplay.value = v == '1';
    } catch (_) {}
  }

  void _toggleAutoplay() {
    final on = !PreviewController.autoplay.value;
    PreviewController.autoplay.value = on;
    if (!on) PreviewController.instance.stop();
    unawaited(
      const FlutterSecureStorage()
          .write(key: _autoplayKey, value: on ? '1' : '0')
          .catchError((_) {}),
    );
  }

  /// Otomatik çalma açıkken üstteki kart değişince önizlemesi kendiliğinden başlar.
  void _maybeAutoplay() {
    final item = _current;
    if (!PreviewController.autoplay.value || item == null || _busy) return;
    if (_autoplayed == item.track) return;
    _autoplayed = item.track;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _current?.track != item.track) return;
      PreviewController.instance.toggle(
        'vote-${item.track}',
        () => widget.api.previewUrl(trackId: item.track),
        meta: PreviewMeta(
          title: item.title,
          artist: item.artistLine,
          image: item.image,
          track: item.track,
        ),
      );
    });
  }

  @override
  void dispose() {
    _state.removeListener(_onState);
    _queue.removeListener(_onState);
    _queue.dispose();
    PreviewController.autoplay.removeListener(_onState);
    if (widget.state == null) _state.dispose();
    super.dispose();
  }

  void _onState() {
    if (!mounted) return;
    setState(() {});
    // Tab çubuğundaki rozet: kuyrukta bekleyen şarkı sayısı (kabuk AppState'ten okur).
    _state.setPendingVotes(_queue.cards.length);
    _maybeAutoplay(); // kart/otomatik çalma değişimine olay olarak tepki (build içinde değil)
  }

  Future<void> _guard(Future<void> Function() action) async {
    try {
      await action();
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted && Navigator.of(context).canPop()) {
          Navigator.of(context).pop();
        }
        return widget.onLogout?.call();
      }
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    }
  }

  Future<void> _init() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    await _guard(() => _state.load());
    if (mounted) setState(() => _loading = false);
    // Kuyruk durumu denetleyiciden çizilir; başlatma ekranı bekletmez.
    unawaited(_queue.start());
  }

  Future<void> _answer(int? vote) async {
    final item = _current;
    if (item == null || _busy || _state.forced != UiState.normal) return;
    // Kart ağaçtan hemen çıkar; sunucu yanıtı beklenirse sürükleme durumu asılı kalır.
    setState(() {
      _busy = true;
      _error = null;
    });
    _queue.pop();
    final prev = _state.votes[item.track];
    var saved = false;
    await _guard(() async {
      if (vote != null) {
        await widget.api.castVote(item.track, vote, source: item.sourceLabel);
        _state.recordVote(item, vote);
      } else {
        await widget.api.markUnheard(item.track, source: item.sourceLabel);
        _state.recordUnheard();
      }
      saved = true;
      _history.add(_Step(item, vote, prevVote: prev));
    });
    if (!saved) _queue.putBack(item); // kayıt başarısızsa kart geri gelir
    if (mounted) {
      setState(() => _busy = false);
      _maybeAutoplay();
    }
  }

  /// Sağa kaydırma: parça "Sonra dinle" listesine girer, kuyruktan çıkar.
  Future<void> _later() async {
    final item = _current;
    if (item == null || _busy || _state.forced != UiState.normal) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    _queue.pop();
    var saved = false;
    await _guard(() async {
      await widget.api.addLater(item.track);
      saved = true;
      _history.add(_Step(item, null, later: true));
    });
    if (!saved) _queue.putBack(item);
    if (mounted) {
      setState(() => _busy = false);
      _maybeAutoplay();
      if (saved) {
        ScaffoldMessenger.of(context)
          ..clearSnackBars()
          ..showSnackBar(
            const SnackBar(
              content: Text('Sonra dinle listesine eklendi'),
              duration: Duration(seconds: 2),
            ),
          );
      }
    }
  }

  /// Geri al: kart kuyruğa döner. Parça daha önce oylanmışsa önceki oy yeni bir olay olarak
  /// yazılır (olay silinmez; güncel oy son olaydır). İlk kez oylanan parçada sunucudaki oy,
  /// kullanıcı yeniden oylayana kadar kalır (oyu temizleme olayı yok).
  Future<void> _undo() async {
    if (_history.isEmpty || _busy) return;
    final step = _history.removeLast();
    if (step.later) {
      unawaited(widget.api.removeLater(step.item.track).catchError((_) {}));
    }
    _queue.putBack(step.item);
    final prev = step.prevVote;
    final cur = step.vote;
    if (step.later || cur == null || prev == null || prev == cur) return;
    setState(
      () => _busy = true,
    ); // geri yazma bitmeden yeni oy gitmesin (sıra bozulmasın)
    await _guard(() async {
      await widget.api.castVote(step.item.track, prev);
      _state.recordChange(
        HistoryItem(
          step.item.track,
          cur,
          step.item.title,
          step.item.artists,
          step.item.image,
        ),
        prev,
      );
    });
    if (mounted) setState(() => _busy = false);
  }

  /// Keşif listesine geçer (kabukta Öneriler sekmesi; yoksa liste ekranı).
  void _openDiscover() {
    final open = widget.onOpenRecommendations;
    if (open != null) return open();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ListScreen(api: widget.api, onLogout: widget.onLogout),
      ),
    );
  }

  Future<void> _buildProfile() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    await _guard(() async {
      await widget.api.rebuildProfile();
      if (!mounted) return;
      _state.markProfileBuilt();
      final open = widget.onOpenRecommendations;
      if (open != null) return open();
      // Profil hazır: keşif listesine geç (oylamaya geri dönülebilir).
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) =>
              ListScreen(api: widget.api, onLogout: widget.onLogout),
        ),
      );
    });
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final canVote =
        !_busy &&
        !_loading &&
        _current != null &&
        _state.forced == UiState.normal;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: Padding(
          padding: EdgeInsets.fromLTRB(
            TiniTokens.listMargin,
            0,
            TiniTokens.listMargin,
            widget.bottomInset + 12,
          ),
          child: Column(
            children: [
              _TopBar(
                state: _state,
                canUndo: _history.isNotEmpty && !_busy,
                onUndo: _undo,
                autoplay: PreviewController.autoplay.value,
                onAutoplay: _toggleAutoplay,
                onSearch: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => SearchScreen(api: widget.api),
                  ),
                ),
                onLater: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => LaterScreen(api: widget.api),
                  ),
                ),
              ),
              AnimatedSize(
                duration: const Duration(milliseconds: 220),
                curve: Curves.easeOutCubic,
                alignment: Alignment.topCenter,
                child: Column(
                  children: [
                    if (_state.unlocked)
                      _ProfileBand(
                        built: _state.profileBuilt,
                        busy: _busy,
                        onBuild: _buildProfile,
                      ),
                    // Profil/özet yüklenemediyse seviye 0 görünür; hata ve yeniden deneme göster.
                    if (_error != null && (_current != null || !_state.loaded))
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                _error!,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: Theme.of(context).colorScheme.error,
                                ),
                              ),
                            ),
                            if (!_state.loaded)
                              TextButton(
                                onPressed: _loading ? null : _init,
                                child: const Text('Yeniden dene'),
                              ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Expanded(child: _cardArea(c, canVote)),
              const SizedBox(height: 12),
              // Kayıt sürerken dokunma kapalı ama düğmeler solmaz (her oyda titreme olmasın).
              Opacity(
                opacity:
                    _loading ||
                        _current == null ||
                        _state.forced != UiState.normal
                    ? 0.45
                    : 1,
                child: VoteRow(
                  enabled: canVote,
                  showLabels: true,
                  onVote: _answer,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(child: UnheardButton(onTap: canVote ? () => _answer(null) : null)),
                  const InfoIconButton(
                    title: TiniStrings.unheardInfoTitle,
                    body: TiniStrings.unheardInfoBody,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cardArea(TiniCosmicColors c, bool canVote) {
    final forced = _state.forced;
    final item = _current;
    if (forced == UiState.loading || _loading) {
      return _SkeletonCard(color: c.card);
    }
    if (forced == UiState.error) {
      return _MessageCard(
        color: c.card,
        icon: Icons.cloud_off_rounded,
        text: 'Bağlantı hatası',
        action: 'Yeniden dene',
        onAction: () {
          _state.setForced(UiState.normal);
          _init();
        },
      );
    }
    if (forced == UiState.queueFetching) {
      return _MessageCard(
        color: c.card,
        busy: true,
        text: 'Kuyruk bitti, yeni şarkılar taranıyor',
        action: 'Normale dön',
        onAction: () => _state.setForced(UiState.normal),
      );
    }
    if (item == null) {
      switch (_queue.status) {
        case QueueStatus.waking:
          return _MessageCard(
            color: c.card,
            busy: true,
            text: 'Sunucu uyanıyor, birkaç saniye sürebilir',
          );
        case QueueStatus.offline:
          return _MessageCard(
            color: c.card,
            icon: Icons.wifi_off_rounded,
            text: 'İnternet bağlantısı yok. Bağlantı gelince kendiliğinden devam eder.',
            action: 'Yeniden dene',
            onAction: _queue.retry,
          );
        case QueueStatus.failed:
          return _MessageCard(
            color: c.card,
            icon: Icons.cloud_off_rounded,
            text: _queue.message ?? 'Sunucuya ulaşılamadı',
            action: 'Yeniden dene',
            onAction: _queue.retry,
          );
        case QueueStatus.exhausted:
          return _MessageCard(
            color: c.card,
            icon: Icons.library_music_rounded,
            text: _queue.stale > 0
                ? '${_queue.stale} şarkının bilgisi eskidi. Kütüphaneyi yenile.'
                : 'Yeni şarkılar hazırlanıyor olabilir. Biraz sonra kendiliğinden bakılır.',
            action: _queue.stale > 0 ? 'Kütüphaneyi yenile' : 'Yeniden dene',
            onAction: _queue.stale > 0 ? _queue.refreshLibrary : _queue.retry,
            secondaryAction: _state.profileBuilt ? 'Keşif listesine git' : null,
            onSecondary: _openDiscover,
          );
        case QueueStatus.ready:
        case QueueStatus.filling:
          return _MessageCard(
            color: c.card,
            busy: true,
            text: 'Kuyruk bitti, yeni şarkılar taranıyor',
          );
      }
    }
    return _SwipeCard(
      key: ValueKey(item.track),
      api: widget.api,
      item: item,
      behind: _queue.cards.skip(1).take(2).toList(),
      color: c.card,
      enabled: canVote,
      peek: _peekPending,
      onPeeked: () => _peekPending = false,
      onLater: _later,
      onSkip: () => _answer(null),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.state,
    required this.canUndo,
    required this.onUndo,
    required this.autoplay,
    required this.onAutoplay,
    required this.onSearch,
    required this.onLater,
  });
  final AppState state;
  final bool canUndo;
  final VoidCallback onUndo;
  final bool autoplay;
  final VoidCallback onAutoplay;
  final VoidCallback onSearch;
  final VoidCallback onLater;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final theme = Theme.of(context);
    final total = state.total;
    final label = state.unlocked
        ? 'Seviye ${state.level} · ${state.inLevel} / $tourVotes · Toplam $total'
        : 'Başlangıç Turu · $total / $tourVotes';
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    label,
                    style: theme.textTheme.labelMedium?.copyWith(
                      fontFeatures: _tabular,
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                TweenAnimationBuilder<double>(
                  key: ValueKey(state.level),
                  tween: Tween(begin: 0, end: state.inLevel / tourVotes),
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeOutCubic,
                  builder: (_, v, _) => ClipRRect(
                    borderRadius: BorderRadius.circular(TiniTokens.rPill),
                    child: Container(
                      height: 4,
                      color: c.raised,
                      alignment: Alignment.centerLeft,
                      child: FractionallySizedBox(
                        key: const ValueKey('level-progress'),
                        widthFactor: v.clamp(0.0, 1.0),
                        child: const DecoratedBox(
                          decoration: BoxDecoration(gradient: TiniTokens.brandGradient),
                          child: SizedBox.expand(),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          StudioIconButton(
            key: const ValueKey('toggle-autoplay'),
            onPressed: onAutoplay,
            selected: autoplay,
            icon: Icons.volume_off_rounded,
            selectedIcon: Icons.volume_up_rounded,
            tooltip: autoplay ? 'Otomatik çalma açık' : 'Otomatik çalma kapalı',
          ),
          const SizedBox(width: 6),
          StudioIconButton(
            key: const ValueKey('open-search'),
            onPressed: onSearch,
            icon: Icons.search_rounded,
            tooltip: 'Şarkı ara',
          ),
          const SizedBox(width: 6),
          StudioIconButton(
            key: const ValueKey('open-later'),
            onPressed: onLater,
            icon: Icons.bookmark_border_rounded,
            selectedIcon: Icons.bookmark_rounded,
            tooltip: 'Sonra dinle',
          ),
          const SizedBox(width: 6),
          StudioIconButton(
            onPressed: canUndo ? onUndo : null,
            icon: Icons.undo_rounded,
            tooltip: 'Geri al',
          ),
        ],
      ),
    );
  }
}

class _ProfileBand extends StatelessWidget {
  const _ProfileBand({
    required this.built,
    required this.busy,
    required this.onBuild,
  });
  final bool built;
  final bool busy;
  final VoidCallback onBuild;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    return Container(
      height: 52,
      padding: const EdgeInsets.only(left: 12, right: 6),
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.primary.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Icon(Icons.graphic_eq_rounded, size: 20, color: c.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Tını profilin hazır',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelLarge,
            ),
          ),
          SizedBox(
            width: 168,
            child: StudioButton(
              dense: true,
              icon: built ? Icons.sync_rounded : Icons.auto_awesome_rounded,
              label: built ? 'Profili Güncelle' : 'Profili Kur',
              busy: busy,
              onPressed: busy ? null : onBuild,
            ),
          ),
        ],
      ),
    );
  }
}

BoxDecoration _cardDecoration(BuildContext context, Color color) {
  final t = TiniTokens.of(context);
  return BoxDecoration(
    borderRadius: BorderRadius.circular(TiniTokens.rHero),
    color: t.surface1,
    border: Border.all(color: t.line),
    boxShadow: [
      BoxShadow(
        color: t.scrim.withValues(alpha: 0.25),
        blurRadius: 24,
        offset: const Offset(0, 10),
      ),
    ],
  );
}

class _SwipeCard extends StatefulWidget {
  const _SwipeCard({
    super.key,
    required this.api,
    required this.item,
    required this.color,
    required this.enabled,
    required this.peek,
    required this.onPeeked,
    required this.onLater,
    required this.onSkip,
    this.behind = const [],
  });
  final Api api;
  final QueueItem item;
  final List<QueueItem> behind;
  final Color color;
  final bool enabled;
  final bool peek;
  final VoidCallback onPeeked;
  final VoidCallback onLater;
  final VoidCallback onSkip;

  @override
  State<_SwipeCard> createState() => _SwipeCardState();
}

class _SwipeCardState extends State<_SwipeCard>
    with SingleTickerProviderStateMixin {
  final _dx = ValueNotifier<double>(0);
  late final AnimationController _ctl = AnimationController(vsync: this);
  Animation<double>? _anim;
  bool _crossed = false;
  double _width = 300;

  double get _threshold => _width * 0.28;

  @override
  void initState() {
    super.initState();
    _ctl.addListener(() {
      final a = _anim;
      if (a != null) _dx.value = a.value;
    });
    if (widget.peek) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        widget.onPeeked();
        _anim = TweenSequence<double>([
          TweenSequenceItem(tween: Tween(begin: 0.0, end: 14.0), weight: 1),
          TweenSequenceItem(tween: Tween(begin: 14.0, end: -14.0), weight: 2),
          TweenSequenceItem(tween: Tween(begin: -14.0, end: 0.0), weight: 1),
        ]).chain(CurveTween(curve: Curves.easeInOut)).animate(_ctl);
        _ctl.duration = const Duration(milliseconds: 600);
        _ctl.forward(from: 0);
      });
    }
  }

  @override
  void dispose() {
    // Kart gidince (oy, geçiş) bu şarkının önizlemesi de susar; ağaç kilitliyken bildirim atılmaz.
    final preview = PreviewController.instance;
    if (preview.key == 'vote-${widget.item.track}') {
      scheduleMicrotask(preview.stop);
    }
    _ctl.dispose();
    _dx.dispose();
    super.dispose();
  }

  void _snapBack() {
    if (!mounted) return;
    _anim = Tween(
      begin: _dx.value,
      end: 0.0,
    ).chain(CurveTween(curve: Curves.easeOutCubic)).animate(_ctl);
    _ctl.duration = const Duration(milliseconds: 180);
    _ctl.forward(from: 0);
  }

  void _update(DragUpdateDetails d) {
    if (!widget.enabled) return;
    _ctl.stop();
    _dx.value += d.delta.dx;
    final over = _dx.value.abs() >= _threshold;
    if (over && !_crossed) HapticFeedback.lightImpact();
    _crossed = over;
  }

  void _end(DragEndDetails d) {
    final v = d.velocity.pixelsPerSecond.dx;
    final dx = _dx.value;
    final fling = v.abs() > 900 && dx.abs() > 20 && v.sign == dx.sign;
    _crossed = false;
    if (widget.enabled && (dx.abs() >= _threshold || fling)) {
      if (dx > 0) {
        widget.onLater();
      } else {
        widget.onSkip();
      }
    }
    _snapBack();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final c = TiniCosmicColors.of(context);
    final item = widget.item;
    return LayoutBuilder(
      builder: (context, box) {
        _width = box.maxWidth;
        final compact = box.maxHeight < 250;
        return Semantics(
          customSemanticsActions: widget.enabled
              ? {
                  const CustomSemanticsAction(label: 'Sonra dinle'):
                      widget.onLater,
                  const CustomSemanticsAction(label: 'Dinlemedim, geç'):
                      widget.onSkip,
                }
              : const {},
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onHorizontalDragUpdate: _update,
            onHorizontalDragEnd: _end,
            onHorizontalDragCancel: _snapBack,
            child: ValueListenableBuilder<double>(
              valueListenable: _dx,
              builder: (context, dx, child) => Transform(
                alignment: Alignment.bottomCenter,
                transform: Matrix4.identity()
                  ..translateByDouble(dx, 0, 0, 1)
                  ..rotateZ(dx / _width * 0.12),
                child: Stack(
                  children: [
                    child!,
                    if (dx.abs() > 20)
                      Positioned.fill(
                        child: IgnorePointer(
                          child: _SwipeOverlay(
                            right: dx > 0,
                            strength: ((dx.abs() - 20) / _threshold).clamp(
                              0.0,
                              1.0,
                            ),
                            style: dx > 0 ? c.votes[4]! : c.skip,
                            label: dx > 0 ? 'SONRA DİNLE' : 'DİNLEMEDİM · GEÇ',
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                child: Column(
                  children: [
                    Flexible(
                      child: Center(
                        child: AspectRatio(
                          aspectRatio: 1,
                          child: LayoutBuilder(
                            builder: (_, b) => Stack(
                              clipBehavior: Clip.none,
                              children: [
                                // Art arda dizilmiş sıradaki kartlar: hafif eğik, soluk.
                                for (final (i, g) in widget.behind.indexed.toList().reversed)
                                  Positioned.fill(
                                    child: Opacity(
                                      opacity: i == 0 ? 0.6 : 0.35,
                                      child: Transform.rotate(
                                        angle: (i == 0 ? -1 : 1) * (i == 0 ? 0.075 : 0.055),
                                        child: Transform.translate(
                                          offset: Offset(0, 10.0 * (i + 1)),
                                          child: TiniCover(
                                            key: ValueKey('behind-${g.track}'),
                                            seed: '${g.title}|${g.artistLine}',
                                            url: g.image,
                                            size: b.biggest.shortestSide,
                                            radius: TiniTokens.rSheet,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                TiniCover(
                                  seed: '${item.title}|${item.artistLine}',
                                  url: item.image,
                                  size: b.biggest.shortestSide,
                                  radius: TiniTokens.rSheet,
                                ),
                                Positioned(
                                  top: 6,
                                  right: 6,
                                  child: LikeButton(
                                    api: widget.api,
                                    track: item.track,
                                    liked: item.liked,
                                    overlay: true,
                                    onChanged: (v) => item.liked = v,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      item.title,
                      textAlign: TextAlign.center,
                      maxLines: compact ? 1 : 2,
                      overflow: TextOverflow.ellipsis,
                      style: studioTitle(
                        context,
                        base: theme.textTheme.titleLarge,
                      ),
                    ),
                    Text(
                      item.artistLine,
                      textAlign: TextAlign.center,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (item.source == 'suggested' && !compact)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          item.reasonSeed != null
                              ? "${item.reasonSeed}'i sevdiğin için"
                              : 'Senin için önerildi',
                          key: const ValueKey('source-badge'),
                          textAlign: TextAlign.center,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.labelMedium?.copyWith(
                            color: c.primary,
                          ),
                        ),
                      ),
                    if (item.isDiscovery && !compact)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: InkWell(
                          key: const ValueKey('discovery-badge'),
                          borderRadius: BorderRadius.circular(8),
                          onTap: () => showTiniInfoSheet(
                            context,
                            title: TiniStrings.discoveryInfoTitle,
                            body: TiniStrings.discoveryInfoBody(
                              item.coverageSub == null
                                  ? null
                                  : TiniStrings.subGenreLabel(item.coverageSub!),
                              joker: item.source == 'joker',
                            ),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Flexible(
                                  child: Text(
                                    [
                                      item.source == 'joker'
                                          ? TiniStrings.discoveryJoker
                                          : TiniStrings.discoveryProbe,
                                      if (item.coverageSub != null)
                                        TiniStrings.subGenreLabel(
                                          item.coverageSub!,
                                        ),
                                    ].join(' · '),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: theme.textTheme.labelMedium
                                        ?.copyWith(color: c.primary),
                                  ),
                                ),
                                const SizedBox(width: 4),
                                Icon(
                                  Icons.info_outline,
                                  size: 14,
                                  color: c.primary,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    const SizedBox(height: 10),
                    PreviewClip(
                      api: widget.api,
                      previewKey: 'vote-${item.track}',
                      trackId: item.track,
                      title: item.title,
                      artist: item.artistLine,
                      image: item.image,
                      source: switch (item.source) {
                        'suggested' => 'Öneri',
                        'probe' => TiniStrings.discoveryProbe,
                        'joker' => TiniStrings.discoveryJoker,
                        _ => null,
                      },
                      onOpenExternal: () =>
                          openInSpotify(item.title, item.artistLine),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _SwipeOverlay extends StatelessWidget {
  const _SwipeOverlay({
    required this.right,
    required this.strength,
    required this.style,
    required this.label,
  });
  final bool right;
  final double strength;
  final VoteStyle style;
  final String label;

  @override
  Widget build(BuildContext context) {
    // Renkler sağda "İyi" kademesinin stilinden gelir (yalnızca renk; sağ kaydırma oy vermez); sol: nötr gri.
    final base = style.fill;
    return Container(
      decoration: BoxDecoration(
        color: base.withValues(alpha: 0.35 + 0.5 * strength),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: style.border, width: 2),
      ),
      alignment: Alignment.center,
      child: Opacity(
        opacity: 0.4 + 0.6 * strength,
        child: Text(
          label,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            color: style.fg,
            fontWeight: FontWeight.w800,
            letterSpacing: 1,
          ),
        ),
      ),
    );
  }
}

class _SkeletonCard extends StatefulWidget {
  const _SkeletonCard({required this.color});
  final Color color;

  @override
  State<_SkeletonCard> createState() => _SkeletonCardState();
}

class _SkeletonCardState extends State<_SkeletonCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _ctl.stop();
      _ctl.value = 1;
    } else if (!_ctl.isAnimating) {
      _ctl.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bar = Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.12);
    Widget block(double? w, double h, double r) => Container(
      width: w,
      height: h,
      decoration: BoxDecoration(
        color: bar,
        borderRadius: BorderRadius.circular(r),
      ),
    );
    return Container(
      decoration: _cardDecoration(context, widget.color),
      padding: const EdgeInsets.all(14),
      child: FadeTransition(
        opacity: Tween(begin: 0.45, end: 1.0).animate(_ctl),
        child: Column(
          children: [
            Flexible(
              child: Center(
                child: AspectRatio(
                  aspectRatio: 1,
                  child: Container(
                    decoration: BoxDecoration(
                      color: bar,
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 14),
            block(180, 20, 6),
            const SizedBox(height: 8),
            block(110, 14, 6),
            const SizedBox(height: 8),
            Align(alignment: Alignment.centerRight, child: block(150, 40, 20)),
          ],
        ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({
    required this.color,
    required this.text,
    this.icon,
    this.busy = false,
    this.action,
    this.onAction,
    this.secondaryAction,
    this.onSecondary,
  });
  final Color color;
  final String text;
  final IconData? icon;
  final bool busy;
  final String? action;
  final VoidCallback? onAction;
  final String? secondaryAction;
  final VoidCallback? onSecondary;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    return Container(
      width: double.infinity,
      decoration: _cardDecoration(context, color),
      padding: const EdgeInsets.all(24),
      child: Center(
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (busy)
                const SizedBox(
                  width: 40,
                  height: 40,
                  child: CircularProgressIndicator(),
                )
              else if (icon != null)
                Icon(icon, size: 48, color: c.primary),
              const SizedBox(height: 16),
              Text(text, textAlign: TextAlign.center),
              if (action != null) ...[
                const SizedBox(height: 16),
                FilledButton.tonal(onPressed: onAction, child: Text(action!)),
              ],
              if (secondaryAction != null) ...[
                const SizedBox(height: 8),
                TextButton(
                  onPressed: onSecondary,
                  child: Text(secondaryAction!),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
