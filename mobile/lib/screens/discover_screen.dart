import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../app_state.dart';
import '../theme/cosmic_colors.dart';
import '../theme/tini_tokens.dart';
import '../strings.dart';
import '../ui/components/components.dart';
import '../widgets/preview_button.dart';
import '../preview_player.dart' show PreviewMeta;
import '../widgets/studio.dart';
import 'list_screen.dart' show reasonText;

Future<bool> _launchExternal(String url) =>
    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

/// "Keşfet": günün şarkısı vitrini ve takip edilen sanatçıların taze yayınları. Her şey
/// sunucudan gelir; gerekçe hesabın kendisindendir (uydurma yüzde/tür yok).
class DiscoverScreen extends StatefulWidget {
  const DiscoverScreen({
    super.key,
    required this.api,
    required this.state,
    required this.onLogout,
    required this.onOpenRating,
    required this.onOpenProfile,
    this.bottomInset = 0,
    this.launch = _launchExternal,
  });
  final Api api;
  final AppState state;
  final VoidCallback onLogout;
  final VoidCallback onOpenRating;
  final VoidCallback onOpenProfile;
  final double bottomInset;
  final Future<bool> Function(String url) launch;

  @override
  State<DiscoverScreen> createState() => _DiscoverScreenState();
}

/// Yayın tarihini "Bugün", "2 gün önce", "Geçen hafta" gibi okunur hâle getirir.
String relativeDate(String iso, [DateTime? now]) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  final today = now ?? DateTime.now();
  final days = DateTime(
    today.year,
    today.month,
    today.day,
  ).difference(DateTime(d.year, d.month, d.day)).inDays;
  if (days <= 0) return 'Bugün';
  if (days == 1) return 'Dün';
  if (days < 7) return '$days gün önce';
  if (days < 14) return 'Geçen hafta';
  if (days < 60) return '${days ~/ 7} hafta önce';
  return iso;
}

class _DiscoverScreenState extends State<DiscoverScreen> {
  DailySong? _daily;
  bool _dailyLoaded = false;
  String? _dailyNote; // yükleme hatasında profil mesajı yerine gösterilir
  List<NewRelease>? _releases;
  String? _releaseError;
  List<NewTrack> _tracks = const [];
  int _shuffle = 0;
  List<NewRelease> _shown =
      const []; // karışım yalnızca veri/sayaç değişince hesaplanır
  String? _tracksError;
  String? _message;

  @override
  void initState() {
    super.initState();
    _loadDaily();
    _loadReleases();
    _loadTracks();
  }

  /// Yardımcı bölüm: boş yanıt bölümü gizler; hata olursa yeniden dene ile gösterilir.
  Future<void> _loadTracks() async {
    if (_tracksError != null) setState(() => _tracksError = null);
    try {
      final t = await widget.api.newTracks();
      if (mounted) setState(() => _tracks = t);
    } on ApiException catch (e) {
      if (e.status == 401) return widget.onLogout();
      if (mounted) setState(() => _tracksError = e.message);
    } catch (_) {
      if (mounted) setState(() => _tracksError = 'Sunucuya ulaşılamadı');
    }
  }

  Future<void> _loadDaily() async {
    try {
      final d = await widget.api.dailySong();
      if (mounted) {
        setState(() {
          _daily = d;
          _dailyNote = null;
        });
      }
    } on ApiException catch (e) {
      if (e.status == 401) widget.onLogout();
      _dailyNote = (e.status == 404 || e.status == 409)
          ? 'Günün şarkısı şu an hazır değil: ${e.message}'
          : 'Günün şarkısı şu an yüklenemedi. Biraz sonra tekrar dene.';
    } catch (_) {
      // Yardımcı özellik: hata ekranı bozmaz; profil yokmuş gibi yanıltmayız.
      _dailyNote = 'Günün şarkısı şu an yüklenemedi. Biraz sonra tekrar dene.';
    } finally {
      if (mounted) setState(() => _dailyLoaded = true);
    }
  }

  Future<void> _loadReleases() async {
    if (_releaseError != null) setState(() => _releaseError = null);
    try {
      final r = await widget.api.newReleases();
      if (mounted) {
        setState(() {
          _releases = r;
          _reshuffle();
        });
      }
    } on ApiException catch (e) {
      if (e.status == 401) return widget.onLogout();
      if (mounted) {
        setState(
          () => _releaseError = switch (e.status) {
            404 || 409 => 'Önce oylayıp profilini kur; takip ettiğin sanatçıların yayınları burada çıkar.',
            _ => e.message,
          },
        );
      }
    } catch (_) {
      if (mounted) setState(() => _releaseError = 'Sunucuya ulaşılamadı');
    }
  }

  int? _dailyVote;

  Future<void> _voteDaily(DailySong d, int vote) async {
    final track = d.track;
    if (track == null) return;
    try {
      await widget.api.castVote(track, vote);
      widget.state.recordVote(
        QueueItem(track, d.entry.title ?? d.entry.name, d.artists, d.image),
        vote,
      );
      if (mounted) setState(() => _dailyVote = vote);
    } on ApiException catch (e) {
      if (e.status == 401) return widget.onLogout();
      if (mounted) setState(() => _message = e.message);
    } catch (_) {
      if (mounted) setState(() => _message = 'Sunucuya ulaşılamadı');
    }
  }

  Future<void> _openDaily(DailySong d) async {
    try {
      await widget.launch(await widget.api.openUrl(d.listId, d.entry.position));
    } catch (_) {
      if (mounted) setState(() => _message = 'Şarkı açılamadı');
    }
  }

  /// Aynı sıra her zaman aynı karışımı verir (tohum = sayaç); görünen 10 yayını seçer.
  void _reshuffle() {
    final all = [...?_releases];
    if (_shuffle > 0) all.shuffle(math.Random(_shuffle));
    _shown = all.take(10).toList();
  }

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final theme = Theme.of(context);
    final shown = _shown;
    final carousel = shown.take(5).toList();
    final rest = shown.skip(5).toList();
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: EdgeInsets.fromLTRB(
            TiniTokens.pageMargin,
            16,
            TiniTokens.pageMargin,
            widget.bottomInset + 24,
          ),
          children: [
            ListenableBuilder(
              listenable: widget.state,
              builder: (_, _) => Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          TiniStrings.tabDiscover,
                          style: TiniTokens.screenTitle.copyWith(
                            color: TiniTokens.of(context).text,
                          ),
                        ),
                      ],
                    ),
                  ),
                  InkWell(
                    key: const ValueKey('level-badge'),
                    borderRadius: BorderRadius.circular(TiniTokens.rPill),
                    onTap: widget.onOpenProfile,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: c.primary.withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(TiniTokens.rPill),
                        border: Border.all(
                          color: c.primary.withValues(alpha: 0.4),
                        ),
                      ),
                      child: Text(
                        'Seviye ${widget.state.level} · ${widget.state.total} Oy',
                        style: theme.textTheme.labelLarge?.copyWith(
                          color: c.primary,
                          fontWeight: FontWeight.w700,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            ListenableBuilder(
              listenable: widget.state,
              builder: (_, _) => widget.state.pendingVotes > 0
                  ? Padding(
                      padding: const EdgeInsets.only(top: 16),
                      child: _PendingVotesCard(
                        count: widget.state.pendingVotes,
                        onTap: widget.onOpenRating,
                      ),
                    )
                  : const SizedBox.shrink(),
            ),
            const SizedBox(height: TiniTokens.sectionGap),
            const SectionLabel('GÜNÜN TINISI'),
            const SizedBox(height: 10),
            _hero(context),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(_message!),
              ),
            if (_tracks.isNotEmpty || _tracksError != null) ...[
              const SizedBox(height: TiniTokens.sectionGap),
              const SectionLabel('BU HAFTA ÇIKANLAR'),
              const SizedBox(height: 10),
              if (_tracksError != null)
                StateNote.error(_tracksError!, onRetry: _loadTracks)
              else
                for (final t in _tracks.take(10))
                  _TrackRow(api: widget.api, track: t),
            ],
            const SizedBox(height: TiniTokens.sectionGap),
            Row(
              children: [
                const Expanded(
                  child: SectionLabel('YENİ ÇIKANLAR · TAZE KEŞİF'),
                ),
                Tooltip(
                  message: (_releases?.length ?? 0) < 2
                      ? 'Karıştırmak için en az 2 yayın gerekir'
                      : '',
                  child: TextButton.icon(
                    key: const ValueKey('shuffle'),
                    onPressed: (_releases?.length ?? 0) < 2
                        ? null
                        : () => setState(() {
                            _shuffle++;
                            _reshuffle();
                          }),
                    style: TextButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                    ),
                    icon: const Icon(Icons.shuffle_rounded, size: 18),
                    label: const Text('Yenile / Rastgele'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            if (_releases == null && _releaseError == null)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_releaseError != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: StateNote.error(_releaseError!, onRetry: _loadReleases),
              )
            else if (_releases!.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: StateNote.empty(
                  'Henüz yeni yayın yok.',
                  icon: Icons.album_outlined,
                ),
              )
            else
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 320),
                switchInCurve: Curves.easeOutCubic,
                child: Column(
                  key: ValueKey(_shuffle),
                  children: [
                    SizedBox(
                      height: 218,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: carousel.length,
                        separatorBuilder: (_, _) => const SizedBox(width: 14),
                        itemBuilder: (_, i) =>
                            _ReleaseCard(release: carousel[i]),
                      ),
                    ),
                    if (rest.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      const Align(
                        alignment: Alignment.centerLeft,
                        child: SectionLabel('HIZLI KEŞİF'),
                      ),
                      const SizedBox(height: 8),
                      for (final r in rest) _ReleaseRow(release: r),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _hero(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final theme = Theme.of(context);
    final dark = theme.brightness == Brightness.dark;
    final fill = dark ? TiniTokens.heroFillDark : TiniTokens.heroFillLight;
    final edge = dark
        ? (
            TiniTokens.heroEdgeDarkHi.withValues(alpha: 0.45),
            TiniTokens.heroEdgeDarkLo.withValues(alpha: 0.18),
          )
        : (
            TiniTokens.heroEdgeLightHi.withValues(alpha: 0.4),
            TiniTokens.heroEdgeLightLo.withValues(alpha: 0.18),
          );
    final d = _daily;
    return StudioSurface(
      radius: TiniTokens.rHero,
      padding: const EdgeInsets.all(16),
      fill: fill,
      edge: edge,
      child: d == null
          ? Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                children: [
                  const Icon(Icons.wb_sunny_rounded),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      !_dailyLoaded
                          ? 'Günün şarkısı hazırlanıyor…'
                          : (_dailyNote ??
                                'Günün şarkısı için önce oylayıp profilini kur.'),
                      style: theme.textTheme.bodyMedium,
                    ),
                  ),
                ],
              ),
            )
          : _heroBody(context, d, c),
    );
  }

  Widget _heroBody(BuildContext context, DailySong d, TiniCosmicColors c) {
    final theme = Theme.of(context);
    final title = d.entry.title ?? d.entry.name;
    final artist = d.artists.isNotEmpty
        ? d.artists.join(', ')
        : (d.entry.title != null ? d.entry.name : null);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.wb_sunny_rounded, size: 16, color: c.votes[4]!.fg),
            const SizedBox(width: 6),
            const SectionLabel('GÜNÜN ŞARKISI'),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TiniCover(
              seed: '$title|${artist ?? ''}',
              url: d.image,
              size: 76,
              radius: TiniTokens.rCard,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: studioTitle(
                      context,
                      base: theme.textTheme.titleLarge,
                    ),
                  ),
                  if (artist != null)
                    Text(artist, maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 6),
                  // Gerekçe listeden gelir (PPR çapa payları); sonradan uydurulmaz.
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.insights_rounded, size: 14, color: c.primary),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          reasonText(d.entry, top: 2),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        if (d.track != null) ...[
          const SizedBox(height: 14),
          Row(
            children: [
              for (var v = 1; v <= 6; v++) ...[
                if (v > 1) const SizedBox(width: 6),
                Expanded(
                  child: _QuickVote(
                    key: ValueKey('daily-vote-$v'),
                    vote: v,
                    style: c.votes[v]!,
                    selected: _dailyVote == v,
                    onTap: () => _voteDaily(d, v),
                  ),
                ),
              ],
            ],
          ),
          if (_dailyVote != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                'Oyun kaydedildi: $_dailyVote · ${c.votes[_dailyVote]!.label}',
                style: theme.textTheme.labelSmall,
              ),
            ),
        ],
        const SizedBox(height: 14),
        Row(
          children: [
            if (d.entry.artistId != null) ...[
              PreviewButton(
                key: const ValueKey('daily-preview'),
                api: widget.api,
                previewKey: 'daily-${d.listId}',
                artistId: d.entry.artistId,
                trackId: d.track,
                meta: PreviewMeta(
                  title: title,
                  artist: artist ?? '',
                  image: d.image,
                  track: d.track,
                ),
              ),
              const SizedBox(width: 8),
            ],
            Expanded(
              flex: 2,
              child: StudioButton(
                key: const ValueKey('daily-open'),
                dense: true,
                onPressed: () => _openDaily(d),
                icon: Icons.play_arrow_rounded,
                label: 'Dinle',
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              flex: 3,
              child: StudioButton(
                key: const ValueKey('daily-rate'),
                dense: true,
                primary: false,
                onPressed: widget.onOpenRating,
                icon: Icons.tune_rounded,
                label: 'Oylamaya Geç',
              ),
            ),
          ],
        ),
      ],
    );
  }
}

/// Günün şarkısı için küçük 1–6 oy düğmesi (oylama ekranındaki renklerle).
class _QuickVote extends StatelessWidget {
  const _QuickVote({
    super.key,
    required this.vote,
    required this.style,
    required this.selected,
    required this.onTap,
  });
  final int vote;
  final VoteStyle style;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: '$vote · ${style.label}',
      child: Hoverable(
        scale: 1.06,
        child: Material(
          color: Colors.transparent,
          child: Ink(
            height: 44,
            decoration: BoxDecoration(
              color: selected
                  ? style.border.withValues(alpha: 0.35)
                  : style.fill,
              borderRadius: BorderRadius.circular(TiniTokens.rCard),
              border: Border.all(
                color: style.border,
                width: selected ? 2 : style.borderWidth,
              ),
            ),
            child: InkWell(
              borderRadius: BorderRadius.circular(TiniTokens.rCard),
              onTap: onTap,
              child: Center(
                child: Text(
                  '$vote',
                  style: TiniTokens.bodyStrong.copyWith(
                    color: style.fg,
                    fontWeight: FontWeight.w800,
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

class _ReleaseCard extends StatelessWidget {
  const _ReleaseCard({required this.release});
  final NewRelease release;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    // Tasarımdaki gibi: çerçevesiz büyük kapak, altında kalın ad ve soluk alt satır.
    return SizedBox(
      width: 150,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Stack(
            children: [
              TiniCover(
                seed: '${release.title}|${release.artist}',
                url: release.cover,
                size: 150,
                radius: TiniTokens.rCard,
              ),
              const Positioned(left: 8, top: 8, child: NewBadge()),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            release.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TiniTokens.bodyStrong.copyWith(color: t.text),
          ),
          Text(
            '${release.artist} · ${relativeDate(release.released)}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TiniTokens.caption.copyWith(color: t.muted),
          ),
        ],
      ),
    );
  }
}

/// Bu haftanın tek bir parçası: kapak yer tutucusu, ad, sanatçı · yayın · tarih ve play tuşu.
class _TrackRow extends StatelessWidget {
  const _TrackRow({required this.api, required this.track});
  final Api api;
  final NewTrack track;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: StudioSurface(
        radius: TiniTokens.rCard,
        padding: const EdgeInsets.fromLTRB(8, 8, 4, 8),
        child: Row(
          children: [
            TiniCover(
              seed: '${track.title}|${track.artist}',
              url: track.cover,
              size: 48,
              radius: TiniTokens.rCoverSmall,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    track.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: studioTitle(
                      context,
                      base: theme.textTheme.titleSmall,
                    ),
                  ),
                  Text(
                    '${track.artist} · ${track.release} · ${relativeDate(track.released)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            PreviewButton(
              key: ValueKey('new-track-${track.deezerId}'),
              api: api,
              previewKey: 'new-track-${track.deezerId}',
              deezerId: track.deezerId,
              meta: PreviewMeta(
                title: track.title,
                artist: track.artist,
                image: track.cover,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReleaseRow extends StatelessWidget {
  const _ReleaseRow({required this.release});
  final NewRelease release;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: StudioSurface(
        radius: TiniTokens.rCard,
        padding: const EdgeInsets.all(8),
        child: Row(
          children: [
            TiniCover(
              seed: '${release.title}|${release.artist}',
              url: release.cover,
              size: 48,
              radius: TiniTokens.rCoverSmall,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    release.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: studioTitle(
                      context,
                      base: theme.textTheme.titleSmall,
                    ),
                  ),
                  Text(
                    '${release.artist} · ${release.type}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(
              relativeDate(release.released),
              style: theme.textTheme.labelSmall,
            ),
          ],
        ),
      ),
    );
  }
}

/// Kuyrukta bekleyen oyları gösteren kart; "Oyla" Oyla sekmesine götürür.
class _PendingVotesCard extends StatelessWidget {
  const _PendingVotesCard({required this.count, required this.onTap});
  final int count;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    // Tahmini süre: oy başına ~20 sn (yaklaşık değer, sunucudan gelmez).
    final minutes = math.max(1, (count / 3).round());
    return Container(
      key: const ValueKey('pending-votes-card'),
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      decoration: BoxDecoration(
        color: t.surface1,
        borderRadius: BorderRadius.circular(TiniTokens.rCard),
        border: Border.all(color: t.line),
      ),
      child: Row(
        children: [
          // Üst üste binen üç kapak: sıradaki kartların önizlemesi.
          SizedBox(
            width: 64,
            height: 34,
            child: Stack(
              children: [
                for (final (i, s) in const ['kuyruk-1', 'kuyruk-2', 'kuyruk-3'].indexed)
                  Positioned(
                    left: i * 15.0,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(
                          TiniTokens.rCoverSmall,
                        ),
                        border: Border.all(color: t.surface1, width: 2),
                      ),
                      child: TiniCover(seed: s, size: 34),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  TiniStrings.pendingVotesCard(count),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TiniTokens.bodyStrong.copyWith(color: t.text),
                ),
                Text(
                  '~$minutes dk · profilini netleştirir',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TiniTokens.caption.copyWith(color: t.muted),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          FilledButton(
            key: const ValueKey('pending-votes-rate'),
            onPressed: onTap,
            style: FilledButton.styleFrom(
              backgroundColor: dark ? t.text : TiniTokens.onLightFill,
              foregroundColor: dark ? TiniTokens.onLightFill : Colors.white,
              shape: const StadiumBorder(),
            ),
            child: const Text(TiniStrings.rate),
          ),
        ],
      ),
    );
  }
}
