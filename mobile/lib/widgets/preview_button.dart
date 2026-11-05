import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../preview_player.dart';
import '../theme/cosmic_colors.dart';
import 'studio.dart';

/// 30 sn'lik önizleme düğmesi: çal / durdur, yüklenirken döner, bulunamazsa soluk görünür.
class PreviewButton extends StatefulWidget {
  const PreviewButton({
    super.key,
    required this.api,
    required this.previewKey,
    this.artistId,
    this.trackId,
    this.deezerId,
  });
  final Api api;
  final String previewKey;
  final int? artistId;
  final int? trackId;

  /// Yeni çıkan parçalar: Deezer kimliğiyle doğrudan çözülür.
  final int? deezerId;

  @override
  State<PreviewButton> createState() => _PreviewButtonState();
}

class _PreviewButtonState extends State<PreviewButton> {
  Api get api => widget.api;
  String get previewKey => widget.previewKey;
  int? get artistId => widget.artistId;
  int? get trackId => widget.trackId;
  int? get deezerId => widget.deezerId;

  @override
  void dispose() {
    // Sayfa kapanınca ya da düğme ekrandan kalkınca bu önizleme susar; ağaç kilitliyken
    // bildirim atılmaz.
    final ctl = PreviewController.instance;
    if (ctl.key == previewKey) scheduleMicrotask(ctl.stop);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final ctl = PreviewController.instance;
    return ListenableBuilder(
      listenable: ctl,
      builder: (_, _) {
        final st = ctl.statusOf(previewKey);
        final unavailable = st == PreviewStatus.unavailable;
        return Tooltip(
          message: unavailable ? 'Önizleme bulunamadı' : '30 sn önizleme',
          child: Hoverable(
            enabled: !unavailable,
            scale: 1.1,
            child: Material(
            color: c.primary.withValues(alpha: st == PreviewStatus.playing ? 0.28 : 0.14),
            shape: const CircleBorder(),
            child: InkWell(
              customBorder: const CircleBorder(),
              onTap: unavailable
                  ? null
                  : () => ctl.toggle(
                      previewKey,
                      () => api.previewUrl(
                          artistId: artistId, trackId: trackId, deezerId: deezerId)),
              child: SizedBox(
                width: 44,
                height: 44,
                child: Center(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 180),
                    child: switch (st) {
                      PreviewStatus.loading => SizedBox(
                          key: const ValueKey('loading'),
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: c.primary)),
                      PreviewStatus.playing =>
                        Icon(Icons.pause_rounded, key: const ValueKey('pause'), color: c.primary),
                      PreviewStatus.unavailable => Icon(Icons.music_off_rounded,
                          key: const ValueKey('off'),
                          size: 20,
                          color: c.primary.withValues(alpha: 0.4)),
                      PreviewStatus.idle => Icon(Icons.play_arrow_rounded,
                          key: const ValueKey('play'), color: c.primary),
                    },
                  ),
                ),
              ),
            ),
          ),
          ),
        );
      },
    );
  }
}
