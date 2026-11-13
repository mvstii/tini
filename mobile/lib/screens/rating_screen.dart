import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/semantics.dart' show CustomSemanticsAction;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../app_state.dart';
import '../preview_player.dart';
import '../queue_controller.dart';
import '../theme/cosmic_colors.dart';
import '../widgets/cover_art.dart';
import '../widgets/like_button.dart';
import '../widgets/preview_button.dart';
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
    if (await launchUrl(Uri.parse('spotify:search:$q'), mode: LaunchMode.externalApplication)) {
      return;
    }
  } catch (_) {}
  try {
    await launchUrl(Uri.parse('https://open.spotify.com/search/$q'),
        mode: LaunchMode.externalApplication);
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
    unawaited(const FlutterSecureStorage()
        .write(key: _autoplayKey, value: on ? '1' : '0')
        .catchError((_) {}));
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
          'vote-${item.track}', () => widget.api.previewUrl(trackId: item.track));
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
    _maybeAutoplay(); // kart/otomatik çalma değişimine olay olarak tepki (build içinde değil)
  }

  Future<void> _guard(Future<void> Function() action) async {
    try {
      await action();
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted && Navigator.of(context).canPop()) Navigator.of(context).pop();
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
          ..showSnackBar(const SnackBar(
              content: Text('Sonra dinle listesine eklendi'), duration: Duration(seconds: 2)));
      }
    }
  }

  /// Geri al: kart kuyruğa döner. Parça daha önce oylanmışsa önceki oy yeni bir olay olarak
  /// yazılır (olay silinmez; güncel oy son olaydır). İlk kez oylanan parçada sunucudaki oy,
  /// kullanıcı yeniden oylayana kadar kalır (oyu temizleme olayı yok).
  Future<void> _undo() async {
    if (_history.isEmpty || _busy) return;
    final step = _history.removeLast();
    if (step.later) unawaited(widget.api.removeLater(step.item.track).catchError((_) {}));
    _queue.putBack(step.item);
    final prev = step.prevVote;
    final cur = step.vote;
    if (step.later || cur == null || prev == null || prev == cur) return;
    setState(() => _busy = true); // geri yazma bitmeden yeni oy gitmesin (sıra bozulmasın)
    await _guard(() async {
      await widget.api.castVote(step.item.track, prev);
      _state.recordChange(
          HistoryItem(step.item.track, cur, step.item.title, step.item.artists), prev);
    });
    if (mounted) setState(() => _busy = false);
  }

  /// Keşif listesine geçer (kabukta Öneriler sekmesi; yoksa liste ekranı).
  void _openDiscover() {
    final open = widget.onOpenRecommendations;
    if (open != null) return open();
    Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => ListScreen(api: widget.api, onLogout: widget.onLogout)));
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
      await Navigator.of(context).push(MaterialPageRoute<void>(
          builder: (_) => ListScreen(api: widget.api, onLogout: widget.onLogout)));
    });
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final canVote = !_busy &&
        !_loading &&
        _current != null &&
        _state.forced == UiState.normal;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: Padding(
          padding: EdgeInsets.fromLTRB(16, 0, 16, widget.bottomInset + 8),
          child: Column(
            children: [
              _TopBar(
                state: _state,
                canUndo: _history.isNotEmpty && !_busy,
                onUndo: _undo,
                autoplay: PreviewController.autoplay.value,
                onAutoplay: _toggleAutoplay,
                onSearch: () => Navigator.of(context).push(MaterialPageRoute<void>(
                    builder: (_) => SearchScreen(api: widget.api))),
                onLater: () => Navigator.of(context).push(MaterialPageRoute<void>(
                    builder: (_) => LaterScreen(api: widget.api))),
              ),
              AnimatedSize(
                duration: const Duration(milliseconds: 220),
                curve: Curves.easeOutCubic,
                alignment: Alignment.topCenter,
                child: Column(
                  children: [
                    if (_state.unlocked)
                      _ProfileBand(
                          built: _state.profileBuilt, busy: _busy, onBuild: _buildProfile),
                    // Profil/özet yüklenemediyse seviye 0 görünür; hata ve yeniden deneme göster.
                    if (_error != null && (_current != null || !_state.loaded))
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(_error!,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
                            ),
                            if (!_state.loaded)
                              TextButton(
                                  onPressed: _loading ? null : _init,
                                  child: const Text('Yeniden dene')),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Expanded(child: _cardArea(c, canVote)),
              const SizedBox(height: 10),
              // Kayıt sürerken dokunma kapalı ama düğmeler solmaz (her oyda titreme olmasın).
              _VoteGrid(
                  enabled: canVote,
                  dimmed: _loading || _current == null || _state.forced != UiState.normal,
                  onVote: _answer),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cardArea(TiniCosmicColors c, bool canVote) {
    final forced = _state.forced;
    final item = _current;
    if (forced == UiState.loading || _loading) return _SkeletonCard(color: c.card);
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
                : 'Oylanacak şarkı kalmadı.',
            action: 'Kütüphaneyi yenile',
            onAction: _queue.refreshLibrary,
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
                  child: Text(label,
                      style: theme.textTheme.labelMedium?.copyWith(fontFeatures: _tabular)),
                ),
                const SizedBox(height: 4),
                TweenAnimationBuilder<double>(
                  key: ValueKey(state.level),
                  tween: Tween(begin: 0, end: state.inLevel / tourVotes),
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeOutCubic,
                  builder: (_, v, _) => LinearProgressIndicator(
                    value: v,
                    minHeight: 6,
                    borderRadius: BorderRadius.circular(3),
                    color: c.primary,
                    backgroundColor: c.card,
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
  const _ProfileBand({required this.built, required this.busy, required this.onBuild});
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
            child: Text('Tını profilin hazır',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelLarge),
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
  final dark = Theme.of(context).brightness == Brightness.dark;
  final tok = TiniCosmicColors.of(context);
  return BoxDecoration(
    borderRadius: BorderRadius.circular(24),
    gradient: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      // Dolu, katmanlı yüzey: açık temada da beyaz boşluk yerine lavanta geçiş.
      colors: dark ? [tok.raised, tok.card] : [Colors.white, tok.raised],
    ),
    border: Border.all(
        color: dark ? Colors.white.withValues(alpha: 0.10) : tok.primary.withValues(alpha: 0.18)),
    boxShadow: [
      BoxShadow(
          color: tok.primary.withValues(alpha: dark ? 0.16 : 0.14),
          blurRadius: 30,
          offset: const Offset(0, 12)),
      if (dark) const BoxShadow(color: Color(0x99000000), blurRadius: 14, offset: Offset(0, 4)),
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
  });
  final Api api;
  final QueueItem item;
  final Color color;
  final bool enabled;
  final bool peek;
  final VoidCallback onPeeked;
  final VoidCallback onLater;
  final VoidCallback onSkip;

  @override
  State<_SwipeCard> createState() => _SwipeCardState();
}

class _SwipeCardState extends State<_SwipeCard> with SingleTickerProviderStateMixin {
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
    if (preview.key == 'vote-${widget.item.track}') scheduleMicrotask(preview.stop);
    _ctl.dispose();
    _dx.dispose();
    super.dispose();
  }

  void _snapBack() {
    if (!mounted) return;
    _anim = Tween(begin: _dx.value, end: 0.0)
        .chain(CurveTween(curve: Curves.easeOutCubic))
        .animate(_ctl);
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
    return LayoutBuilder(builder: (context, box) {
      _width = box.maxWidth;
      final compact = box.maxHeight < 250;
      final hintStyle = theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurface);
      return Semantics(
        customSemanticsActions: widget.enabled
            ? {
                const CustomSemanticsAction(label: 'Sonra dinle'): widget.onLater,
                const CustomSemanticsAction(label: 'Dinlemedim, geç'): widget.onSkip,
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
                        strength: ((dx.abs() - 20) / _threshold).clamp(0.0, 1.0),
                        style: dx > 0 ? c.votes[4]! : c.skip,
                        label: dx > 0 ? 'SONRA DİNLE' : 'DİNLEMEDİM · GEÇ',
                      ),
                    ),
                  ),
              ],
            ),
          ),
          child: Container(
            decoration: _cardDecoration(context, widget.color),
            padding: const EdgeInsets.all(14),
            child: Column(
              children: [
                if (!compact)
                  Opacity(
                    opacity: 0.6,
                    child: Row(
                      children: [
                        Icon(Icons.chevron_left_rounded, size: 18, color: theme.colorScheme.onSurface),
                        Text('Geç', style: hintStyle),
                        const Spacer(),
                        Text('Sonra dinle', style: hintStyle),
                        Icon(Icons.chevron_right_rounded, size: 18, color: theme.colorScheme.onSurface),
                      ],
                    ),
                  ),
                Flexible(
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: 1,
                      child: LayoutBuilder(
                        builder: (_, b) => Stack(
                          children: [
                            CoverArt(
                              url: item.image,
                              size: b.biggest.shortestSide,
                              radius: 16,
                              gradientSeed: item.title,
                              glow: true,
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
                Text(item.title,
                    textAlign: TextAlign.center,
                    maxLines: compact ? 1 : 2,
                    overflow: TextOverflow.ellipsis,
                    style: studioTitle(context, base: theme.textTheme.titleLarge)),
                Text(item.artistLine,
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodyMedium
                        ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
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
                      style: theme.textTheme.labelMedium?.copyWith(color: c.primary),
                    ),
                  ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    PreviewButton(
                        api: widget.api,
                        previewKey: 'vote-${item.track}',
                        trackId: item.track),
                    const SizedBox(width: 8),
                    StudioLinkPill(
                      key: const ValueKey('open-spotify'),
                      onPressed: () => openInSpotify(item.title, item.artistLine),
                      icon: Icons.open_in_new_rounded,
                      label: "Spotify'da aç",
                      accent: Theme.of(context).brightness == Brightness.dark
                          ? const Color(0xFF1DB954)
                          : const Color(0xFF138A3D),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Align(
                        alignment: Alignment.centerRight,
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerRight,
                          child: _SkipPill(
                              style: c.skip, enabled: widget.enabled, onTap: widget.onSkip),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ));
    });
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
        child: Text(label,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: style.fg,
                fontWeight: FontWeight.w800,
                letterSpacing: 1)),
      ),
    );
  }
}

class _SkipPill extends StatelessWidget {
  const _SkipPill({required this.style, required this.enabled, required this.onTap});
  final VoteStyle style;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Hoverable(
      enabled: enabled,
      child: Opacity(
      opacity: enabled ? 1 : 0.45,
      child: Material(
        color: style.fill,
        shape: StadiumBorder(side: BorderSide(color: style.border)),
        child: InkWell(
          key: const ValueKey('skip-pill'),
          customBorder: const StadiumBorder(),
          onTap: enabled ? onTap : null,
          child: SizedBox(
            height: 40,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(style.icon, size: 20, color: style.fg),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(style.label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context)
                            .textTheme
                            .labelLarge
                            ?.copyWith(color: style.fg)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      ),
    );
  }
}

class _VoteGrid extends StatelessWidget {
  const _VoteGrid({required this.enabled, required this.dimmed, required this.onVote});
  final bool enabled;
  final bool dimmed;
  final ValueChanged<int> onVote;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    // Sabit yükseklik yerine alt sınır: büyük yazı ölçeğinde düğmeler büyür, taşmaz.
    Widget row(List<int> ids, double h) => ConstrainedBox(
          constraints: BoxConstraints(minHeight: h),
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
              for (var i = 0; i < ids.length; i++) ...[
                if (i > 0) const SizedBox(width: 8),
                Expanded(
                  child: _VoteButton(
                    value: ids[i],
                    style: c.votes[ids[i]]!,
                    enabled: enabled,
                    dimmed: dimmed,
                    onTap: () => onVote(ids[i]),
                  ),
                ),
              ],
            ],
            ),
          ),
        );
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        row(const [1, 2, 3], 50),
        const SizedBox(height: 8),
        row(const [4, 5, 6], 54),
      ],
    );
  }
}

class _VoteButton extends StatefulWidget {
  const _VoteButton(
      {required this.value,
      required this.style,
      required this.enabled,
      required this.dimmed,
      required this.onTap});
  final int value;
  final VoteStyle style;
  final bool enabled;
  final bool dimmed;
  final VoidCallback onTap;

  @override
  State<_VoteButton> createState() => _VoteButtonState();
}

class _VoteButtonState extends State<_VoteButton> with SingleTickerProviderStateMixin {
  bool _pressed = false;
  bool _hover = false;

  /// Dokunuşta bir kez oynar (tekrarlı değil): halka dışa yayılır, ikon zıplar, yüzey parlar.
  late final AnimationController _burst =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 520));

  @override
  void dispose() {
    _burst.dispose();
    super.dispose();
  }

  void _tap() {
    HapticFeedback.selectionClick();
    if (!MediaQuery.disableAnimationsOf(context)) _burst.forward(from: 0);
    widget.onTap();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.style;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final live = widget.enabled && !widget.dimmed;
    final lit = live && (_pressed || _hover);
    // Yüksek oylar daha sıcak ışır: 6 en güçlü, 1 en sönük.
    final heat = 0.6 + 0.4 * (widget.value / 6);
    final glow = !live
        ? <BoxShadow>[]
        : [
            BoxShadow(
                color: s.border.withValues(alpha: (lit ? 0.55 : (dark ? 0.24 : 0.20)) * heat),
                blurRadius: lit ? 20 : 12,
                offset: Offset(0, lit ? 3 : 5)),
          ];
    return Semantics(
      button: true,
      enabled: widget.enabled,
      label: '${widget.value}, ${s.label}',
      excludeSemantics: true,
      onTap: widget.enabled ? widget.onTap : null,
      child: Opacity(
        opacity: widget.dimmed ? 0.45 : 1,
        child: AnimatedScale(
          scale: _pressed ? 0.93 : (_hover && widget.enabled ? 1.05 : 1),
          duration: Duration(milliseconds: _pressed ? 90 : 280),
          curve: _pressed ? Curves.easeOut : Curves.easeOutBack,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutCubic,
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), boxShadow: glow),
            child: Ink(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: s.border, width: s.borderWidth),
                // Sol üstten gelen ışık: üstte açılmış, altta kendi rengine inen geçiş.
                gradient: LinearGradient(
                  begin: const Alignment(-0.6, -1),
                  end: const Alignment(0.4, 1),
                  colors: [
                    Color.alphaBlend(Colors.white.withValues(alpha: lit ? 0.18 : 0.12), s.fill),
                    s.fill,
                    Color.alphaBlend(s.border.withValues(alpha: dark ? 0.10 : 0.06), s.fill),
                  ],
                  stops: const [0, 0.55, 1],
                ),
              ),
              child: InkWell(
                key: ValueKey('vote-${widget.value}'),
                customBorder: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                onHighlightChanged: (v) => setState(() => _pressed = v),
                onHover: (v) => setState(() => _hover = v),
                onTap: widget.enabled ? _tap : null,
                child: AnimatedBuilder(
                  animation: _burst,
                  builder: (_, child) {
                    final t = _burst.value;
                    final active = _burst.isAnimating;
                    return Stack(
                      alignment: Alignment.center,
                      clipBehavior: Clip.none,
                      children: [
                        if (active) ...[
                          // Parlama: yüzey kısa süre aydınlanıp söner.
                          Positioned.fill(
                            child: DecoratedBox(
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(14),
                                color: s.fg.withValues(alpha: 0.28 * (1 - Curves.easeOut.transform(t))),
                              ),
                            ),
                          ),
                          // Halka: düğme çevresinden dışa yayılıp solar.
                          Positioned.fill(
                            child: Transform.scale(
                              scale: 1 + 0.35 * Curves.easeOutCubic.transform(t),
                              child: DecoratedBox(
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(14),
                                  border: Border.all(
                                      color: s.fg.withValues(alpha: 0.7 * (1 - t)), width: 2),
                                ),
                              ),
                            ),
                          ),
                        ],
                        child!,
                      ],
                    );
                  },
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text('${widget.value}',
                                style: TextStyle(
                                    fontSize: 15,
                                    color: s.fg,
                                    fontWeight: FontWeight.w700,
                                    fontFeatures: _tabular)),
                            const SizedBox(width: 4),
                            // İkon: dokunuşta yaylanarak büyüyüp döner, sonra yerine oturur.
                            AnimatedBuilder(
                              animation: _burst,
                              builder: (_, child) {
                                final k = math.sin(math.pi * Curves.easeOut.transform(_burst.value));
                                return Transform.rotate(
                                  angle: 0.35 * k * (widget.value.isEven ? -1 : 1),
                                  child: Transform.scale(scale: 1 + 0.55 * k, child: child),
                                );
                              },
                              child: Icon(s.icon, size: 18, color: s.fg),
                            ),
                          ],
                        ),
                        Text(s.label,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                fontSize: 12, fontWeight: FontWeight.w600, color: s.fg, height: 1.1)),
                      ],
                    ),
                  ),
                ),
              ),
            ),
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

class _SkeletonCardState extends State<_SkeletonCard> with SingleTickerProviderStateMixin {
  late final AnimationController _ctl = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 900));

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
        decoration: BoxDecoration(color: bar, borderRadius: BorderRadius.circular(r)));
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
                        color: bar, borderRadius: BorderRadius.circular(16)),
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
                const SizedBox(width: 40, height: 40, child: CircularProgressIndicator())
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
                TextButton(onPressed: onSecondary, child: Text(secondaryAction!)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
