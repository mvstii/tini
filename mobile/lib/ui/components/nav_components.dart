import 'dart:ui' show ImageFilter;

import 'package:flutter/material.dart';

import '../../strings.dart';
import '../../theme/tini_tokens.dart';
import 'tini_cover.dart';
import 'vote_widgets.dart';

/// Tek şarkı çalan mini oynatıcı: 58 pt, altta 2 pt ilerleme, %96 opak + 20 blur.
/// Tab çubuğunun 8 pt üstünde konumlandırmak ekranın işidir. Liste/kuyruk içermez.
class MiniPlayer extends StatelessWidget {
  const MiniPlayer({
    super.key,
    required this.title,
    required this.artist,
    required this.progress,
    required this.playing,
    required this.onToggle,
    this.sourceLabel,
    this.vote,
    this.coverSeed,
    this.coverUrl,
    this.onTap,
  });
  final String title;
  final String artist;
  final String? sourceLabel;
  final int? vote;
  final double progress;
  final bool playing;
  final VoidCallback onToggle;
  final String? coverSeed;
  final String? coverUrl;
  final VoidCallback? onTap;

  static const double height = 58;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final radius = BorderRadius.circular(TiniTokens.rCard);
    return ClipRRect(
      borderRadius: radius,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: TiniTokens.blur, sigmaY: TiniTokens.blur),
        child: Container(
          height: height,
          decoration: BoxDecoration(
            color: t.miniPlayer,
            borderRadius: radius,
            border: Border.all(color: t.line),
          ),
          child: Stack(
            children: [
              Positioned.fill(
                child: InkWell(
                  onTap: onTap,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(10, 8, 6, 10),
                    child: Row(
                      children: [
                        TiniCover(seed: coverSeed ?? '$title|$artist', url: coverUrl, size: 40),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TiniTokens.bodyStrong.copyWith(color: t.text, fontWeight: FontWeight.w700)),
                              Text(sourceLabel == null ? artist : '$artist · $sourceLabel',
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TiniTokens.secondary.copyWith(color: t.muted)),
                            ],
                          ),
                        ),
                        if (vote != null) ...[VoteBadge(vote: vote!, size: 30), const SizedBox(width: 6)],
                        IconButton(
                          tooltip: playing ? TiniStrings.pause : TiniStrings.play,
                          onPressed: onToggle,
                          icon: Icon(playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                              color: t.text, size: 30),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              Positioned(
                left: 12,
                right: 12,
                bottom: 4,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(1),
                  child: SizedBox(
                    height: 2,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        ColoredBox(color: t.line),
                        FractionallySizedBox(
                          alignment: Alignment.centerLeft,
                          widthFactor: progress.clamp(0.0, 1.0),
                          child: const DecoratedBox(
                              decoration: BoxDecoration(gradient: TiniTokens.brandGradient)),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Alt gezinme: Keşfet, Oyla, Listeler, Profil. Oyla'da bekleyen oy sayısı kırmızı rozetle.
class TiniTabBar extends StatelessWidget {
  const TiniTabBar({super.key, required this.index, required this.onSelect, this.pendingVotes = 0, this.recsFresh = false});
  final int index;
  final ValueChanged<int> onSelect;
  final int pendingVotes;

  /// Öneriler sekmesindeki liste bayat: sekmede nokta gösterilir.
  final bool recsFresh;

  static const _labels = [
    TiniStrings.tabDiscover,
    TiniStrings.tabRate,
    TiniStrings.tabLists,
    TiniStrings.tabProfile,
  ];
  static const _icons = [
    Icons.explore_outlined,
    Icons.style_outlined,
    Icons.queue_music_rounded,
    Icons.person_outline_rounded,
  ];
  static const _iconsActive = [
    Icons.explore_rounded,
    Icons.style_rounded,
    Icons.queue_music_rounded,
    Icons.person_rounded,
  ];

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: TiniTokens.blur, sigmaY: TiniTokens.blur),
        child: Container(
          decoration: BoxDecoration(color: t.tabBar, border: Border(top: BorderSide(color: t.line))),
          child: SafeArea(
            top: false,
            child: SizedBox(
              height: 62,
              child: Row(
                children: [
                  for (var i = 0; i < 4; i++)
                    Expanded(
                      child: _TabItem(
                        key: ValueKey('tab-$i'),
                        label: _labels[i],
                        icon: index == i ? _iconsActive[i] : _icons[i],
                        active: index == i,
                        badge: i == 1 ? pendingVotes : 0,
                        dot: i == 2 && recsFresh,
                        onTap: () => onSelect(i),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TabItem extends StatelessWidget {
  const _TabItem({
    super.key,
    required this.label,
    required this.icon,
    required this.active,
    required this.badge,
    required this.onTap,
    this.dot = false,
  });
  final String label;
  final IconData icon;
  final bool active;
  final int badge;
  final bool dot;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return Semantics(
      button: true,
      selected: active,
      label: dot
          ? '${TiniStrings.tabSemantics(label, badge)}, ${TiniStrings.newRecsSemantics}'
          : TiniStrings.tabSemantics(label, badge),
      excludeSemantics: true,
      onTap: onTap,
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                Icon(icon, size: 26, color: active ? TiniTokens.activeTab : t.muted2),
                if (dot)
                  Positioned(
                    left: 20,
                    top: -2,
                    child: Container(
                      key: const ValueKey('recs-dot'),
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(color: TiniVote.c1, shape: BoxShape.circle),
                    ),
                  ),
                if (badge > 0)
                  Positioned(
                    left: 14,
                    top: -6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                      constraints: const BoxConstraints(minWidth: 18),
                      decoration: BoxDecoration(
                        color: TiniVote.c1,
                        borderRadius: BorderRadius.circular(TiniTokens.rPill),
                      ),
                      child: Text(badge > 99 ? '99+' : '$badge',
                          textAlign: TextAlign.center,
                          style: TiniTokens.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(label,
                style: TiniTokens.tabLabel.copyWith(
                    color: active ? t.text : t.muted2,
                    fontWeight: active ? FontWeight.w700 : FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}
