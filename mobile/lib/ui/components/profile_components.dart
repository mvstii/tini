import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../strings.dart';
import '../../theme/tini_tokens.dart';
import 'tini_cover.dart';

// ---------------------------------------------------------------------------
// Zevk modu balonları: daire paketleme (saf fonksiyon) + ModeBubble
// ---------------------------------------------------------------------------

class PackedCircle {
  const PackedCircle(this.x, this.y, this.r);
  final double x;
  final double y;
  final double r;
}

/// [radii] sırasıyla verilen daireleri [width]×[height] alana çakışmadan yerleştirir.
/// Açgözlü: ilk daire merkeze, sonrakiler yerleşmişlere teğet adaylar arasından merkeze en
/// yakın olana. Sığmazsa tüm yarıçaplar küçültülür. Aynı girdi her zaman aynı çıktıyı verir.
List<PackedCircle> packCircles(List<double> radii,
    {required double width, required double height, double gap = 4}) {
  if (radii.isEmpty) return const [];
  var scale = 1.0;
  for (var attempt = 0; attempt < 40; attempt++) {
    final res = _tryPack([for (final r in radii) r * scale], width, height, gap);
    if (res != null) return res;
    scale *= 0.92;
  }
  return [for (final r in radii) PackedCircle(width / 2, height / 2, r * scale)];
}

List<PackedCircle>? _tryPack(List<double> radii, double w, double h, double gap) {
  final placed = <PackedCircle>[];
  final cx = w / 2, cy = h / 2;
  bool fits(double x, double y, double r) {
    if (x - r < -1e-6 || x + r > w + 1e-6 || y - r < -1e-6 || y + r > h + 1e-6) return false;
    for (final p in placed) {
      final d = math.sqrt((p.x - x) * (p.x - x) + (p.y - y) * (p.y - y));
      if (d < p.r + r + gap - 1e-6) return false;
    }
    return true;
  }

  for (final r in radii) {
    if (placed.isEmpty) {
      if (!fits(cx, cy, r)) return null;
      placed.add(PackedCircle(cx, cy, r));
      continue;
    }
    final cands = <Offset>[];
    for (final p in placed) {
      for (var a = 0; a < 360; a += 10) {
        final rad = a * math.pi / 180;
        final d = p.r + r + gap;
        cands.add(Offset(p.x + d * math.cos(rad), p.y + d * math.sin(rad)));
      }
    }
    for (var i = 0; i < placed.length; i++) {
      for (var j = i + 1; j < placed.length; j++) {
        final a = placed[i], b = placed[j];
        final dx = b.x - a.x, dy = b.y - a.y;
        final d = math.sqrt(dx * dx + dy * dy);
        final ra = a.r + r + gap, rb = b.r + r + gap;
        if (d == 0 || d > ra + rb || d < (ra - rb).abs()) continue;
        final l = (ra * ra - rb * rb + d * d) / (2 * d);
        final hh = math.sqrt(math.max(0, ra * ra - l * l));
        final mx = a.x + l * dx / d, my = a.y + l * dy / d;
        cands.add(Offset(mx + hh * dy / d, my - hh * dx / d));
        cands.add(Offset(mx - hh * dy / d, my + hh * dx / d));
      }
    }
    Offset? best;
    var bestD = double.infinity;
    for (final c in cands) {
      if (!fits(c.dx, c.dy, r)) continue;
      final d = (c.dx - cx) * (c.dx - cx) + (c.dy - cy) * (c.dy - cy);
      if (d < bestD - 1e-9 ||
          ((d - bestD).abs() <= 1e-9 && best != null && (c.dy < best.dy || (c.dy == best.dy && c.dx < best.dx)))) {
        bestD = d;
        best = c;
      }
    }
    if (best == null) return null;
    placed.add(PackedCircle(best.dx, best.dy, r));
  }
  return placed;
}

enum ModeKind { moon, spiral, record, bolt, wave }

extension ModeKindX on ModeKind {
  Color get color => switch (this) {
        ModeKind.moon => TiniTokens.modeMoon,
        ModeKind.spiral => TiniTokens.modeSpiral,
        ModeKind.record => TiniTokens.modeRecord,
        ModeKind.bolt => TiniTokens.modeBolt,
        ModeKind.wave => TiniTokens.modeWave,
      };
  IconData get icon => switch (this) {
        ModeKind.moon => Icons.nightlight_round,
        ModeKind.spiral => Icons.cyclone_rounded,
        ModeKind.record => Icons.album_rounded,
        ModeKind.bolt => Icons.bolt_rounded,
        ModeKind.wave => Icons.graphic_eq_rounded,
      };
}

/// Baskın etiketten (listedeki ilk eşleşen) mod simgesi seçer; eşleşme yoksa dalga.
ModeKind modeKindFor(List<String> tags) {
  const map = <ModeKind, List<String>>{
    ModeKind.moon: ['dream pop', 'shoegaze', 'ambient'],
    ModeKind.spiral: ['psychedelic', 'psych', 'anadolu'],
    ModeKind.record: ['trip-hop', 'trip hop', 'downtempo', 'electronic'],
    ModeKind.bolt: ['funk', 'soul', 'disco'],
  };
  for (final tag in tags) {
    final t = tag.toLowerCase();
    for (final e in map.entries) {
      if (e.value.any(t.contains)) return e.key;
    }
  }
  return ModeKind.wave;
}

class ModeData {
  const ModeData({required this.name, required this.share, this.anchors, this.tags = const []});
  final String name;

  /// 0–1 arası zevk payı.
  final double share;

  /// Çapa sayısı; arka uç vermiyorsa null (satır gösterilmez).
  final int? anchors;
  final List<String> tags;
}

/// Tek zevk modu balonu: simge, ad, "%34 · 9 çapa". Küçük balonlarda yalnızca ad ve yüzde.
class ModeBubble extends StatelessWidget {
  const ModeBubble({super.key, required this.mode, required this.diameter, this.onTap});
  final ModeData mode;
  final double diameter;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final kind = modeKindFor([mode.name, ...mode.tags]);
    final pct = (mode.share * 100).round();
    final big = diameter >= 150;
    final small = diameter < 100;
    final detail = (big && mode.anchors != null)
        ? '${TiniStrings.fitPercent(pct)} · ${mode.anchors} ${TiniStrings.anchorUnit}'
        : TiniStrings.fitPercent(pct);
    final iconBox = small ? 28.0 : 40.0;
    return Semantics(
      button: onTap != null,
      label: '${mode.name}, $detail',
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: diameter,
          height: diameter,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              center: const Alignment(-0.3, -0.4),
              colors: [kind.color.withValues(alpha: 0.42), kind.color.withValues(alpha: 0.16)],
            ),
            border: Border.all(color: kind.color.withValues(alpha: 0.7), width: 1.2),
          ),
          padding: EdgeInsets.all(diameter * 0.12),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: iconBox,
                  height: iconBox,
                  decoration: BoxDecoration(shape: BoxShape.circle, color: t.line),
                  child: Icon(kind.icon, size: iconBox * 0.55, color: kind.color),
                ),
                SizedBox(height: small ? 2 : 6),
                Text(mode.name,
                    textAlign: TextAlign.center,
                    style: TiniTokens.bodyStrong.copyWith(color: t.text, fontWeight: FontWeight.w800)),
                Text(detail, style: TiniTokens.secondary.copyWith(color: t.muted)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Modları paylara göre boyutlandırıp daire paketleme ile dizen alan.
class ModeBubbleField extends StatelessWidget {
  const ModeBubbleField({super.key, required this.modes, this.height = 300, this.onTap});
  final List<ModeData> modes;
  final double height;
  final ValueChanged<ModeData>? onTap;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth.isFinite ? c.maxWidth : 360.0;
      final sorted = [...modes]..sort((a, b) => b.share.compareTo(a.share));
      final maxShare = sorted.isEmpty ? 1.0 : math.max(sorted.first.share, 1e-6);
      final base = math.min(w, height) * 0.5;
      final radii = [for (final m in sorted) base * math.sqrt(m.share / maxShare)];
      final placed = packCircles(radii, width: w, height: height);
      return SizedBox(
        width: w,
        height: height,
        child: Stack(
          children: [
            for (var i = 0; i < sorted.length; i++)
              Positioned(
                left: placed[i].x - placed[i].r,
                top: placed[i].y - placed[i].r,
                child: ModeBubble(
                  mode: sorted[i],
                  diameter: placed[i].r * 2,
                  onTap: onTap == null ? null : () => onTap!(sorted[i]),
                ),
              ),
          ],
        ),
      );
    });
  }
}

// ---------------------------------------------------------------------------
// Oy dağılımı grafiği
// ---------------------------------------------------------------------------

/// 1–6 oy sayılarını renkli çubuklarla gösterir (Efsane gradyan).
class VoteDistributionChart extends StatelessWidget {
  const VoteDistributionChart({super.key, required this.counts, this.height = 130});

  /// Altı eleman: 1..6 oy sayıları.
  final List<int> counts;
  final double height;

  @override
  Widget build(BuildContext context) {
    assert(counts.length == 6);
    final t = TiniTokens.of(context);
    final maxC = counts.fold<int>(1, math.max);
    return Semantics(
      label: '${TiniStrings.votesChartTitle}: '
          '${[for (var i = 0; i < 6; i++) '${i + 1}: ${counts[i]}'].join(', ')}',
      excludeSemantics: true,
      child: SizedBox(
        height: height,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            for (var i = 0; i < 6; i++) ...[
              if (i > 0) const SizedBox(width: 14),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Expanded(
                      child: Align(
                        alignment: Alignment.bottomCenter,
                        child: FractionallySizedBox(
                          heightFactor: math.max(counts[i] / maxC, 0.04),
                          widthFactor: 1,
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(8),
                              color: TiniVote.gradient(i + 1) == null ? TiniVote.color(i + 1) : null,
                              gradient: TiniVote.gradient(i + 1),
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text('${i + 1}', style: TiniTokens.bodyStrong.copyWith(color: t.muted)),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// 30 sn önizleme oynatıcısı
// ---------------------------------------------------------------------------

String _mmss(Duration d) {
  final s = d.inSeconds;
  return '${s ~/ 60}:${(s % 60).toString().padLeft(2, '0')}';
}

/// Dalga formu çubukları (seed'den deterministik) + oynat/duraklat + süre.
/// Çalınan kısım marka gradyanıyla boyanır.
class ClipPlayer extends StatelessWidget {
  const ClipPlayer({
    super.key,
    required this.seed,
    required this.progress,
    required this.playing,
    required this.onToggle,
    this.total = const Duration(seconds: 30),
    this.onOpenExternal,
    this.bars = 36,
  });
  final String seed;

  /// 0–1.
  final double progress;
  final bool playing;
  final VoidCallback onToggle;
  final Duration total;
  final VoidCallback? onOpenExternal;
  final int bars;

  /// Seed'den 0.25–1.0 arası çubuk yükseklikleri.
  static List<double> waveform(String seed, int n) {
    var h = tiniHash(seed);
    final out = <double>[];
    for (var i = 0; i < n; i++) {
      h = (h * 1103515245 + 12345) & 0x7FFFFFFF;
      final env = 0.55 + 0.45 * math.sin(i / n * math.pi);
      out.add((0.25 + 0.75 * ((h >> 8) % 100) / 100) * env);
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final wave = waveform(seed, bars);
    final p = progress.clamp(0.0, 1.0);
    final elapsed = Duration(milliseconds: (total.inMilliseconds * p).round());
    return Semantics(
      label: TiniStrings.clipSemantics,
      value: '${_mmss(elapsed)} / ${_mmss(total)}',
      container: true,
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: t.surface1,
          borderRadius: BorderRadius.circular(TiniTokens.rCard),
          border: Border.all(color: t.line),
        ),
        child: Row(
          children: [
            Semantics(
              button: true,
              label: playing ? TiniStrings.pause : TiniStrings.play,
              excludeSemantics: true,
              onTap: onToggle,
              child: Material(
                color: Colors.white,
                shape: const CircleBorder(),
                child: InkWell(
                  customBorder: const CircleBorder(),
                  onTap: onToggle,
                  child: SizedBox(
                    width: 44,
                    height: 44,
                    child: Icon(playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                        color: TiniTokens.onLightFill, size: 26),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: SizedBox(
                height: 36,
                // Dar ekranda çubuk sayısı azalır (her çubuk en az 2 pt); dalga yine seed'den gelir.
                child: LayoutBuilder(builder: (_, box) {
                  final n = math.max(8, math.min(bars, ((box.maxWidth + 2) / 4).floor()));
                  final w = n == bars ? wave : waveform(seed, n);
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      for (var i = 0; i < n; i++) ...[
                        if (i > 0) const SizedBox(width: 2),
                        Expanded(
                          child: FractionallySizedBox(
                            heightFactor: w[i],
                            child: DecoratedBox(
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(2),
                                color: i / n < p
                                    ? Color.lerp(TiniVote.efsaneStart, TiniVote.efsaneEnd, i / n)
                                    : t.muted2.withValues(alpha: 0.55),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ],
                  );
                }),
              ),
            ),
            const SizedBox(width: 10),
            Text('${_mmss(elapsed)} / ${_mmss(total)}',
                style: TiniTokens.secondary.copyWith(color: t.muted, fontFeatures: const [FontFeature.tabularFigures()])),
            if (onOpenExternal != null)
              IconButton(
                onPressed: onOpenExternal,
                icon: Icon(Icons.open_in_new_rounded, size: 20, color: t.muted),
              ),
          ],
        ),
      ),
    );
  }
}
