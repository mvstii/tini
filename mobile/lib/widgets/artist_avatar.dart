import 'package:flutter/material.dart';

import '../api.dart';
import '../theme/cosmic_colors.dart';
import '../theme/tini_tokens.dart';

/// Spotify sanatçı sayfası tarzı yuvarlak portre. Fotoğraf yoksa ya da yüklenemezse adın baş
/// harfi, addan türeyen Kozmik Spektrum geçişi üzerinde gösterilir.
class ArtistAvatar extends StatelessWidget {
  const ArtistAvatar({super.key, required this.name, this.url, this.size = 64});
  final String name;
  final String? url;
  final double size;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final i = name.hashCode.abs() % 6 + 1;
    final initial = name.trim().isEmpty ? '?' : name.trim().characters.first.toUpperCase();
    final fallback = Center(
      child: Text(initial,
          style: TiniTokens.initial(size).copyWith(color: Colors.white.withValues(alpha: 0.92))),
    );
    final u = url;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
              color: c.votes[i]!.border.withValues(alpha: 0.3),
              blurRadius: 18,
              offset: const Offset(0, 8)),
        ],
      ),
      child: ClipOval(
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [c.votes[i]!.fill, c.votes[i % 6 + 1]!.fill],
            ),
          ),
          child: u == null
              ? fallback
              : Image.network(
                  u,
                  width: size,
                  height: size,
                  fit: BoxFit.cover,
                  gaplessPlayback: true,
                  errorBuilder: (_, _, _) => fallback,
                  loadingBuilder: (_, child, progress) => progress == null ? child : fallback,
                ),
        ),
      ),
    );
  }
}

/// Liste yüklenince eksik portreleri sunucudan ister; sunucu her istekte az sayıda doldurduğu
/// için `pending` bitene dek (en çok [rounds] kez) yeniler. Hata sessizce yutulur: fotoğraf süstür.
Future<void> loadArtistPhotos(
  Api api,
  Iterable<int> ids,
  void Function(Map<int, String?> found) onFound, {
  int rounds = 6,
  bool Function() alive = _always,
  Duration retryDelay = const Duration(seconds: 2),
}) async {
  final want = ids.toSet().toList();
  for (var r = 0; r < rounds && want.isNotEmpty && alive(); r++) {
    try {
      final res = await api.artistImages(want);
      if (!alive()) return;
      onFound(res.images);
      want.removeWhere(res.images.containsKey);
      if (res.pending == 0) return;
    } catch (_) {
      // Geçici hata (soğuk sunucu, ağ kesintisi): kısa bekleyip en çok iki kez yeniden dene.
      await Future<void>.delayed(retryDelay);
      if (r >= 1) return;
    }
  }
}

bool _always() => true;
