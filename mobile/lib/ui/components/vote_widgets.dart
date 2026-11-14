import 'package:flutter/material.dart';

import '../../strings.dart';
import '../../theme/tini_tokens.dart';
import '../../widgets/studio.dart';

/// Oy düğmesinin durumu: normal, seçili (%112 büyür, 5 pt hale) ya da pasif (başka oy seçili).
enum VoteButtonState { normal, selected, passive }

/// Oy ölçeğindeki rengin üstünde okunur yazı rengi.
Color onVoteColor(int vote) {
  if (vote == 6) return Colors.white;
  return TiniVote.color(vote).computeLuminance() > 0.4 ? TiniTokens.onLightFill : Colors.white;
}

/// 50 pt'lik yuvarlak oy düğmesi. Efsane (6) her durumda gradyandır.
class VoteButton extends StatelessWidget {
  const VoteButton({
    super.key,
    required this.value,
    this.state = VoteButtonState.normal,
    this.onTap,
    this.size = 46,
  });
  final int value;
  final VoteButtonState state;
  final VoidCallback? onTap;
  final double size;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final color = TiniVote.color(value);
    final grad = TiniVote.gradient(value);
    final selected = state == VoteButtonState.selected;
    final passive = state == VoteButtonState.passive;
    // Efsane her durumda gradyan; diğerleri seçilince dolu, değilken yumuşak dolgu + kenar.
    final filled = selected || value == 6;
    final label = TiniStrings.voteLabels[value - 1];
    return Semantics(
      button: true,
      selected: selected,
      label: TiniStrings.voteSemantics(value, label),
      excludeSemantics: true,
      onTap: onTap,
      child: Opacity(
        opacity: passive ? 0.45 : 1,
        child: AnimatedScale(
          scale: selected ? 1.12 : 1,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOutBack,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: grad != null && filled ? grad : null,
              color: grad != null && filled
                  ? null
                  : (selected ? color : Color.alphaBlend(color.withValues(alpha: 0.16), t.surface1)),
              border: Border.all(
                color: grad != null && !selected ? TiniVote.efsaneStart : color,
                width: 1.5,
              ),
              boxShadow: [
                if (selected)
                  BoxShadow(color: color.withValues(alpha: 0.35), blurRadius: 12, spreadRadius: 5),
              ],
            ),
            child: Material(
              type: MaterialType.transparency,
              shape: const CircleBorder(),
              child: InkWell(
                customBorder: const CircleBorder(),
                onTap: onTap,
                child: Center(
                  child: Text(
                    '$value',
                    style: TiniTokens.cardTitle.copyWith(
                      color: filled ? onVoteColor(value) : t.text,
                      letterSpacing: 0,
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

/// Altı oy düğmesi yan yana; dokunuşta hafif titreşim verir. Seçili oy varsa diğerleri pasifleşir.
class VoteRow extends StatelessWidget {
  const VoteRow({super.key, this.selected, required this.onVote, this.enabled = true, this.showLabels = false});
  final int? selected;
  final ValueChanged<int> onVote;
  final bool enabled;

  /// Her düğmenin altına oy adını (Berbat … Efsane) yazar.
  final bool showLabels;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var v = 1; v <= 6; v++)
          SizedBox(
            width: 52,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                VoteButton(
                  key: ValueKey('vote-$v'),
                  value: v,
                  state: selected == null
                      ? VoteButtonState.normal
                      : (selected == v ? VoteButtonState.selected : VoteButtonState.passive),
                  onTap: enabled
                      ? () {
                          Haptics.select();
                          onVote(v);
                        }
                      : null,
                ),
                if (showLabels) ...[
                  const SizedBox(height: 6),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(TiniStrings.voteLabels[v - 1],
                        maxLines: 1,
                        style: TiniTokens.caption.copyWith(
                            color: selected == v ? t.text : t.muted, fontWeight: FontWeight.w600)),
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

/// Listelerde oy göstermek için küçük rozet (sayı + renk).
class VoteBadge extends StatelessWidget {
  const VoteBadge({super.key, required this.vote, this.size = 24});
  final int vote;
  final double size;

  @override
  Widget build(BuildContext context) {
    final grad = TiniVote.gradient(vote);
    return Semantics(
      label: TiniStrings.voteSemantics(vote, TiniStrings.voteLabels[vote - 1]),
      excludeSemantics: true,
      child: Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: grad,
          color: grad == null ? TiniVote.color(vote) : null,
        ),
        child: Text('$vote',
            style: TiniTokens.initial(size * 1.2).copyWith(color: onVoteColor(vote), fontWeight: FontWeight.w800)),
      ),
    );
  }
}

/// Tahmini oyu gösteren hap: "Tahmin: İyi".
class PredictionPill extends StatelessWidget {
  const PredictionPill({super.key, required this.vote});
  final int vote;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final color = TiniVote.color(vote);
    return Semantics(
      label: '${TiniStrings.predictionPrefix}: ${TiniStrings.voteSemantics(vote, TiniStrings.voteLabels[vote - 1])}',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(TiniTokens.rPill),
          color: Color.alphaBlend(color.withValues(alpha: 0.16), t.surface1),
          border: Border.all(color: color.withValues(alpha: 0.6)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                  shape: BoxShape.circle, color: color, gradient: TiniVote.gradient(vote)),
            ),
            const SizedBox(width: 6),
            Text(
              '${TiniStrings.predictionPrefix}: ${TiniStrings.voteLabels[vote - 1]}',
              style: TiniTokens.secondary.copyWith(color: t.text, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    );
  }
}

/// "Dinlemedim" eylemi: kesikli çerçeve, kulak simgesi, "keşif havuzuna ekle".
class UnheardButton extends StatelessWidget {
  const UnheardButton({super.key, required this.onTap, this.added = false});
  final VoidCallback? onTap;
  final bool added;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final color = added ? TiniTokens.slotUnheard : t.muted;
    return Semantics(
      button: true,
      label: added ? TiniStrings.unheardAdded : TiniStrings.unheardAdd,
      excludeSemantics: true,
      onTap: onTap,
      child: CustomPaint(
        foregroundPainter: _DashedBorder(color: color.withValues(alpha: 0.7), radius: TiniTokens.rCard),
        child: InkWell(
          borderRadius: BorderRadius.circular(TiniTokens.rCard),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(added ? Icons.check_rounded : Icons.hearing_rounded, size: 18, color: color),
                const SizedBox(width: 8),
                Text(added ? TiniStrings.unheardAdded : TiniStrings.unheardAdd,
                    style: TiniTokens.bodyStrong.copyWith(color: color)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DashedBorder extends CustomPainter {
  _DashedBorder({required this.color, required this.radius});
  final Color color;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    final path = Path()..addRRect(RRect.fromRectAndRadius(Offset.zero & size, Radius.circular(radius)));
    for (final m in path.computeMetrics()) {
      var d = 0.0;
      while (d < m.length) {
        canvas.drawPath(m.extractPath(d, d + 6), paint);
        d += 10;
      }
    }
  }

  @override
  bool shouldRepaint(_DashedBorder old) => old.color != color || old.radius != radius;
}
