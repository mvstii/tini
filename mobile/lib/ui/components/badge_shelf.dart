import 'package:flutter/material.dart';

import '../../badges.dart';
import '../../strings.dart';
import '../../theme/tini_tokens.dart';

/// Rozet şeridi: kazanılanlar renkli, kazanılmayanlar soluk ve ilerlemesiyle ("37 / 100").
class BadgeShelf extends StatelessWidget {
  const BadgeShelf({super.key, required this.badges});
  final List<TiniBadge> badges;

  static const _palette = [
    TiniVote.c5,
    TiniVote.c3,
    TiniVote.c4,
    TiniTokens.modeBolt,
    TiniVote.c2,
    TiniVote.efsaneStart,
    TiniVote.c1,
    TiniTokens.modeMoon,
    TiniTokens.slotExplore,
  ];

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 104,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: badges.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (_, i) => _BadgeTile(
          key: ValueKey('badge-${badges[i].id}'),
          badge: badges[i],
          color: _palette[i % _palette.length],
        ),
      ),
    );
  }
}

class _BadgeTile extends StatelessWidget {
  const _BadgeTile({super.key, required this.badge, required this.color});
  final TiniBadge badge;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final earned = badge.earned;
    final status = earned ? TiniStrings.badgeEarned : '${badge.value} / ${badge.goal}';
    return Semantics(
      label: '${badge.title}, $status',
      excludeSemantics: true,
      child: Tooltip(
        message: badge.hint,
        triggerMode: TooltipTriggerMode.tap,
        child: Container(
          width: 88,
          padding: const EdgeInsets.fromLTRB(6, 10, 6, 8),
          decoration: BoxDecoration(
            color: earned ? Color.alphaBlend(color.withValues(alpha: 0.10), t.surface1) : t.surface1,
            borderRadius: BorderRadius.circular(TiniTokens.rCard),
            border: Border.all(color: earned ? color.withValues(alpha: 0.45) : t.line),
          ),
          child: Column(
            children: [
              SizedBox(
                width: 40,
                height: 40,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    if (!earned)
                      SizedBox(
                        width: 40,
                        height: 40,
                        child: CircularProgressIndicator(
                          value: badge.progress,
                          strokeWidth: 2.5,
                          color: color.withValues(alpha: 0.7),
                          backgroundColor: t.line,
                        ),
                      ),
                    Container(
                      width: earned ? 40 : 30,
                      height: earned ? 40 : 30,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: earned ? color : t.line,
                      ),
                      child: Icon(
                        badge.icon,
                        size: earned ? 22 : 16,
                        color: earned ? TiniTokens.onLightFill : t.muted2,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              Text(
                badge.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: TiniTokens.caption.copyWith(
                  color: earned ? t.text : t.muted,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(
                status,
                maxLines: 1,
                style: TiniTokens.caption.copyWith(
                  color: earned ? color : t.muted2,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
