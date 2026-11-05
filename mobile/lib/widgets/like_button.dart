import 'package:flutter/material.dart';

import '../api.dart';
import '../theme/cosmic_colors.dart';

/// Beğeni kalbi: dokununca dolar, tekrar dokununca beğeni geri çekilir. Yer imidir, oy değildir.
/// Anında yerelde değişir; sunucu hata verirse eski haline döner.
class LikeButton extends StatefulWidget {
  const LikeButton({
    super.key,
    required this.api,
    required this.track,
    required this.liked,
    this.onChanged,
    this.overlay = false,
  });
  final Api api;
  final int track;
  final bool liked;
  final ValueChanged<bool>? onChanged;

  /// Kapak üstünde yarı saydam zeminli yuvarlak düğme.
  final bool overlay;

  @override
  State<LikeButton> createState() => _LikeButtonState();
}

class _LikeButtonState extends State<LikeButton> {
  late bool _liked = widget.liked;
  bool _busy = false;

  @override
  void didUpdateWidget(LikeButton old) {
    super.didUpdateWidget(old);
    if (old.liked != widget.liked || old.track != widget.track) _liked = widget.liked;
  }

  Future<void> _toggle() async {
    if (_busy) return;
    final next = !_liked;
    setState(() {
      _liked = next;
      _busy = true;
    });
    widget.onChanged?.call(next);
    try {
      await (next ? widget.api.addLike(widget.track) : widget.api.removeLike(widget.track));
    } catch (e) {
      if (!mounted) return;
      setState(() => _liked = !next);
      widget.onChanged?.call(!next);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(e is ApiException ? e.message : 'Beğeni kaydedilemedi, tekrar dene')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final color = _liked ? c.votes[5]!.border : Theme.of(context).colorScheme.onSurfaceVariant;
    final button = IconButton(
      key: ValueKey('like-${widget.track}'),
      tooltip: _liked ? 'Beğeniyi geri çek' : 'Beğen',
      onPressed: _toggle,
      icon: AnimatedSwitcher(
        duration: const Duration(milliseconds: 160),
        transitionBuilder: (child, a) => ScaleTransition(scale: a, child: child),
        child: Icon(
          _liked ? Icons.favorite_rounded : Icons.favorite_border_rounded,
          key: ValueKey(_liked),
          color: color,
        ),
      ),
    );
    if (!widget.overlay) return button;
    return DecoratedBox(
      decoration:
          BoxDecoration(shape: BoxShape.circle, color: Colors.black.withValues(alpha: 0.35)),
      child: button,
    );
  }
}
