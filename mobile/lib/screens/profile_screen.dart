import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart' show ImageSource;

import '../api.dart';
import '../app_state.dart';
import '../badges.dart';
import '../profile_photo.dart';
import '../strings.dart';
import '../theme/tini_tokens.dart';
import '../ui/components/components.dart';
import '../widgets/info_sheet.dart';
import '../widgets/studio.dart' show Haptics, SkeletonCard, StateNote;
import 'home_screen.dart';
import 'intro_screen.dart';
import 'tracks_screen.dart' show LaterScreen;

/// Profil sekmesi: kullanıcı kartı, zevk modları, oy dağılımı, kaçınma bölgesi ve oy geçmişi.
/// Oy sayıları [AppState]'ten, mod payları ve kaçınma sayıları sunucudaki son profilden gelir.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.api,
    required this.state,
    required this.onLogout,
    this.themeMode = ThemeMode.system,
    this.onThemeChanged,
  });
  final Api api;
  final AppState state;
  final VoidCallback onLogout;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode>? onThemeChanged;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  TasteProfile? _profile;
  bool _profileLoading = true;
  String? _profileError;
  File? _photo;
  late int _seenRevision;

  @override
  void initState() {
    super.initState();
    _seenRevision = widget.state.profileRevision;
    widget.state.addListener(_onState);
    _loadProfile();
    // Önce yerel kare hemen görünür, sonra sunucuyla sessizce eşitlenir.
    ProfilePhotoStore.load().then((f) {
      if (mounted && f != null) setState(() => _photo = f);
    });
    ProfilePhotoStore.sync(widget.api).then((f) {
      if (mounted) setState(() => _photo = f);
    });
  }

  /// Profil başka bir sekmeden yeniden kurulunca sunucudaki yeni profil okunur.
  void _onState() {
    if (widget.state.profileRevision == _seenRevision) return;
    _seenRevision = widget.state.profileRevision;
    _loadProfile();
  }

  @override
  void dispose() {
    widget.state.removeListener(_onState);
    super.dispose();
  }

  /// Aşağı çekince oy özeti ve zevk profili sunucudan yeniden okunur.
  Future<void> _refresh() async {
    try {
      await Future.wait([widget.state.load(), _loadProfile()]);
    } on ApiException catch (e) {
      if (e.status == 401) return widget.onLogout();
      _toast(e.message);
    } catch (_) {
      _toast(TiniStrings.unreachable);
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _editPhoto() async {
    final t = TiniTokens.of(context);
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: t.sheet,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(TiniTokens.rSheet)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            ListTile(
              key: const ValueKey('photo-gallery'),
              leading: const Icon(Icons.photo_library_rounded),
              title: const Text(TiniStrings.photoGallery),
              onTap: () => Navigator.pop(ctx, 'gallery'),
            ),
            ListTile(
              key: const ValueKey('photo-camera'),
              leading: const Icon(Icons.photo_camera_rounded),
              title: const Text(TiniStrings.photoCamera),
              onTap: () => Navigator.pop(ctx, 'camera'),
            ),
            if (_photo != null)
              ListTile(
                key: const ValueKey('photo-remove'),
                leading: const Icon(Icons.delete_outline_rounded),
                title: const Text(TiniStrings.photoRemove),
                onTap: () => Navigator.pop(ctx, 'remove'),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (action == null) return;
    if (action == 'remove') {
      if (mounted) setState(() => _photo = null);
      await ProfilePhotoStore.remove(widget.api);
      return;
    }
    final f = await ProfilePhotoStore.pick(
      action == 'camera' ? ImageSource.camera : ImageSource.gallery,
    );
    if (mounted && f != null) setState(() => _photo = f);
    if (f != null) await ProfilePhotoStore.upload(widget.api);
  }

  /// Profil yoksa (404) `null` döner ve bölümler boş durumda kalır; sunucuya ulaşılamazsa
  /// "profil yok" gibi görünmesin diye hata ayrı tutulur ve yeniden deneme sunulur.
  Future<void> _loadProfile() async {
    if (_profileError != null) setState(() => _profileError = null);
    String? error;
    try {
      final p = await widget.api.tasteProfile();
      if (mounted) setState(() => _profile = p);
    } on ApiException catch (e) {
      if (e.status == 401) return widget.onLogout();
      error = e.message;
    } catch (_) {
      error = TiniStrings.unreachable;
    }
    if (mounted) {
      setState(() {
        _profileLoading = false;
        _profileError = error;
      });
    }
  }

  static String _date(DateTime d) {
    final l = d.toLocal();
    return '${l.day.toString().padLeft(2, '0')}.${l.month.toString().padLeft(2, '0')}.${l.year}';
  }

  /// Üstte açık sayfa varken çıkış yapılırsa yığın temizlenir (giriş ekranı üstte kalmasın).
  void _logout(BuildContext context) {
    Navigator.of(context).popUntil((r) => r.isFirst);
    widget.onLogout();
  }

  void _openSettings(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => HomeScreen(
          api: widget.api,
          onLogout: () => _logout(context),
          themeMode: widget.themeMode,
          onThemeChanged: widget.onThemeChanged,
        ),
      ),
    );
  }

  Future<void> _change(BuildContext context, HistoryItem h) async {
    final t = TiniTokens.of(context);
    final picked = await showModalBottomSheet<int>(
      context: context,
      backgroundColor: t.surface1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(TiniTokens.rSheet),
        ),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: Text(
                h.title ?? TiniStrings.trackFallback(h.track),
                style: TiniTokens.cardTitle.copyWith(color: t.text),
              ),
            ),
            for (var v = 1; v <= 6; v++)
              ListTile(
                leading: VoteBadge(vote: v),
                title: Text(
                  '$v · ${TiniStrings.voteLabels[v - 1]}',
                  style: TiniTokens.bodyStrong.copyWith(color: t.text),
                ),
                selected: v == h.vote,
                onTap: () => Navigator.pop(ctx, v),
              ),
          ],
        ),
      ),
    );
    if (picked == null || picked == h.vote) return;
    try {
      await widget.api.castVote(
        h.track,
        picked,
      ); // yeni bir olay; eskisi silinmez
      widget.state.recordChange(h, picked);
      Haptics.success();
    } on ApiException catch (e) {
      Haptics.warn();
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (_) {
      Haptics.warn();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text(TiniStrings.unreachable)),
        );
      }
    }
  }

  List<ModeData> _modes() {
    final w = _profile?.clusterWeights ?? const <double>[];
    final names = _profile?.clusterNames ?? const <String?>[];
    final tags = _profile?.clusterTags ?? const <List<String>>[];
    final sum = w.fold<double>(0, (a, b) => a + b);
    if (sum <= 0) return const [];
    return [
      for (var i = 0; i < w.length; i++)
        if (w[i] > 0)
          // Ad ve etiketler sunucudan gelir (yoksa "Mod N"); simge ve renk sırayla verilir.
          ModeData(
            name: (i < names.length ? names[i] : null) ?? TiniStrings.modeName(i + 1),
            tags: i < tags.length ? tags[i] : const [],
            share: w[i] / sum,
            kind: ModeKind.values[i % ModeKind.values.length],
          ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: ListenableBuilder(
          listenable: widget.state,
          builder: (context, _) {
            final state = widget.state;
            final counts = [for (var v = 1; v <= 6; v++) state.counts[v] ?? 0];
            final modes = _modes();
            return RefreshIndicator(
              key: const ValueKey('profile-refresh'),
              onRefresh: _refresh,
              child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(
                TiniTokens.pageMargin,
                14,
                TiniTokens.pageMargin,
                80 + 24,
              ),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        TiniStrings.profileTitle,
                        style: TiniTokens.screenTitle.copyWith(color: t.text),
                      ),
                    ),
                    IconButton(
                      key: const ValueKey('open-settings'),
                      tooltip: TiniStrings.settings,
                      onPressed: () => _openSettings(context),
                      icon: Icon(Icons.settings_rounded, color: t.muted),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                _UserCard(state: state, photo: _photo, onEditPhoto: _editPhoto),
                const SizedBox(height: TiniTokens.sectionGap),
                Text(
                  TiniStrings.tasteModes,
                  style: TiniTokens.section.copyWith(color: t.text),
                ),
                const SizedBox(height: 10),
                if (_profileError != null && _profile == null)
                  StateNote.error(
                    _profileError!,
                    key: const ValueKey('profile-error'),
                    onRetry: _loadProfile,
                  )
                else if (_profileLoading && _profile == null)
                  const SkeletonCard(key: ValueKey('profile-loading'))
                else if (modes.isEmpty)
                  const StateNote.empty(
                    TiniStrings.modesEmpty,
                    key: ValueKey('modes-empty'),
                    icon: Icons.bubble_chart_outlined,
                  )
                else
                  ModeBubbleField(
                    key: const ValueKey('mode-field'),
                    modes: modes,
                    height: 220,
                  ),
                if (_profile?.version != null && _profile?.createdAt != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      TiniStrings.profileStamp(_profile!.version!, _date(_profile!.createdAt!)),
                      key: const ValueKey('profile-stamp'),
                      style: TiniTokens.body.copyWith(color: t.muted),
                    ),
                  ),
                const SizedBox(height: TiniTokens.sectionGap),
                Text(
                  TiniStrings.yourVotes,
                  style: TiniTokens.section.copyWith(color: t.text),
                ),
                const SizedBox(height: 12),
                _Surface(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      VoteDistributionChart(counts: counts),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          for (var v = 1; v <= 6; v++) ...[
                            if (v > 1) const SizedBox(width: 14),
                            Expanded(
                              child: Text(
                                '${counts[v - 1]}',
                                key: ValueKey('count-$v'),
                                textAlign: TextAlign.center,
                                style: TiniTokens.secondary.copyWith(
                                  color: t.muted,
                                  fontFeatures: const [
                                    FontFeature.tabularFigures(),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        state.total >= tourVotes
                            ? TiniStrings.calibrationDone
                            : TiniStrings.calibrationLeft(
                                tourVotes - state.total,
                              ),
                        key: const ValueKey('calibration-note'),
                        style: TiniTokens.secondary.copyWith(color: t.muted),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: TiniTokens.sectionGap),
                Builder(builder: (_) {
                  final badges = computeBadges(total: state.total, counts: counts);
                  final earned = badges.where((b) => b.earned).length;
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              TiniStrings.badgesTitle,
                              style: TiniTokens.section.copyWith(color: t.text),
                            ),
                          ),
                          Text(
                            TiniStrings.badgeCount(earned, badges.length),
                            key: const ValueKey('badge-count'),
                            style: TiniTokens.secondary.copyWith(
                              color: t.muted,
                              fontFeatures: const [FontFeature.tabularFigures()],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      BadgeShelf(badges: badges),
                    ],
                  );
                }),
                const SizedBox(height: TiniTokens.sectionGap),
                Row(
                  children: [
                    Text(
                      TiniStrings.avoidZone,
                      style: TiniTokens.section.copyWith(color: t.text),
                    ),
                    const InfoIconButton(
                      title: TiniStrings.avoidInfoTitle,
                      body: TiniStrings.avoidInfoBody,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _AvoidCard(profile: _profile),
                const SizedBox(height: TiniTokens.sectionGap),
                Text(
                  TiniStrings.recentVotes,
                  style: TiniTokens.section.copyWith(color: t.text),
                ),
                const SizedBox(height: 10),
                if (state.recent.isEmpty)
                  const StateNote.empty(
                    TiniStrings.noVotesYet,
                    icon: Icons.how_to_vote_outlined,
                  ),
                for (final h in state.recent)
                  _HistoryRow(item: h, onTap: () => _change(context, h)),
                const SizedBox(height: TiniTokens.sectionGap),
                Text(
                  TiniStrings.myLists,
                  style: TiniTokens.section.copyWith(color: t.text),
                ),
                const SizedBox(height: 10),
                _Surface(
                  padding: EdgeInsets.zero,
                  child: Column(
                    children: [
                      _LinkTile(
                        tileKey: const ValueKey('open-later-list'),
                        icon: Icons.bookmark_border_rounded,
                        label: TiniStrings.listenLater,
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => LaterScreen(api: widget.api),
                          ),
                        ),
                      ),
                      _LinkTile(
                        tileKey: const ValueKey('open-likes-list'),
                        icon: Icons.favorite_border_rounded,
                        label: TiniStrings.myLikes,
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) =>
                                LaterScreen(api: widget.api, likes: true),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: TiniTokens.sectionGap),
                Text(
                  TiniStrings.appearance,
                  style: TiniTokens.section.copyWith(color: t.text),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: SegmentedButton<ThemeMode>(
                    segments: const [
                      ButtonSegment(
                        value: ThemeMode.system,
                        icon: Icon(Icons.brightness_auto),
                        label: Text(TiniStrings.themeSystem),
                      ),
                      ButtonSegment(
                        value: ThemeMode.light,
                        icon: Icon(Icons.light_mode),
                        label: Text(TiniStrings.themeLight),
                      ),
                      ButtonSegment(
                        value: ThemeMode.dark,
                        icon: Icon(Icons.dark_mode),
                        label: Text(TiniStrings.themeDark),
                      ),
                    ],
                    selected: {widget.themeMode},
                    onSelectionChanged: (s) =>
                        widget.onThemeChanged?.call(s.first),
                  ),
                ),
                const SizedBox(height: 10),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    key: const ValueKey('intro-replay'),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (ctx) => IntroScreen(onDone: () => Navigator.of(ctx).pop()),
                      ),
                    ),
                    icon: const Icon(Icons.school_outlined),
                    label: const Text(TiniStrings.introReplay),
                  ),
                ),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () async {
                      try {
                        await widget.api.logout();
                      } catch (_) {
                        // Yerel oturum silinemedi: çıkmış gibi göstermeyelim.
                        Haptics.warn();
                        return _toast(TiniStrings.unreachable);
                      }
                      if (context.mounted) _logout(context);
                    },
                    icon: const Icon(Icons.logout_rounded),
                    label: const Text(TiniStrings.logout),
                  ),
                ),
              ],
            ));
          },
        ),
      ),
    );
  }
}

class _Surface extends StatelessWidget {
  const _Surface({
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });
  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: t.surface1,
        borderRadius: BorderRadius.circular(TiniTokens.rCard),
        border: Border.all(color: t.line),
      ),
      child: Material(type: MaterialType.transparency, child: child),
    );
  }
}

/// Kullanıcı kartı: avatar, "Seviye N" ve "412 oy · 38 Efsane · 27 Dinlemedin".
/// Sunucu kullanıcı adı vermediği için ad yerine genel bir başlık kullanılır.
class _UserCard extends StatelessWidget {
  const _UserCard({required this.state, this.photo, this.onEditPhoto});
  final AppState state;
  final File? photo;
  final VoidCallback? onEditPhoto;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return _Surface(
      child: Row(
        children: [
          Semantics(
            button: true,
            label: TiniStrings.photoEdit,
            child: GestureDetector(
              key: const ValueKey('profile-avatar'),
              onTap: onEditPhoto,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    clipBehavior: Clip.antiAlias,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: [
                          TiniCover.colorsFor('profile').$1,
                          TiniCover.colorsFor('profile').$2,
                        ],
                      ),
                    ),
                    child: photo != null
                        ? Image.file(photo!,
                            fit: BoxFit.cover,
                            cacheWidth: 156,
                            errorBuilder: (_, _, _) =>
                                Icon(Icons.person_rounded, color: TiniTokens.onLightFill))
                        : Icon(Icons.person_rounded, color: TiniTokens.onLightFill),
                  ),
                  Positioned(
                    right: -2,
                    bottom: -2,
                    child: Container(
                      width: 20,
                      height: 20,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: t.surface2,
                        border: Border.all(color: t.surface1, width: 2),
                      ),
                      child: Icon(Icons.photo_camera_rounded, size: 11, color: t.text),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      TiniStrings.you,
                      style: TiniTokens.cardTitle.copyWith(color: t.text),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      TiniStrings.levelLabel(state.level),
                      style: TiniTokens.badge.copyWith(color: t.muted),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  TiniStrings.profileSummary(
                    state.total,
                    state.counts[6] ?? 0,
                    state.unheardSession,
                  ),
                  key: const ValueKey('profile-summary'),
                  style: TiniTokens.secondary.copyWith(color: t.muted),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Kaçınma bölgesi: kırmızı tonlu kart. Sunucu yalnızca sayı verir (etiket/ad yok).
class _AvoidCard extends StatelessWidget {
  const _AvoidCard({required this.profile});
  final TasteProfile? profile;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final danger = TiniVote.color(1);
    final p = profile;
    final soft = p == null ? 0 : p.avoidCount - p.hardAvoidCount;
    return Container(
      key: const ValueKey('avoid-card'),
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: danger.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(TiniTokens.rCard),
        border: Border.all(color: danger.withValues(alpha: 0.35)),
      ),
      child: p == null || p.avoidCount == 0
          ? Text(
              TiniStrings.avoidEmpty,
              style: TiniTokens.body.copyWith(color: t.muted),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    if (p.hardAvoidCount > 0)
                      TagChip(
                        label: TiniStrings.avoidHard,
                        count: p.hardAvoidCount,
                        danger: true,
                      ),
                    if (soft > 0)
                      TagChip(
                        label: TiniStrings.avoidSoft,
                        count: soft,
                        danger: true,
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  TiniStrings.avoidHint,
                  style: TiniTokens.secondary.copyWith(color: t.muted),
                ),
              ],
            ),
    );
  }
}

class _HistoryRow extends StatelessWidget {
  const _HistoryRow({required this.item, required this.onTap});
  final HistoryItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final title = item.title ?? TiniStrings.trackFallback(item.track);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(TiniTokens.rCard),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            TiniCover(seed: 'track-${item.track}', url: item.image, size: 46),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TiniTokens.bodyStrong.copyWith(color: t.text),
                  ),
                  Text(
                    item.artists.join(', '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TiniTokens.secondary.copyWith(color: t.muted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            VoteBadge(vote: item.vote, size: 30),
          ],
        ),
      ),
    );
  }
}

class _LinkTile extends StatelessWidget {
  const _LinkTile({
    required this.tileKey,
    required this.icon,
    required this.label,
    required this.onTap,
  });
  final Key tileKey;
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return ListTile(
      key: tileKey,
      leading: Icon(icon, color: t.muted),
      title: Text(label, style: TiniTokens.bodyStrong.copyWith(color: t.text)),
      trailing: Icon(Icons.chevron_right_rounded, color: t.muted2),
      onTap: onTap,
    );
  }
}
