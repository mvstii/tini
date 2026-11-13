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
  bool _down = false;
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
        final playing = st == PreviewStatus.playing;
        final dark = Theme.of(context).brightness == Brightness.dark;
        final scheme = Theme.of(context).colorScheme;
        // Dolu gradyan: çalarken daha parlak ve çevresinde ince halka; bulunamazsa sönük yüzey.
        final decoration = unavailable
            ? BoxDecoration(
                shape: BoxShape.circle,
                color: dark ? c.raised : c.card,
                border: Border.all(color: c.highlight))
            : BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [scheme.primary, Color.lerp(scheme.primary, Colors.black, 0.14)!],
                ),
                border: Border.all(color: Colors.white.withValues(alpha: playing ? 0.55 : 0.0), width: 2),
                boxShadow: [
                  BoxShadow(
                      color: scheme.primary.withValues(alpha: playing ? 0.65 : 0.35),
                      blurRadius: playing ? 22 : 14,
                      offset: const Offset(0, 4)),
                ],
              );
        const onFill = Colors.white;
        return Tooltip(
          message: unavailable
              ? 'Önizleme bulunamadı'
              : st == PreviewStatus.error
                  ? 'Önizleme yüklenemedi, tekrar dene'
                  : '30 sn önizleme',
          child: Hoverable(
            enabled: !unavailable,
            scale: 1.1,
            child: AnimatedScale(
            scale: _down && !unavailable ? 0.9 : 1,
            duration: Duration(milliseconds: _down ? 80 : 260),
            curve: _down ? Curves.easeOut : Curves.easeOutBack,
            child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutCubic,
            decoration: decoration,
            child: Material(
            color: Colors.transparent,
            shape: const CircleBorder(),
            child: InkWell(
              customBorder: const CircleBorder(),
              onHighlightChanged: (v) => setState(() => _down = v),
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
                    transitionBuilder: (w, a) => ScaleTransition(
                        scale: CurvedAnimation(parent: a, curve: Curves.easeOutBack),
                        child: FadeTransition(opacity: a, child: w)),
                    child: switch (st) {
                      PreviewStatus.loading => SizedBox(
                          key: const ValueKey('loading'),
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: onFill)),
                      PreviewStatus.playing =>
                        Icon(Icons.pause_rounded, key: const ValueKey('pause'), color: onFill),
                      PreviewStatus.unavailable => Icon(Icons.music_off_rounded,
                          key: const ValueKey('off'),
                          size: 20,
                          color: scheme.onSurfaceVariant.withValues(alpha: 0.6)),
                      PreviewStatus.error => Icon(Icons.refresh_rounded,
                          key: const ValueKey('retry'), color: onFill),
                      PreviewStatus.idle => Icon(Icons.play_arrow_rounded,
                          key: const ValueKey('play'), size: 28, color: onFill),
                    },
                  ),
                ),
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
