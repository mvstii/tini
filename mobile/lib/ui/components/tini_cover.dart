
import 'package:flutter/material.dart';

import '../../theme/cover_art.dart';
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
/// üretilmiş bir kapak çizilir (halkalar, bokeh, çizgiler, ufuk, küre; uydurma görsel yok).
class TiniCover extends StatelessWidget {
  const TiniCover({
    super.key,
    required this.seed,
    this.url,
    this.size = 50,
    this.radius = TiniTokens.rCoverSmall,
    this.fallbackUrl,
  });
  final String seed;
  final String? url;

  /// Kapak yoksa ya da yüklenemezse gösterilecek ikinci görsel (ör. sanatçı portresi).
  final String? fallbackUrl;
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

  /// Seed'den türeyen iki renk (avatar ve testlerde de kullanılır).
  static (Color, Color) colorsFor(String seed) {
    final h = tiniHash(seed);
    final a = _palette[h % _palette.length];
    var b = _palette[(h ~/ 7) % _palette.length];
    if (b == a) b = _palette[(h ~/ 7 + 3) % _palette.length];
    return (a, b);
  }

  static CoverArtKind kindFor(String seed) =>
      CoverArtKind.values[(tiniHash(seed) ~/ 13) % CoverArtKind.values.length];

  Widget _fallbackImage(BuildContext context) {
    final f = fallbackUrl;
    if (f == null || f.isEmpty) return const SizedBox.shrink();
    return Image.network(
      f,
      fit: BoxFit.cover,
      gaplessPlayback: true,
      cacheWidth: (size * MediaQuery.devicePixelRatioOf(context)).round(),
      errorBuilder: (_, _, _) => const SizedBox.shrink(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final h = tiniHash(seed);
    final fallback = CustomPaint(
      key: const ValueKey('cover-art'),
      painter: TiniCoverArtPainter(kindFor(seed), (h >> 5) & 1),
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
                errorBuilder: (_, _, _) => _fallbackImage(context),
              )
            else
              _fallbackImage(context),
          ],
        ),
      ),
    );
  }
}

