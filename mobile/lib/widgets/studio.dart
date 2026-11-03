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
                    colors: [top.withValues(alpha: dark ? 0.12 : 0.22), top.withValues(alpha: 0)],
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
                      bottom.withValues(alpha: dark ? 0.07 : 0.18),
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
            ? const [Color(0xFF1B1730), Color(0xFF171329)]
            : const [Color(0xFFFFFFFF), Color(0xFFFAF8FF)]);
    final (hi, lo) = edge ??
        (dark
            ? (Colors.white.withValues(alpha: 0.12), Colors.white.withValues(alpha: 0.04))
            : (const Color(0xFF6750A4).withValues(alpha: 0.16),
                const Color(0xFF6750A4).withValues(alpha: 0.05)));
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        // Açık temada kart gölgeyle zeminden ayrılır; koyuda ışık kenarı yeterli.
        boxShadow: dark
            ? null
            : [
                BoxShadow(
                    color: const Color(0xFF4A3A8C).withValues(alpha: 0.10),
                    blurRadius: 22,
                    offset: const Offset(0, 8)),
              ],
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

/// Üzerine gelince (fare/kalem/odak) hafifçe büyüyen sarmalayıcı. Dokunmatikte etkisizdir;
/// basma geri bildirimi her düğmenin kendi animasyonundadır.
class Hoverable extends StatefulWidget {
  const Hoverable({super.key, required this.child, this.scale = 1.04, this.enabled = true});
  final Widget child;
  final double scale;
  final bool enabled;

  @override
  State<Hoverable> createState() => _HoverableState();
}

class _HoverableState extends State<Hoverable> {
  bool _hover = false;

  void _set(bool v) {
    if (_hover != v) setState(() => _hover = v);
  }

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => _set(true),
      onExit: (_) => _set(false),
      child: AnimatedScale(
        scale: _hover && widget.enabled ? widget.scale : 1,
        duration: const Duration(milliseconds: 140),
        curve: Curves.easeOutCubic,
        child: widget.child,
      ),
    );
  }
}

/// Ortak hata / boş durum kartı: simge + metin, isteğe bağlı "Yeniden dene".
class StateNote extends StatelessWidget {
  const StateNote.error(this.text, {super.key, this.onRetry})
      : icon = Icons.error_outline_rounded,
        isError = true;
  const StateNote.empty(this.text, {super.key, this.icon = Icons.inbox_outlined})
      : onRetry = null,
        isError = false;
  final String text;
  final IconData icon;
  final bool isError;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = isError ? scheme.error : scheme.onSurfaceVariant;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: StudioSurface(
        padding: const EdgeInsets.all(14),
        child: Row(children: [
          Icon(icon, color: color),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: TextStyle(color: color))),
          if (onRetry != null)
            TextButton(onPressed: onRetry, child: const Text('Yeniden dene')),
        ]),
      ),
    );
  }
}

/// Şarkı adı ve sayfa başlıkları için sıkı, kalın stil.
TextStyle? studioTitle(BuildContext context, {TextStyle? base}) =>
    (base ?? Theme.of(context).textTheme.titleMedium)
        ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.4);

/// Birincil (gradyan dolgu) ya da ikincil (gradyan çerçeve) eylem düğmesi. Basınca hafifçe küçülür,
/// [busy] iken etiketi korur ve başına dönen bir gösterge koyar; tekrar basılmasını engeller.
class StudioButton extends StatefulWidget {
  const StudioButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.busy = false,
    this.primary = true,
    this.dense = false,
  });
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool busy;
  final bool primary;
  final bool dense;

  @override
  State<StudioButton> createState() => _StudioButtonState();
}

class _StudioButtonState extends State<StudioButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final enabled = widget.onPressed != null && !widget.busy;
    final radius = BorderRadius.circular(widget.dense ? 12 : 16);
    final gradient = [
      scheme.primary,
      Color.lerp(scheme.primary, const Color(0xFFE0479E), 0.55)!,
    ];
    // Karanlık temada birincil renk açık lavantadır; beyaz yazı okunmaz. Gradyanın en açık
    // ucuna göre kontrastı yüksek olan yazı rengi seçilir.
    final lightest = gradient.reduce((a, b) => a.computeLuminance() >= b.computeLuminance() ? a : b);
    const dark = Color(0xFF1B1030);
    final fg = !widget.primary
        ? scheme.onSurface
        : (lightest.computeLuminance() > 0.18 ? dark : Colors.white);
    final h = widget.dense ? 40.0 : 52.0;
    final decoration = widget.primary
        ? BoxDecoration(
            borderRadius: radius,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: gradient,
            ),
            boxShadow: enabled
                ? [
                    BoxShadow(
                        color: scheme.primary.withValues(alpha: 0.35),
                        blurRadius: 16,
                        offset: const Offset(0, 6))
                  ]
                : null,
          )
        : BoxDecoration(
            borderRadius: radius,
            color: scheme.surfaceContainerHighest.withValues(alpha: 0.35),
            border: Border.all(color: scheme.outlineVariant),
          );
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      child: Hoverable(
        enabled: enabled,
        scale: 1.02,
        child: AnimatedScale(
        scale: _down && enabled ? 0.97 : 1,
        duration: const Duration(milliseconds: 90),
        child: Opacity(
          opacity: widget.onPressed == null && !widget.busy ? 0.45 : 1,
          child: Material(
            color: Colors.transparent,
            child: Ink(
              height: h,
              decoration: decoration,
              child: InkWell(
                borderRadius: radius,
                onTap: enabled ? widget.onPressed : null,
                onHighlightChanged: (v) => setState(() => _down = v),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 18),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (widget.busy)
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2.2, color: fg),
                        )
                      else if (widget.icon != null)
                        Icon(widget.icon, size: 20, color: fg),
                      if (widget.busy || widget.icon != null) const SizedBox(width: 8),
                      Flexible(
                        child: Text(widget.label,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                color: fg, fontWeight: FontWeight.w700, letterSpacing: 0.1)),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
      ),
    );
  }
}

/// Yükleme sırasında listenin yerini tutan, nefes alan iskelet kartı.
class SkeletonCard extends StatefulWidget {
  const SkeletonCard({super.key, this.height = 84});
  final double height;

  @override
  State<SkeletonCard> createState() => _SkeletonCardState();
}

class _SkeletonCardState extends State<SkeletonCard> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))
        ..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final base = Theme.of(context).colorScheme.onSurface;
    Widget bar(double w, double h) => Container(
          width: w,
          height: h,
          decoration: BoxDecoration(
              color: base.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(6)),
        );
    return FadeTransition(
      opacity: Tween(begin: 0.45, end: 1.0).animate(_c),
      child: StudioSurface(
        padding: const EdgeInsets.all(14),
        child: SizedBox(
          height: widget.height,
          child: Row(children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                  color: base.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(12)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [bar(160, 14), const SizedBox(height: 10), bar(100, 10)],
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

/// Çocuğu [index]'e göre gecikmeli olarak yumuşakça yukarı kayarak görünür kılar.
class StaggerIn extends StatelessWidget {
  const StaggerIn({super.key, required this.index, required this.child});
  final int index;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final delay = index.clamp(0, 8) * 45;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 280 + delay),
      curve: Curves.easeOutCubic,
      builder: (_, t, c) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 14), child: c),
      ),
      child: child,
    );
  }
}
