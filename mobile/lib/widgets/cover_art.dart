import 'package:flutter/material.dart';

/// Albüm kapağı; URL yoksa ya da yüklenemezse albüm simgesi gösterilir.
class CoverArt extends StatelessWidget {
  const CoverArt({super.key, required this.url, this.size = 96});
  final String? url;
  final double size;

  @override
  Widget build(BuildContext context) {
    final placeholder = Icon(Icons.album, size: size * 0.45);
    final box = SizedBox(
      width: size,
      height: size,
      child: ColoredBox(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
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
    return ClipRRect(borderRadius: BorderRadius.circular(12), child: box);
  }
}
