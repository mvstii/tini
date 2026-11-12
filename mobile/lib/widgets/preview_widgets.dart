import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../app_state.dart';
import '../preview_player.dart';
import '../strings.dart';
import '../theme/tini_tokens.dart';
import '../ui/components/components.dart';

/// Önizleme süresi (30 sn); ilerleme bu sürede 0→1 dolar, çalma baştan başlayınca sıfırlanır.
const previewTotal = Duration(seconds: 30);

/// Çalarken 0→1 ilerleyen değeri [builder]'a verir; çalmıyorsa 0. Ses konumu okunmaz, kesit
/// sabit uzunlukta olduğu için ilerleme çalma başlangıcından hesaplanır.
class PreviewProgress extends StatelessWidget {
  const PreviewProgress({super.key, required this.playId, required this.playing, required this.builder});
  final int playId;
  final bool playing;
  final Widget Function(double progress) builder;

  @override
  Widget build(BuildContext context) {
    if (!playing) return builder(0);
    return TweenAnimationBuilder<double>(
      key: ValueKey(playId),
      tween: Tween(begin: 0, end: 1),
      duration: previewTotal,
      builder: (_, v, _) => builder(v),
    );
  }
}

/// Oyla ekranındaki 30 sn'lik kesit oynatıcısı: dalga formu, süre, çal/durdur.
class PreviewClip extends StatefulWidget {
  const PreviewClip({
    super.key,
    required this.api,
    required this.previewKey,
    required this.title,
    required this.artist,
    this.trackId,
    this.image,
    this.source,
    this.onOpenExternal,
  });
  final Api api;
  final String previewKey;
  final int? trackId;
  final String title;
  final String artist;
  final String? image;
  final String? source;
  final VoidCallback? onOpenExternal;

  @override
  State<PreviewClip> createState() => _PreviewClipState();
}

class _PreviewClipState extends State<PreviewClip> {
  @override
  void dispose() {
    final ctl = PreviewController.instance;
    if (ctl.key == widget.previewKey) scheduleMicrotask(ctl.stop);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ctl = PreviewController.instance;
    final t = TiniTokens.of(context);
    return ListenableBuilder(
      listenable: ctl,
      builder: (_, _) {
        final st = ctl.statusOf(widget.previewKey);
        if (st == PreviewStatus.unavailable) {
          return Container(
            height: 64,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: t.surface1,
              borderRadius: BorderRadius.circular(TiniTokens.rCard),
              border: Border.all(color: t.line),
            ),
            child: Text(TiniStrings.previewUnavailable, style: TiniTokens.secondary.copyWith(color: t.muted)),
          );
        }
        final playing = st == PreviewStatus.playing;
        return PreviewProgress(
          playId: ctl.playId,
          playing: playing,
          builder: (p) => ClipPlayer(
            seed: '${widget.title}|${widget.artist}',
            progress: p,
            playing: playing || st == PreviewStatus.loading,
            total: previewTotal,
            onOpenExternal: widget.onOpenExternal,
            onToggle: () => ctl.toggle(
              widget.previewKey,
              () => widget.api.previewUrl(trackId: widget.trackId),
              meta: PreviewMeta(
                title: widget.title,
                artist: widget.artist,
                image: widget.image,
                track: widget.trackId,
                source: widget.source,
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Sekmelerin altında, tab çubuğunun üstünde: o an çalan tek önizleme. Liste/kuyruk yoktur.
/// [hideForPrefix] ile eşleşen anahtarlar (Oyla ekranının kendi oynatıcısı) için gizlenir.
class PreviewMiniPlayer extends StatelessWidget {
  const PreviewMiniPlayer({super.key, required this.state, this.hideForPrefix});
  final AppState state;
  final String? hideForPrefix;

  @override
  Widget build(BuildContext context) {
    final ctl = PreviewController.instance;
    return ListenableBuilder(
      listenable: Listenable.merge([ctl, state]),
      builder: (_, _) {
        final m = ctl.meta;
        final key = ctl.key;
        final active = ctl.status == PreviewStatus.playing || ctl.status == PreviewStatus.loading;
        final hidden = m == null ||
            key == null ||
            !active ||
            (hideForPrefix != null && key.startsWith(hideForPrefix!));
        if (hidden) return const SizedBox(width: double.infinity);
        final playing = ctl.status == PreviewStatus.playing;
        return Padding(
          padding: const EdgeInsets.fromLTRB(TiniTokens.listMargin, 0, TiniTokens.listMargin, 8),
          child: PreviewProgress(
            playId: ctl.playId,
            playing: playing,
            builder: (p) => MiniPlayer(
              title: m.title,
              artist: m.artist,
              sourceLabel: m.source,
              coverUrl: m.image,
              coverSeed: '${m.title}|${m.artist}',
              vote: m.track == null ? null : state.votes[m.track],
              progress: p,
              playing: playing,
              onToggle: ctl.stop,
            ),
          ),
        );
      },
    );
  }
}
