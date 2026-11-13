import 'package:flutter/material.dart';

import '../../strings.dart';
import '../../theme/tini_tokens.dart';
import 'tini_cover.dart';
import 'vote_widgets.dart';

/// Keşif listesindeki dört slot: sana uyan, dinlemediğin, keşif, taze.
enum TrackSlot { fit, unheard, explore, fresh }

extension TrackSlotX on TrackSlot {
  Color get color => switch (this) {
    TrackSlot.fit => TiniTokens.slotFit,
    TrackSlot.unheard => TiniTokens.slotUnheard,
    TrackSlot.explore => TiniTokens.slotExplore,
    TrackSlot.fresh => TiniTokens.slotFresh,
  };
  String get label => switch (this) {
    TrackSlot.fit => TiniStrings.slotFit,
    TrackSlot.unheard => TiniStrings.slotUnheard,
    TrackSlot.explore => TiniStrings.slotExplore,
    TrackSlot.fresh => TiniStrings.slotFresh,
  };
}

/// 5 pt'lik ilerleme/oran çubuğu. [gradient] verilmezse marka gradyanı kullanılır.
class SlotBar extends StatelessWidget {
  const SlotBar({super.key, required this.value, this.color, this.height = 5});
  final double value;
  final Color? color;
  final double height;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final v = value.clamp(0.0, 1.0);
    return ClipRRect(
      borderRadius: BorderRadius.circular(TiniTokens.rPill),
      child: SizedBox(
        height: height,
        child: Stack(
          fit: StackFit.expand,
          children: [
            ColoredBox(color: t.line),
            FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: v,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: color,
                  gradient: color == null ? TiniTokens.brandGradient : null,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// "YENİ" rozeti.
class NewBadge extends StatelessWidget {
  const NewBadge({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: TiniTokens.slotFresh,
        borderRadius: BorderRadius.circular(TiniTokens.rCoverSmall / 2),
      ),
      child: Text(
        TiniStrings.newBadge,
        style: TiniTokens.badge.copyWith(color: Colors.white),
      ),
    );
  }
}

/// Keşif listesi satırı: 50 pt kapak, başlık (+YENİ), sanatçı, slot noktası + tek satır gerekçe,
/// sağda uyum yüzdesi. Dokunmak Gerekçe panelini açar; şarkıyı çalmaz.
class TrackRow extends StatelessWidget {
  const TrackRow({
    super.key,
    required this.title,
    required this.artist,
    required this.slot,
    required this.reason,
    this.coverSeed,
    this.coverUrl,
    this.fit,
    this.isNew = false,
    this.onTap,
  });
  final String title;
  final String artist;
  final TrackSlot slot;
  final String reason;
  final String? coverSeed;
  final String? coverUrl;
  final int? fit;
  final bool isNew;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final tint = slot == TrackSlot.unheard;
    return Semantics(
      button: true,
      label:
          '$title, $artist, ${slot.label}, $reason'
          '${fit != null ? ', ${TiniStrings.fitPercent(fit!)} ${TiniStrings.fitSuffix}' : ''}',
      excludeSemantics: true,
      onTap: onTap,
      child: Material(
        color: tint ? slot.color.withValues(alpha: 0.08) : Colors.transparent,
        borderRadius: BorderRadius.circular(TiniTokens.rCard),
        child: InkWell(
          borderRadius: BorderRadius.circular(TiniTokens.rCard),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                TiniCover(seed: coverSeed ?? '$title|$artist', url: coverUrl),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TiniTokens.bodyStrong.copyWith(
                                color: t.text,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          if (isNew) ...[
                            const SizedBox(width: 6),
                            const NewBadge(),
                          ],
                        ],
                      ),
                      Text(
                        artist,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TiniTokens.secondary.copyWith(color: t.muted),
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Container(
                            width: 7,
                            height: 7,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: slot.color,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              reason,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TiniTokens.caption.copyWith(
                                color: t.muted,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                if (fit != null) ...[
                  const SizedBox(width: 10),
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        TiniStrings.fitPercent(fit!),
                        style: TiniTokens.cardTitle.copyWith(
                          color: t.text,
                          letterSpacing: 0,
                        ),
                      ),
                      Text(
                        TiniStrings.fitSuffix,
                        style: TiniTokens.caption.copyWith(color: t.muted2),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Gerekçe panelindeki çapa satırı: kapak, ad, "6 verdin" ve katkı oranı çubuğu + yüzde.
class AnchorRow extends StatelessWidget {
  const AnchorRow({
    super.key,
    required this.title,
    required this.share,
    this.artist = '',
    this.vote,
    this.coverSeed,
    this.coverUrl,
  });
  final String title;
  final String artist;

  /// Kullanıcının bu çapaya verdiği oy; bilinmiyorsa (sunucu göndermiyorsa) boş bırakılır.
  final int? vote;

  /// 0–1 arası katkı payı.
  final double share;
  final String? coverSeed;
  final String? coverUrl;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final pct = (share * 100).round();
    return Semantics(
      label:
          '$title, $artist${vote != null ? ', ${TiniStrings.gaveVote(vote!)}' : ''}, ${TiniStrings.fitPercent(pct)}',
      excludeSemantics: true,
      child: Row(
        children: [
          TiniCover(
            seed: coverSeed ?? '$title|$artist',
            url: coverUrl,
            size: 50,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TiniTokens.bodyStrong.copyWith(
                    color: t.text,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                if (artist.isNotEmpty || vote != null)
                  Row(
                    children: [
                      if (artist.isNotEmpty)
                        Flexible(
                          child: Text(
                            vote != null ? '$artist · ' : artist,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TiniTokens.secondary.copyWith(
                              color: t.muted,
                            ),
                          ),
                        ),
                      if (vote != null) ...[
                        VoteBadge(vote: vote!, size: 20),
                        const SizedBox(width: 4),
                        Text(
                          TiniStrings.gaveSuffix,
                          style: TiniTokens.secondary.copyWith(color: t.muted),
                        ),
                      ],
                    ],
                  ),
                const SizedBox(height: 6),
                SlotBar(value: share),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            TiniStrings.fitPercent(pct),
            style: TiniTokens.cardTitle.copyWith(
              color: t.text,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

/// Etiket hapı; [count] verilirse pembe "×3" eklenir.
class TagChip extends StatelessWidget {
  const TagChip({
    super.key,
    required this.label,
    this.count,
    this.danger = false,
  });
  final String label;
  final int? count;

  /// Kaçınma bölgesi etiketi: kırmızı tonlu.
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final fg = danger ? TiniVote.c1 : t.text;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(TiniTokens.rPill),
        color: danger ? TiniVote.c1.withValues(alpha: 0.14) : t.surface2,
      ),
      child: Text.rich(
        TextSpan(
          text: label,
          style: TiniTokens.bodyStrong.copyWith(color: fg),
          children: [
            if (count != null)
              TextSpan(
                text: ' ×$count',
                style: TiniTokens.bodyStrong.copyWith(
                  color: TiniTokens.slotFresh,
                  fontWeight: FontWeight.w800,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

enum ServiceKind { apple, spotify }

enum SaveState { idle, saving, saved, notConnected }

/// Listeyi bir servise kaydeden düğme. Apple: beyaz zemin, kırmızı simge; Spotify: koyu yüzey,
/// yeşil simge. Logo yok; servis adı ve simge rengi ayırır. Bağlı değilse bağlama akışına gider.
class ServiceSaveButton extends StatelessWidget {
  const ServiceSaveButton({
    super.key,
    required this.service,
    this.state = SaveState.idle,
    this.onPressed,
    this.compact = false,
  });
  final ServiceKind service;
  final SaveState state;
  final VoidCallback? onPressed;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final apple = service == ServiceKind.apple;
    final bg = apple ? Colors.white : t.surface2;
    final fg = apple ? TiniTokens.onLightFill : t.text;
    final accent = apple
        ? TiniTokens.apple
        : (dark ? TiniTokens.spotify : TiniTokens.spotifyOnLight);
    final label = switch (state) {
      SaveState.idle => apple ? TiniStrings.saveApple : TiniStrings.saveSpotify,
      SaveState.saving => TiniStrings.saving,
      SaveState.saved => TiniStrings.saved,
      SaveState.notConnected =>
        apple ? TiniStrings.connectApple : TiniStrings.connectSpotify,
    };
    final icon = switch (state) {
      SaveState.idle => Icons.download_rounded,
      SaveState.saving => null,
      SaveState.saved => Icons.check_rounded,
      SaveState.notConnected => Icons.link_rounded,
    };
    final busy = state == SaveState.saving;
    return Semantics(
      button: true,
      enabled: !busy && state != SaveState.saved,
      label: label,
      excludeSemantics: true,
      onTap: onPressed,
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(TiniTokens.rPill),
        child: InkWell(
          borderRadius: BorderRadius.circular(TiniTokens.rPill),
          onTap: busy || state == SaveState.saved ? null : onPressed,
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: compact ? 44 : 48),
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: compact ? 14 : 18,
                vertical: 10,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (busy)
                    SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: accent,
                      ),
                    )
                  else
                    Icon(icon, size: 18, color: accent),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TiniTokens.bodyStrong.copyWith(
                        color: fg,
                        fontWeight: FontWeight.w700,
                      ),
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
