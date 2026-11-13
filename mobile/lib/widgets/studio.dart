import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/cosmic_colors.dart';
import '../theme/tini_tokens.dart';
import '../theme/tokens.dart';

/// Tüm ekranların arkasındaki galaksi zemini: simsiyah-mor taban, iki nebula ışığı ve sabit bir
/// yıldız tozu katmanı (tek `CustomPaint`, animasyonsuz; `BackdropFilter` yok, bu yüzden ucuz).
/// Açık temada aynı kurgu pastel: lavanta zemin, pembe/mor nebula, ince parıltılar.
class AmbientBackground extends StatelessWidget {
  const AmbientBackground({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final base = TiniCosmicColors.of(context).scaffold;
    final top = dark ? TiniTokens.nebulaTopDark : TiniTokens.nebulaTopLight;
    final bottom = dark ? TiniTokens.nebulaBottomDark : TiniTokens.nebulaBottomLight;
    Widget glow(Alignment at, double radius, Color color, double alpha) => Positioned.fill(
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                    center: at,
                    radius: radius,
                    colors: [color.withValues(alpha: alpha), color.withValues(alpha: 0)]),
              ),
            ),
          ),
        );
    return ColoredBox(
      color: base,
      child: Stack(
        children: [
          glow(const Alignment(1.0, -1.0), 1.3, top, dark ? 0.22 : 0.26),
          glow(const Alignment(-1.0, 1.0), 1.1, bottom, dark ? 0.12 : 0.20),
          glow(const Alignment(-0.9, -0.3), 0.7, top, dark ? 0.06 : 0.08),
          Positioned.fill(
            child: IgnorePointer(
              child: RepaintBoundary(
                child: CustomPaint(painter: _StarDust(dark: dark)),
              ),
            ),
          ),
          child,
        ],
      ),
    );
  }
}

/// Sabit tohumdan üretilen yıldız tozu: aynı ekran her seferinde aynı gökyüzünü çizer.
class _StarDust extends CustomPainter {
  const _StarDust({required this.dark});
  final bool dark;

  static final List<(double, double, double, double)> _stars = () {
    final r = math.Random(7);
    return List.generate(90,
        (_) => (r.nextDouble(), r.nextDouble(), 0.4 + r.nextDouble() * 1.1, 0.25 + r.nextDouble() * 0.6));
  }();

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint();
    for (final (x, y, rad, a) in _stars) {
      p.color = (dark ? TiniTokens.starDark : TiniTokens.starLight)
          .withValues(alpha: dark ? a : a * 0.35);
      canvas.drawCircle(Offset(x * size.width, y * size.height), rad, p);
    }
  }

  @override
  bool shouldRepaint(_StarDust old) => old.dark != dark;
}

/// Üstten aydınlatmalı kart yüzeyi: dikey gradyan dolgu + 1 dp'lik, üstü parlak alt kenarı sönük
/// çerçeve. [tint] verilirse dolgu o renkten (vitrin kartı) türetilir.
class StudioSurface extends StatelessWidget {
  const StudioSurface({
    super.key,
    required this.child,
    this.radius = TiniShape.card + 4,
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
    final tok = TiniCosmicColors.of(context);
    final fillColors = fill ??
        (dark
            ? [tok.raised, tok.card]
            : const [TiniTokens.lightCardTop, TiniTokens.lightCardBottom]);
    final (hi, lo) = edge ??
        (dark
            ? (Colors.white.withValues(alpha: 0.12), Colors.white.withValues(alpha: 0.04))
            : (TiniTokens.lightAccent.withValues(alpha: 0.16),
                TiniTokens.lightAccent.withValues(alpha: 0.05)));
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        // Açık temada kart gölgeyle zeminden ayrılır; koyuda ışık kenarı yeterli.
        boxShadow: dark
            ? [
                BoxShadow(
                    color: tok.primary.withValues(alpha: 0.10),
                    blurRadius: 28,
                    offset: const Offset(0, 10)),
                const BoxShadow(color: TiniTokens.shadowDeep, blurRadius: 14, offset: Offset(0, 4)),
              ]
            : [
                BoxShadow(
                    color: TiniTokens.shadowTintLight.withValues(alpha: 0.10),
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
        style: TiniTokens.kickerLarge.copyWith(
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
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final tok = TiniCosmicColors.of(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final enabled = widget.onPressed != null && !widget.busy;
    final lit = enabled && (_down || _hover);
    final radius = BorderRadius.circular(widget.dense ? 12 : 16);
    final gradient = [
      scheme.primary,
      Color.lerp(scheme.primary, TiniTokens.pink, 0.35)!,
      Color.lerp(scheme.primary, TiniTokens.pink, 0.75)!,
    ];
    // Karanlık temada birincil renk açık lavantadır; beyaz yazı okunmaz. Gradyanın en açık
    // ucuna göre kontrastı yüksek olan yazı rengi seçilir.
    final lightest = gradient.reduce((a, b) => a.computeLuminance() >= b.computeLuminance() ? a : b);
    const dark = TiniTokens.onLightFill;
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
          )
        : BoxDecoration(
            borderRadius: radius,
            // Dolu yüzey: içi boş (saydam) düğme açık temada kaybolur.
            color: isDark ? tok.raised : tok.card,
            border: Border.all(color: tok.primary.withValues(alpha: isDark ? 0.35 : 0.45)),
          );
    // Işıma: dinlenirken yumuşak, basılı/üzerindeyken parlar (animasyonlu).
    final glow = !enabled
        ? <BoxShadow>[]
        : [
            BoxShadow(
                color: (widget.primary ? scheme.primary : tok.primary)
                    .withValues(alpha: widget.primary ? (lit ? 0.6 : 0.32) : (lit ? 0.30 : 0.12)),
                blurRadius: lit ? 26 : 16,
                offset: Offset(0, lit ? 4 : 7)),
          ];
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      child: Hoverable(
        enabled: enabled,
        scale: 1.02,
        child: AnimatedScale(
        scale: _down && enabled ? 0.96 : 1,
        // Basarken hızlı çöker, bırakınca yaylanarak geri gelir.
        duration: Duration(milliseconds: _down ? 90 : 260),
        curve: _down ? Curves.easeOut : Curves.easeOutBack,
        child: Opacity(
          opacity: widget.onPressed == null && !widget.busy ? 0.45 : 1,
          child: AnimatedContainer(
           duration: const Duration(milliseconds: 220),
           curve: Curves.easeOutCubic,
           decoration: BoxDecoration(borderRadius: radius, boxShadow: glow),
           child: Material(
            color: Colors.transparent,
            child: Ink(
              height: h,
              decoration: decoration,
              child: InkWell(
                borderRadius: radius,
                onTap: enabled ? widget.onPressed : null,
                onHover: (v) => setState(() => _hover = v),
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
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1100));

  /// Hareketi azalt açıkken sonsuz nefes durur, sabit bir kareye çekilir.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.stop();
      _c.value = 1;
    } else if (!_c.isAnimating) {
      _c.repeat(reverse: true);
    }
  }

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
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : Duration(milliseconds: 280 + delay),
      curve: Curves.easeOutCubic,
      builder: (_, t, c) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 14), child: c),
      ),
      child: child,
    );
  }
}

/// Yuvarlak, katmanlı ikon düğmesi (üst çubuk eylemleri). Dolu yüzey, ince kenar; seçiliyken
/// birincil renkte ışır. Basınca çöker, bırakınca yaylanır; ikon değişimi ölçekle geçer.
class StudioIconButton extends StatefulWidget {
  const StudioIconButton({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.selectedIcon,
    this.selected = false,
    this.size = 38,
  });
  final IconData icon;
  final IconData? selectedIcon;
  final bool selected;
  final String tooltip;
  final VoidCallback? onPressed;
  final double size;

  @override
  State<StudioIconButton> createState() => _StudioIconButtonState();
}

class _StudioIconButtonState extends State<StudioIconButton> {
  bool _down = false;
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final tok = TiniCosmicColors.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final enabled = widget.onPressed != null;
    final lit = enabled && (_down || _hover);
    final on = widget.selected;
    final fg = on ? tok.primary : Theme.of(context).colorScheme.onSurface;
    return Tooltip(
      message: widget.tooltip,
      child: AnimatedScale(
        scale: _down && enabled ? 0.88 : 1,
        duration: Duration(milliseconds: _down ? 80 : 260),
        curve: _down ? Curves.easeOut : Curves.easeOutBack,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOutCubic,
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: on
                ? Color.alphaBlend(tok.primary.withValues(alpha: dark ? 0.22 : 0.16),
                    dark ? tok.raised : tok.card)
                : (dark ? tok.raised : tok.card),
            border: Border.all(
                color: on
                    ? tok.primary.withValues(alpha: 0.6)
                    : (lit ? tok.primary.withValues(alpha: 0.45) : tok.highlight)),
            boxShadow: [
              if (enabled && (on || lit))
                BoxShadow(
                    color: tok.primary.withValues(alpha: lit ? 0.45 : 0.28),
                    blurRadius: lit ? 16 : 12),
              if (!dark && enabled)
                BoxShadow(
                    color: tok.primary.withValues(alpha: 0.10),
                    blurRadius: 8,
                    offset: const Offset(0, 3)),
            ],
          ),
          child: Opacity(
            opacity: enabled ? 1 : 0.38,
            child: Material(
              color: Colors.transparent,
              shape: const CircleBorder(),
              child: InkWell(
                customBorder: const CircleBorder(),
                onTap: widget.onPressed,
                onHover: (v) => setState(() => _hover = v),
                onHighlightChanged: (v) => setState(() => _down = v),
                child: Center(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 200),
                    transitionBuilder: (c, a) => ScaleTransition(
                        scale: CurvedAnimation(parent: a, curve: Curves.easeOutBack),
                        child: FadeTransition(opacity: a, child: c)),
                    child: Icon(
                      on && widget.selectedIcon != null ? widget.selectedIcon : widget.icon,
                      key: ValueKey(on),
                      size: widget.size * 0.5,
                      color: fg,
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

/// Hap biçimli ikincil bağlantı düğmesi ("Spotify'da aç"): dolu yüzey, vurgu renkli ince kenar
/// ve ikon; basınca çöker, üzerine gelince ışır.
class StudioLinkPill extends StatefulWidget {
  const StudioLinkPill({
    super.key,
    required this.icon,
    required this.label,
    required this.accent,
    required this.onPressed,
  });
  final IconData icon;
  final String label;
  final Color accent;
  final VoidCallback? onPressed;

  @override
  State<StudioLinkPill> createState() => _StudioLinkPillState();
}

class _StudioLinkPillState extends State<StudioLinkPill> {
  bool _down = false;
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final tok = TiniCosmicColors.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final enabled = widget.onPressed != null;
    final lit = enabled && (_down || _hover);
    return AnimatedScale(
      scale: _down && enabled ? 0.95 : 1,
      duration: Duration(milliseconds: _down ? 80 : 260),
      curve: _down ? Curves.easeOut : Curves.easeOutBack,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          color: dark ? tok.raised : tok.card,
          border: Border.all(color: widget.accent.withValues(alpha: lit ? 0.85 : 0.45)),
          boxShadow: [
            if (enabled)
              BoxShadow(
                  color: widget.accent.withValues(alpha: lit ? 0.35 : (dark ? 0.12 : 0.10)),
                  blurRadius: lit ? 16 : 10,
                  offset: const Offset(0, 3)),
          ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(20),
            onTap: widget.onPressed,
            onHover: (v) => setState(() => _hover = v),
            onHighlightChanged: (v) => setState(() => _down = v),
            child: SizedBox(
              height: 40,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 10),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(widget.icon, size: 16, color: widget.accent),
                    const SizedBox(width: 5),
                    Text(widget.label,
                        maxLines: 1,
                        style: Theme.of(context)
                            .textTheme
                            .labelMedium
                            ?.copyWith(fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
