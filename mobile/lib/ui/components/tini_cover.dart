import 'package:flutter/material.dart';

import '../../theme/tini_tokens.dart';

/// Kararlı (platformdan bağımsız) FNV-1a özeti: aynı dizge her zaman aynı sayıyı verir.
int tiniHash(String s) {
  var h = 0x811C9DC5;
  for (final u in s.codeUnits) {
    h ^= u;
    h = (h * 0x01000193) & 0x7FFFFFFF;
  }
  return h;
}

/// Albüm kapağı. [url] yoksa ya da yüklenemezse [seed]'den türeyen, her zaman aynı olan
/// bir gradyan gösterilir (uydurma kapak görseli yok).
class TiniCover extends StatelessWidget {
  const TiniCover({
    super.key,
    required this.seed,
    this.url,
    this.size = 50,
    this.radius = TiniTokens.rCoverSmall,
  });
  final String seed;
  final String? url;
  final double size;
  final double radius;

  static const _palette = [
    TiniVote.c1,
    TiniVote.c2,
    TiniVote.c3,
    TiniVote.c4,
    TiniVote.c5,
    TiniVote.efsaneStart,
    TiniVote.efsaneEnd,
  ];

  /// Seed'den türeyen iki renk (testlerde de kullanılır).
  static (Color, Color) colorsFor(String seed) {
    final h = tiniHash(seed);
    final a = _palette[h % _palette.length];
    var b = _palette[(h ~/ 7) % _palette.length];
    if (b == a) b = _palette[(h ~/ 7 + 3) % _palette.length];
    return (a, b);
  }

  /// Yedek kapak tonu: renk özü korunur, parlaklık düşürülür; koyu ve doygun, göz yormaz.
  static Color _deep(Color c, double lightness) {
    final h = HSLColor.fromColor(c);
    return h.withLightness(lightness).withSaturation((h.saturation * 0.85).clamp(0.0, 1.0)).toColor();
  }

  @override
  Widget build(BuildContext context) {
    final (a, b) = colorsFor(seed);
    final fallback = DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [_deep(a, 0.40), _deep(b, 0.26)],
        ),
      ),
      child: Center(
        child: Icon(Icons.music_note_rounded, size: size * 0.42, color: Colors.white.withValues(alpha: 0.8)),
      ),
    );
    final u = url;
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: SizedBox(
        width: size,
        height: size,
        child: Stack(
          fit: StackFit.expand,
          children: [
            fallback,
            if (u != null && u.isNotEmpty)
              Image.network(
                u,
                fit: BoxFit.cover,
                gaplessPlayback: true,
                cacheWidth: (size * MediaQuery.devicePixelRatioOf(context)).round(),
                errorBuilder: (_, _, _) => const SizedBox.shrink(),
              ),
          ],
        ),
      ),
    );
  }
}
