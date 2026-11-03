import 'package:flutter/material.dart';

import '../theme/cosmic_colors.dart';

/// Albüm kapağı; URL yoksa ya da yüklenemezse albüm simgesi gösterilir.
/// [gradientSeed] verilirse yer tutucu, bu dizgenin `hashCode`'undan türeyen Kozmik Spektrum
/// geçişi olur (aynı şarkı hep aynı rengi alır).
class CoverArt extends StatelessWidget {
  const CoverArt({
    super.key,
    required this.url,
    this.size = 96,
    this.radius = 12,
    this.gradientSeed,
    this.glow = false,
  });
  final String? url;
  final double size;
  final double radius;
  final String? gradientSeed;

  /// Kapağın altına, kendi renginden türeyen yumuşak renkli gölge ekler.
  final bool glow;

  Decoration? _gradient(BuildContext context) {
    final seed = gradientSeed;
    if (seed == null) return null;
    final votes = TiniCosmicColors.of(context).votes;
    final i = seed.hashCode.abs() % 6 + 1;
    return BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [votes[i]!.fill, votes[i % 6 + 1]!.fill],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final grad = gradientSeed != null;
    final placeholder = Opacity(
      opacity: grad ? 0.3 : 1,
      child: Icon(grad ? Icons.album_rounded : Icons.album, size: grad ? 64 : size * 0.45),
    );
    final box = SizedBox(
      width: size,
      height: size,
      child: DecoratedBox(
        decoration: _gradient(context) ??
            BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest),
        child: url == null
            ? Center(child: placeholder)
            : Image.network(
                url!,
                width: size,
                height: size,
                fit: BoxFit.cover,
                gaplessPlayback: true,
                errorBuilder: (_, _, _) => Center(child: placeholder),
                loadingBuilder: (_, child, progress) =>
                    progress == null ? child : Center(child: placeholder),
              ),
      ),
    );
    final clipped = ClipRRect(borderRadius: BorderRadius.circular(radius), child: box);
    if (!glow) return clipped;
    final c = TiniCosmicColors.of(context);
    final accent = gradientSeed == null ? c.primary : c.votes[gradientSeed.hashCode.abs() % 6 + 1]!.border;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        boxShadow: [
          BoxShadow(color: accent.withValues(alpha: 0.25), blurRadius: 24, offset: const Offset(0, 12)),
        ],
      ),
      child: clipped,
    );
  }
}
