import 'package:flutter/material.dart';

/// Tüm ekranların arkasındaki yumuşak ışık zemini. `BackdropFilter` yok: yalnızca iki
/// `RadialGradient` katmanı (sağ üst mor, sol alt macenta), bu yüzden ucuz.
class AmbientBackground extends StatelessWidget {
  const AmbientBackground({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final base = dark ? const Color(0xFF08060E) : const Color(0xFFF7F4FC);
    final top = dark ? const Color(0xFF3E1F5E) : const Color(0xFFB9A4E8);
    final bottom = dark ? const Color(0xFF59184A) : const Color(0xFFF2B5D4);
    return ColoredBox(
      color: base,
      child: Stack(
        children: [
          Positioned.fill(
            child: IgnorePointer(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: const Alignment(1.0, -1.0),
                    radius: 1.2,
                    colors: [top.withValues(alpha: dark ? 0.18 : 0.22), top.withValues(alpha: 0)],
                  ),
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: IgnorePointer(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: const Alignment(-1.0, 1.0),
                    radius: 1.0,
                    colors: [
                      bottom.withValues(alpha: dark ? 0.12 : 0.18),
                      bottom.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          child,
        ],
      ),
    );
  }
}

/// Üstten aydınlatmalı kart yüzeyi: dikey gradyan dolgu + 1 dp'lik, üstü parlak alt kenarı sönük
/// çerçeve. [tint] verilirse dolgu o renkten (vitrin kartı) türetilir.
class StudioSurface extends StatelessWidget {
  const StudioSurface({
    super.key,
    required this.child,
    this.radius = 20,
    this.padding = EdgeInsets.zero,
    this.fill,
    this.edge,
  });
  final Widget child;
  final double radius;
  final EdgeInsetsGeometry padding;

  /// Verilirse varsayılan dolgu gradyanının yerine geçer.
  final List<Color>? fill;

  /// Verilirse varsayılan çerçeve renklerinin (üst, alt) yerine geçer.
  final (Color, Color)? edge;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final fillColors = fill ??
        (dark
            ? const [Color(0xFF1F1A33), Color(0xFF141122)]
            : const [Color(0xFFFFFFFF), Color(0xFFF0ECF9)]);
    final (hi, lo) = edge ??
        (dark
            ? (Colors.white.withValues(alpha: 0.12), Colors.white.withValues(alpha: 0.04))
            : (Colors.black.withValues(alpha: 0.08), Colors.black.withValues(alpha: 0.03)));
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [hi, lo]),
      ),
      child: Padding(
        padding: const EdgeInsets.all(1),
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(radius - 1),
            gradient: LinearGradient(
                begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: fillColors),
          ),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

/// Bölüm üst başlığı (editoryal küçük harf aralıklı etiket).
class SectionLabel extends StatelessWidget {
  const SectionLabel(this.text, {super.key, this.color});
  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) => Text(
        text,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.4,
          color: color ?? Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      );
}

/// Şarkı adı ve sayfa başlıkları için sıkı, kalın stil.
TextStyle? studioTitle(BuildContext context, {TextStyle? base}) =>
    (base ?? Theme.of(context).textTheme.titleMedium)
        ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.4);
