import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../app_state.dart';
import '../preview_player.dart';
import '../theme/cosmic_colors.dart';
import '../widgets/cover_art.dart';
import '../widgets/preview_button.dart';
import '../widgets/studio.dart';
import 'list_screen.dart';
import 'tracks_screen.dart';

export '../app_state.dart' show tourVotes;

/// Kalan kart sayısı bunun altına düşünce kuyruk arka planda yenilenir.
const prefetchBelow = 6;

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
  _Step(this.item, this.vote, {this.later = false});
  final QueueItem item;
  final int? vote; // null: Unheard (later değilse)
  final bool later; // "Sonra dinle" listesine eklendi
}

class _RatingScreenState extends State<RatingScreen> {
  late final AppState _state = widget.state ?? AppState(widget.api);
  final List<QueueItem> _cards = [];
  final Set<int> _skipped = {};
  final Set<int> _voted = {};
  final List<_Step> _history = [];
  // Her açılışta farklı tohum: sabit 0 olunca aynı şarkı hep ilk sırada çıkıyordu.
  int _seed = DateTime.now().millisecondsSinceEpoch % 100000;
  int _stale = 0;
  bool _loading = true;
  bool _filling = false;
  bool _busy = false;
  bool _peekPending = true;
  String? _error;

  QueueItem? get _current => _cards.isEmpty ? null : _cards.first;

  @override
  void initState() {
    super.initState();
    _state.addListener(_onState);
    _init();
  }

  @override
  void dispose() {
    _state.removeListener(_onState);
    if (widget.state == null) _state.dispose();
    super.dispose();
  }

  void _onState() {
    if (mounted) setState(() {});
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
    await _guard(() async {
      await _state.load();
      await _fill();
    });
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _fill() async {
    final q = await widget.api.voteQueue(seed: _seed);
    _stale = q.stale;
    final seen = _cards.map((c) => c.track).toSet();
    // Sunucu, oy kaydedilmeden önce başlayan bir istekte az önce oylanan parçayı da dönebilir.
    final fresh = q.items.where(
        (i) => !_skipped.contains(i.track) && !_voted.contains(i.track) && !seen.contains(i.track));
    if (mounted) setState(() => _cards.addAll(fresh));
  }

  /// Kartlar azalınca arka planda doldurur; kullanıcı beklemez. Hızlı oylamada kartlar yine
  /// tükenirse boş durum yerine yükleme göstergesi çıkar (`_filling`).
  Future<void> _topUp() async {
    if (_filling) return;
    setState(() => _filling = true);
    _seed++;
    await _guard(() async {
      try {
        await _fill();
      } on ApiException {
        rethrow;
      } catch (_) {
        await _fill(); // geçici ağ hatasında bir kez daha dene
      }
    });
    if (mounted) setState(() => _filling = false);
  }

  Future<void> _refreshLibrary() async {
    setState(() => _loading = true);
    await _guard(() async {
      await widget.api.importLibrary();
      await _fill();
    });
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _answer(int? vote) async {
    final item = _current;
    if (item == null || _busy || _state.forced != UiState.normal) return;
    // Kart ağaçtan hemen çıkar; sunucu yanıtı beklenirse sürükleme durumu asılı kalır.
    setState(() {
      _busy = true;
      _error = null;
      _cards.removeAt(0);
    });
    var saved = false;
    await _guard(() async {
      if (vote != null) {
        await widget.api.castVote(item.track, vote);
        _voted.add(item.track);
        _state.recordVote(item, vote);
      } else {
        await widget.api.markUnheard(item.track);
        _skipped.add(item.track);
        _state.recordUnheard();
      }
      saved = true;
      _history.add(_Step(item, vote));
    });
    if (mounted) {
      setState(() {
        if (!saved) _cards.insert(0, item); // kayıt başarısızsa kart geri gelir
        _busy = false;
      });
      if (saved && _cards.length < prefetchBelow) _topUp();
    }
  }

  /// Sağa kaydırma: parça "Sonra dinle" listesine girer, kuyruktan çıkar.
  Future<void> _later() async {
    final item = _current;
    if (item == null || _busy || _state.forced != UiState.normal) return;
    setState(() {
      _busy = true;
      _error = null;
      _cards.removeAt(0);
    });
    var saved = false;
    await _guard(() async {
      await widget.api.addLater(item.track);
      _skipped.add(item.track);
      saved = true;
      _history.add(_Step(item, null, later: true));
    });
    if (mounted) {
      setState(() {
        if (!saved) _cards.insert(0, item);
        _busy = false;
      });
      if (saved) {
        ScaffoldMessenger.of(context)
          ..clearSnackBars()
          ..showSnackBar(const SnackBar(
              content: Text('Sonra dinle listesine eklendi'), duration: Duration(seconds: 2)));
        if (_cards.length < prefetchBelow) _topUp();
      }
    }
  }

  void _undo() {
    if (_history.isEmpty || _busy) return;
    final step = _history.removeLast();
    if (step.later) unawaited(widget.api.removeLater(step.item.track).catchError((_) {}));
    setState(() {
      _skipped.remove(step.item.track);
      _voted.remove(step.item.track);
      _cards.insert(0, step.item);
    });
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
                    if (_error != null && _current != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(_error!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(color: Theme.of(context).colorScheme.error)),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Expanded(child: _cardArea(c, canVote)),
              const SizedBox(height: 10),
              _VoteGrid(enabled: canVote, onVote: _answer),
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
    if (forced == UiState.error || (_error != null && item == null && !_filling)) {
      return _MessageCard(
        color: c.card,
        icon: Icons.cloud_off_rounded,
        text: forced == UiState.error ? 'Bağlantı hatası' : _error!,
        action: 'Yeniden dene',
        onAction: () {
          _state.setForced(UiState.normal);
          _init();
        },
      );
    }
    if (forced == UiState.queueFetching || (item == null && _filling)) {
      return _MessageCard(
        color: c.card,
        busy: true,
        text: 'Kuyruk bitti, yeni şarkılar taranıyor',
        action: forced == UiState.queueFetching ? 'Normale dön' : null,
        onAction: () => _state.setForced(UiState.normal),
      );
    }
    if (item == null) {
      return _MessageCard(
        color: c.card,
        icon: Icons.library_music_rounded,
        text: _stale > 0
            ? '$_stale şarkının bilgisi eskidi. Kütüphaneyi yenile.'
            : 'Oylanacak şarkı yok.',
        action: _stale > 0 ? 'Kütüphaneyi yenile' : 'Yeniden dene',
        onAction: _stale > 0 ? _refreshLibrary : _init,
      );
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
    required this.onSearch,
    required this.onLater,
  });
  final AppState state;
  final bool canUndo;
  final VoidCallback onUndo;
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
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: c.card,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: c.primary.withValues(alpha: 0.5)),
            ),
            child: Text('Seviye ${state.level}',
                style: theme.textTheme.labelMedium
                    ?.copyWith(color: c.primary, fontFeatures: _tabular)),
          ),
          const SizedBox(width: 12),
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
          SizedBox(
            width: 40,
            height: 48,
            child: IconButton(
              key: const ValueKey('open-search'),
              padding: EdgeInsets.zero,
              onPressed: onSearch,
              icon: const Icon(Icons.search_rounded),
              tooltip: 'Şarkı ara',
            ),
          ),
          SizedBox(
            width: 40,
            height: 48,
            child: IconButton(
              key: const ValueKey('open-later'),
              padding: EdgeInsets.zero,
              onPressed: onLater,
              icon: const Icon(Icons.bookmark_border_rounded),
              tooltip: 'Sonra dinle',
            ),
          ),
          SizedBox(
            width: 40,
            height: 48,
            child: IconButton(
              padding: EdgeInsets.zero,
              onPressed: canUndo ? onUndo : null,
              icon: const Icon(Icons.undo_rounded),
              tooltip: 'Geri al',
            ),
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
  return BoxDecoration(
    borderRadius: BorderRadius.circular(24),
    gradient: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: dark
          ? const [Color(0xFF1B1730), Color(0xFF171329)]
          : [Colors.white, color],
    ),
    border: Border.all(color: (dark ? Colors.white : Colors.black).withValues(alpha: dark ? 0.08 : 0.06)),
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
      return GestureDetector(
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
                        Text('İyi', style: hintStyle),
                        Icon(Icons.chevron_right_rounded, size: 18, color: theme.colorScheme.onSurface),
                      ],
                    ),
                  ),
                Flexible(
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: 1,
                      child: LayoutBuilder(
                        builder: (_, b) => CoverArt(
                          url: item.image,
                          size: b.biggest.shortestSide,
                          radius: 16,
                          gradientSeed: item.title,
                          glow: true,
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
                const SizedBox(height: 8),
                Row(
                  children: [
                    PreviewButton(
                        api: widget.api,
                        previewKey: 'vote-${item.track}',
                        trackId: item.track),
                    const SizedBox(width: 4),
                    TextButton.icon(
                      key: const ValueKey('open-spotify'),
                      onPressed: () => openInSpotify(item.title, item.artistLine),
                      icon: const Icon(Icons.open_in_new_rounded, size: 18),
                      label: const Text("Spotify'da aç"),
                      style: TextButton.styleFrom(
                          foregroundColor: theme.colorScheme.onSurfaceVariant,
                          textStyle: theme.textTheme.labelMedium,
                          padding: const EdgeInsets.symmetric(horizontal: 8)),
                    ),
                    const SizedBox(width: 4),
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
      );
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
    // Renkler kademenin (sağ: "İyi") kendi stilinden gelir; sol: nötr gri.
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
  const _VoteGrid({required this.enabled, required this.onVote});
  final bool enabled;
  final ValueChanged<int> onVote;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    Widget row(List<int> ids, double h) => SizedBox(
          height: h,
          child: Row(
            children: [
              for (var i = 0; i < ids.length; i++) ...[
                if (i > 0) const SizedBox(width: 8),
                Expanded(
                  child: _VoteButton(
                    value: ids[i],
                    style: c.votes[ids[i]]!,
                    enabled: enabled,
                    onTap: () => onVote(ids[i]),
                  ),
                ),
              ],
            ],
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
      {required this.value, required this.style, required this.enabled, required this.onTap});
  final int value;
  final VoteStyle style;
  final bool enabled;
  final VoidCallback onTap;

  @override
  State<_VoteButton> createState() => _VoteButtonState();
}

class _VoteButtonState extends State<_VoteButton> {
  bool _pressed = false;
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final s = widget.style;
    return Opacity(
      opacity: widget.enabled ? 1 : 0.45,
      child: AnimatedScale(
        scale: _pressed ? 0.95 : (_hover && widget.enabled ? 1.05 : 1),
        duration: const Duration(milliseconds: 90),
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: s.border, width: s.borderWidth),
            // Sol üstten gelen ışık: üstte açılmış, altta kendi rengine inen dikey geçiş.
            gradient: LinearGradient(
              begin: const Alignment(-0.6, -1),
              end: const Alignment(0.4, 1),
              colors: [Color.alphaBlend(Colors.white.withValues(alpha: 0.10), s.fill), s.fill],
            ),
          ),
          child: InkWell(
            key: ValueKey('vote-${widget.value}'),
            customBorder: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            onHighlightChanged: (v) => setState(() => _pressed = v),
            onHover: (v) => setState(() => _hover = v),
            onTap: widget.enabled
                ? () {
                    HapticFeedback.selectionClick();
                    widget.onTap();
                  }
                : null,
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
                      Icon(s.icon, size: 18, color: s.fg),
                    ],
                  ),
                  Text(s.label,
                      maxLines: 1,
                      style: TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w600, color: s.fg, height: 1.1)),
                ],
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
      vsync: this, duration: const Duration(milliseconds: 900))
    ..repeat(reverse: true);

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
  });
  final Color color;
  final String text;
  final IconData? icon;
  final bool busy;
  final String? action;
  final VoidCallback? onAction;

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
            ],
          ),
        ),
      ),
    );
  }
}
