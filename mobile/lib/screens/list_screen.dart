import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show PlatformException;
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../strings.dart';
import '../theme/cosmic_colors.dart';
import '../theme/tini_tokens.dart';
import '../ui/components/components.dart';
import '../widgets/artist_avatar.dart';
import '../widgets/studio.dart';

/// Gerekçe cümlesi: en büyük paylı çapalar, yüzdeyle (hesabın kendisinden gelir).
String reasonText(ListEntry e, {int top = 3}) {
  // Gerekçe uydurulmaz: hesap çapa döndürmediyse bunu açıkça söyleriz.
  if (e.reasons.isEmpty) return TiniStrings.noAnchorReason;
  final sorted = [...e.reasons]..sort((a, b) => b.share.compareTo(a.share));
  final parts = sorted
      .take(top)
      .map(
        (r) =>
            '${r.isAnchor ? '★ ' : ''}${r.seedName} %${(r.share * 100).round()}',
      );
  return 'Sevdiğin sanatçılara benzediği için: ${parts.join(', ')}';
}

List<Reason> _topReasons(ListEntry e, [int n = 3]) => ([
  ...e.reasons,
]..sort((a, b) => b.share.compareTo(a.share))).take(n).toList();

Future<bool> _launchExternal(String url) =>
    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

class ListScreen extends StatefulWidget {
  const ListScreen({
    super.key,
    required this.api,
    this.onLogout,
    this.launch = _launchExternal,
    this.embedded = false,
  });
  final Api api;
  final VoidCallback? onLogout;

  /// Kabuk içinde sekme olarak: üst çubuk yok, alt menü için boşluk var.
  final bool embedded;

  /// Testte değiştirilebilir; varsayılan servis uygulamasını açar.
  final Future<bool> Function(String url) launch;

  @override
  State<ListScreen> createState() => _ListScreenState();
}

class _ListScreenState extends State<ListScreen> {
  DiscoveryList? _list;
  bool _busy = false;
  SaveState _spotify = SaveState.idle;
  String? _error;
  VoidCallback?
  _retry; // üstteki hata bandının "Yeniden dene"si: hatayı doğuran işlem
  int _gen =
      0; // liste nesli: eski listenin geç gelen başlıkları yenisine yazılmasın
  final Map<int, String?> _photos = {};
  final Map<int, String> _titles = {};

  @override
  void initState() {
    super.initState();
    // Sekme olarak açılınca ölü ekran yerine ilk listeyi kendiliğinden üret.
    if (widget.embedded) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _list == null && !_busy) _generate();
      });
    }
  }

  /// Önbellekte olmayan sanatçı portrelerini arka planda ister; kapaklar geldikçe güncellenir.
  void _loadPhotos(DiscoveryList l) {
    final missing = [
      for (final e in l.items)
        if (e.artistId != null && e.artistImage == null) e.artistId!,
    ];
    loadArtistPhotos(widget.api, missing, (found) {
      if (mounted) setState(() => _photos.addAll(found));
    }, alive: () => mounted);
  }

  /// Parça adı gelmeyen sanatçı öğeleri için adı arka planda, sırayla çözer (sunucu hız sınırlı).
  Future<void> _loadTitles(DiscoveryList l, int gen) async {
    for (final e in l.items) {
      if (gen != _gen) return;
      if (e.title != null || e.release != null || e.artistId == null) continue;
      try {
        final t = await widget.api.previewTitle(e.artistId!);
        if (!mounted || gen != _gen) return;
        if (t != null) setState(() => _titles[e.position] = t);
      } catch (_) {
        if (!mounted) return;
      }
    }
  }

  Future<void> _generate() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final l = await widget.api.generateList();
      final gen = ++_gen;
      if (mounted) {
        setState(() {
          _list = l;
          _titles.clear();
          _spotify = SaveState.idle;
        });
      }
      _loadPhotos(l);
      unawaited(_loadTitles(l, gen));
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted && Navigator.of(context).canPop()) {
          Navigator.of(context).pop();
        }
        return widget.onLogout?.call();
      }
      if (mounted) {
        setState(() {
          _error = e.status == 404 ? TiniStrings.noProfile : e.message;
          _retry = _generate;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = TiniStrings.unreachable;
          _retry = _generate;
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _saveSpotify() async {
    if (_spotify == SaveState.notConnected) return _connectSpotify();
    setState(() {
      _spotify = SaveState.saving;
      _error = null;
    });
    try {
      final r = await widget.api.exportList(_list!.id);
      if (!mounted) return;
      final named = r.skippedNames.where((n) => n.isNotEmpty).toList();
      final detail = named.isEmpty ? '' : ' (${named.join(', ')})';
      final msg = r.added == 0
          ? '${TiniStrings.noPlayableTracks}$detail'
          : TiniStrings.savedToSpotify(r.added, r.skipped, detail);
      setState(
        () => _spotify = r.added == 0 ? SaveState.idle : SaveState.saved,
      );
      _toast(msg);
    } on ApiException catch (ex) {
      if (!mounted) return;
      setState(() {
        if (ex.status == 409) {
          _spotify = SaveState.notConnected;
          _error = TiniStrings.reconnectSpotify;
        } else {
          _spotify = SaveState.idle;
          _error = ex.message;
        }
        _retry = _saveSpotify;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _spotify = SaveState.idle;
        _error = TiniStrings.unreachable;
        _retry = _saveSpotify;
      });
    }
  }

  /// Bağlı değilse bağlama akışı: yetkilendirme sayfası servis uygulamasında/tarayıcıda açılır.
  Future<void> _connectSpotify() async {
    try {
      final url = await widget.api.spotifyAuthorizeUrl();
      await widget.launch(url);
    } on ApiException catch (ex) {
      _toast(ex.message);
    } on PlatformException {
      _toast(TiniStrings.spotifyOpenFailed);
    } catch (_) {
      _toast(TiniStrings.unreachable);
    }
  }

  Future<void> _open(ListEntry e) async {
    try {
      final url = await widget.api.openUrl(_list!.id, e.position);
      var opened = false;
      try {
        opened = await widget.launch(url);
      } on PlatformException {
        // Uygulama kurulu değilse launchUrl istisna fırlatabilir.
      }
      if (!opened) _toast(TiniStrings.spotifyOpenFailed);
    } on ApiException catch (ex) {
      _toast(ex.status == 409 ? TiniStrings.connectSpotifyFirst : ex.message);
    } catch (_) {
      _toast(TiniStrings.unreachable);
    }
  }

  /// Gerekçe itirazı: tek dokunuşla tüm gerekçe için kaydedilir (algoritmaya etkisi sonraki faz).
  Future<bool> _object(ListEntry e) async {
    try {
      await widget.api.reasonFeedback(_list!.id, e.position);
      _toast(TiniStrings.objectionSaved);
      return true;
    } on ApiException catch (ex) {
      _toast(ex.message);
    } catch (_) {
      _toast(TiniStrings.unreachable);
    }
    return false;
  }

  /// Eylemlerin hatası, kullanıcının baktığı yerde (sayfa tepesindeki bant ekran dışında kalır).
  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(content: Text(msg)));
  }

  String? _portrait(ListEntry e) => _photos[e.artistId] ?? e.artistImage;

  /// Parça/yayın kapağı; yoksa (ya da yüklenemezse) sanatçı portresi.
  String? _cover(ListEntry e) => e.image ?? _portrait(e);

  /// Asıl kapak varsa ve yüklenemezse portre devreye girer.
  String? _coverFallback(ListEntry e) => e.image == null ? null : _portrait(e);

  _Shown _shown(ListEntry e) {
    final song = e.title ?? _titles[e.position];
    if (e.release != null) {
      return _Shown(e.release!.title, e.name, TrackSlot.fresh, true);
    }
    if (song != null) return _Shown(song, e.name, TrackSlot.explore, false);
    return _Shown(e.name, '', TrackSlot.explore, false);
  }

  void _showWhy(ListEntry e) {
    final t = TiniTokens.of(context);
    final shown = _shown(e);
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: false,
      backgroundColor: t.surface1,
      barrierColor: t.scrim,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height - 112,
      ),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(TiniTokens.rSheet),
        ),
      ),
      builder: (_) => _WhySheet(
        entry: e,
        shown: shown,
        coverUrl: _cover(e),
        coverFallbackUrl: _coverFallback(e),
        onObject: () => _object(e),
        onOpen: () => _open(e),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final list = _list;
    final c = TiniCosmicColors.of(context);
    final topPad = widget.embedded
        ? MediaQuery.paddingOf(context).top + 16
        : 8.0;
    return Scaffold(
      backgroundColor: widget.embedded ? Colors.transparent : c.scaffold,
      appBar: widget.embedded
          ? null
          : AppBar(
              backgroundColor: Colors.transparent,
              scrolledUnderElevation: 0,
            ),
      extendBodyBehindAppBar: false,
      body: ListView(
        padding: EdgeInsets.only(bottom: widget.embedded ? 96 : 24),
        children: [
          _Header(
            list: list,
            topPad: topPad,
            covers: [
              if (list != null)
                for (final e in list.items.take(4))
                  (
                    seed: '${_shown(e).title}|${e.name}',
                    url: _cover(e),
                    fallback: _coverFallback(e),
                  ),
            ],
            title: widget.embedded && list == null
                ? TiniStrings.listEmbeddedTitle
                : TiniStrings.listTitle,
            freshCount: list?.items.where((e) => e.release != null).length ?? 0,
            busy: _busy && _spotify != SaveState.saving,
            spotify: _spotify,
            onGenerate: _busy ? null : _generate,
            onSaveSpotify: _list == null ? null : _saveSpotify,
            onSaveApple: () => _toast(TiniStrings.appleNotAvailable),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              TiniTokens.listMargin,
              12,
              TiniTokens.listMargin,
              0,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_error != null)
                  StateNote.error(
                    _error!,
                    onRetry: _busy ? null : (_retry ?? _generate),
                  ),
                if (_busy && list == null)
                  for (var i = 0; i < 6; i++)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 8),
                      child: SkeletonCard(height: 66),
                    ),
                if (list != null && list.items.isEmpty)
                  const StateNote.empty(
                    TiniStrings.listEmpty,
                    icon: Icons.queue_music_rounded,
                  ),
                if (list != null)
                  for (final (i, e) in list.items.indexed)
                    StaggerIn(
                      key: ValueKey('${list.id}-${e.position}'),
                      index: i,
                      child: Builder(
                        builder: (_) {
                          final s = _shown(e);
                          final top = _topReasons(e, 1);
                          return TrackRow(
                            key: ValueKey('track-${list.id}-${e.position}'),
                            title: s.title,
                            artist: s.artist,
                            slot: s.slot,
                            isNew: s.isNew,
                            coverSeed: '${s.title}|${e.name}',
                            coverUrl: _cover(e),
                            coverFallbackUrl: _coverFallback(e),
                            reason: top.isEmpty
                                ? TiniStrings.noAnchorReason
                                : TiniStrings.reasonShort(
                                    top.first.seedName,
                                    (top.first.share * 100).round(),
                                  ),
                            onTap: () => _showWhy(e),
                          );
                        },
                      ),
                    ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Satırda gösterilen başlık/sanatçı ve slot (arayüz sunumu; veri uydurmaz).
class _Shown {
  const _Shown(this.title, this.artist, this.slot, this.isNew);
  final String title;
  final String artist;
  final TrackSlot slot;
  final bool isNew;
}

/// Listeye göre renklenen gradyan başlık: 2×2 kapak kolajı, ad, alt başlık, kaydet düğmeleri.
class _Header extends StatelessWidget {
  const _Header({
    required this.list,
    required this.topPad,
    required this.covers,
    required this.title,
    required this.freshCount,
    required this.busy,
    required this.spotify,
    required this.onGenerate,
    required this.onSaveSpotify,
    required this.onSaveApple,
  });
  final DiscoveryList? list;
  final double topPad;
  final List<({String seed, String? url, String? fallback})> covers;
  final String title;
  final int freshCount;
  final bool busy;
  final SaveState spotify;
  final VoidCallback? onGenerate;
  final VoidCallback? onSaveSpotify;
  final VoidCallback onSaveApple;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final l = list;
    final (a, _) = TiniCover.colorsFor('list-${l?.id ?? 0}');
    final tint = Color.alphaBlend(a.withValues(alpha: 0.28), t.bg);
    final hasItems = l != null && l.items.isNotEmpty;
    final n = l?.items.length ?? 0;
    final explore = n - freshCount;
    return Container(
      padding: EdgeInsets.fromLTRB(
        TiniTokens.pageMargin,
        topPad,
        TiniTokens.pageMargin,
        20,
      ),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            tint,
            Color.alphaBlend(a.withValues(alpha: 0.10), t.bg),
            t.bg,
          ],
        ),
      ),
      child: Column(
        children: [
          if (hasItems) ...[
            _Collage(covers: covers),
            const SizedBox(height: 16),
          ],
          Text(
            title,
            textAlign: TextAlign.center,
            style: TiniTokens.screenTitle.copyWith(color: t.text),
          ),
          if (hasItems) ...[
            const SizedBox(height: 4),
            Text(
              TiniStrings.listForYou(n),
              style: TiniTokens.secondary.copyWith(color: t.muted),
            ),
            const SizedBox(height: 2),
            Text(
              [
                if (explore > 0) '${TiniStrings.slotExplore} $explore',
                if (freshCount > 0) '${TiniStrings.slotFresh} $freshCount',
              ].join(' · '),
              style: TiniTokens.caption.copyWith(color: t.muted2),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ServiceSaveButton(
                    key: const ValueKey('save-apple'),
                    service: ServiceKind.apple,
                    state: SaveState.notConnected,
                    compact: true,
                    onPressed: onSaveApple,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ServiceSaveButton(
                    key: const ValueKey('save-spotify'),
                    service: ServiceKind.spotify,
                    state: spotify,
                    compact: true,
                    onPressed: onSaveSpotify,
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 12),
          StudioButton(
            icon: l == null
                ? Icons.auto_awesome_rounded
                : Icons.refresh_rounded,
            label: l == null ? TiniStrings.generate : TiniStrings.regenerate,
            busy: busy,
            primary: l == null,
            dense: l != null,
            onPressed: onGenerate,
          ),
        ],
      ),
    );
  }
}

/// 190 pt'lik 2×2 kapak kolajı; eksik kapaklar kararlı yedek gradyanla dolar.
class _Collage extends StatelessWidget {
  const _Collage({required this.covers});
  final List<({String seed, String? url, String? fallback})> covers;

  @override
  Widget build(BuildContext context) {
    const size = 190.0;
    const gap = 2.0;
    const cell = (size - gap) / 2;
    Widget at(int i) => i < covers.length
        ? TiniCover(
            seed: covers[i].seed,
            url: covers[i].url,
            fallbackUrl: covers[i].fallback,
            size: cell,
            radius: 0,
          )
        : SizedBox(
            width: cell,
            height: cell,
            child: TiniCover(seed: 'collage-$i', size: cell, radius: 0),
          );
    return ClipRRect(
      borderRadius: BorderRadius.circular(TiniTokens.rCard),
      child: SizedBox(
        key: const ValueKey('list-collage'),
        width: size,
        height: size,
        child: Column(
          children: [
            Row(
              children: [
                at(0),
                const SizedBox(width: gap),
                at(1),
              ],
            ),
            const SizedBox(height: gap),
            Row(
              children: [
                at(2),
                const SizedBox(width: gap),
                at(3),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Gerekçe paneli: kapak, başlık, slot, "neden bu şarkı?" cümlesi ve en büyük paylı çapalar.
class _WhySheet extends StatefulWidget {
  const _WhySheet({
    required this.entry,
    required this.shown,
    required this.coverUrl,
    this.coverFallbackUrl,
    required this.onObject,
    required this.onOpen,
  });
  final ListEntry entry;
  final _Shown shown;
  final String? coverUrl;
  final String? coverFallbackUrl;
  final Future<bool> Function() onObject;
  final VoidCallback onOpen;

  @override
  State<_WhySheet> createState() => _WhySheetState();
}

class _WhySheetState extends State<_WhySheet> {
  bool _saving = false;
  bool _objected = false;

  Future<void> _object() async {
    setState(() => _saving = true);
    final ok = await widget.onObject();
    if (mounted) {
      setState(() {
        _saving = false;
        _objected = ok;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final e = widget.entry;
    final s = widget.shown;
    final top = _topReasons(e);
    final total = top.fold<double>(0, (a, r) => a + r.share);
    final year = e.release != null && e.release!.released.length >= 4
        ? e.release!.released.substring(0, 4)
        : null;
    final sub = [
      if (s.artist.isNotEmpty) s.artist,
      ?year,
    ].join(' · ');
    return SafeArea(
      top: false,
      child: SingleChildScrollView(
        key: const ValueKey('why-sheet'),
        padding: const EdgeInsets.fromLTRB(
          TiniTokens.pageMargin,
          10,
          TiniTokens.pageMargin,
          20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: t.line,
                  borderRadius: BorderRadius.circular(TiniTokens.rPill),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                TiniCover(
                  seed: '${s.title}|${e.name}',
                  url: widget.coverUrl,
                  fallbackUrl: widget.coverFallbackUrl,
                  size: 64,
                  radius: TiniTokens.rCard,
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        s.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TiniTokens.cardTitle.copyWith(color: t.text),
                      ),
                      if (sub.isNotEmpty)
                        Text(
                          sub,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TiniTokens.secondary.copyWith(color: t.muted),
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                _SlotPill(slot: s.slot),
              ],
            ),
            const SizedBox(height: 22),
            Text(
              TiniStrings.whyTitle,
              style: TiniTokens.section.copyWith(color: t.text),
            ),
            const SizedBox(height: 6),
            if (top.isEmpty)
              Text(
                TiniStrings.noAnchorReason,
                style: TiniTokens.body.copyWith(color: t.muted),
              )
            else ...[
              Text(
                TiniStrings.whySentence((total * 100).round(), top.length),
                style: TiniTokens.body.copyWith(color: t.muted),
              ),
              const SizedBox(height: 14),
              for (final r in top)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: AnchorRow(
                    title: r.seedName,
                    vote: r.isAnchor ? 6 : null,
                    share: r.share,
                  ),
                ),
            ],
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    key: const ValueKey('object-similarity'),
                    onPressed: _saving || _objected ? null : _object,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: TiniVote.c1,
                      disabledForegroundColor: t.muted2,
                      side: BorderSide(color: _objected ? t.line : TiniVote.c1),
                      minimumSize: const Size.fromHeight(50),
                      shape: const StadiumBorder(),
                      textStyle: TiniTokens.bodyStrong.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    child: Text(
                      _objected
                          ? TiniStrings.objectionSaved
                          : TiniStrings.objectSimilarity,
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton(
                    key: const ValueKey('open-in-spotify'),
                    onPressed: widget.onOpen,
                    style: FilledButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: TiniTokens.onLightFill,
                      minimumSize: const Size.fromHeight(50),
                      shape: const StadiumBorder(),
                      textStyle: TiniTokens.bodyStrong.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    child: const Text(
                      TiniStrings.openInSpotify,
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SlotPill extends StatelessWidget {
  const _SlotPill({required this.slot});
  final TrackSlot slot;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: slot.color,
        borderRadius: BorderRadius.circular(TiniTokens.rPill),
      ),
      child: Text(
        slot.label,
        style: TiniTokens.bodyStrong.copyWith(
          color: TiniTokens.onLightFill,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
