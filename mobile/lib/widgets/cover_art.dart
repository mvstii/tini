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
  });
  final String? url;
  final double size;
  final double radius;
  final String? gradientSeed;

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
    return ClipRRect(borderRadius: BorderRadius.circular(radius), child: box);
  }
}
