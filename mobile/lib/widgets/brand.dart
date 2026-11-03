import 'package:flutter/material.dart';

import '../theme/cosmic_colors.dart';

const tiniSlogan = 'Zevkini keşfet, her önerinin nedenini gör.';

/// Tını işareti: kozmik gradyanlı yuvarlak içinde "T" ve iki yandan yayılan ses dalgaları.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 96});
  final double size;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [c.primary, const Color(0xFFB0307F)],
        ),
        boxShadow: [
          BoxShadow(
              color: c.primary.withValues(alpha: 0.35), blurRadius: size * 0.4, spreadRadius: 1),
        ],
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Icon(Icons.graphic_eq_rounded, size: size * 0.78, color: Colors.white24),
          Text('T',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: size * 0.52,
                  fontWeight: FontWeight.w800,
                  height: 1)),
        ],
      ),
    );
  }
}

/// Uygulama adı ve slogan; giriş ve yükleme ekranlarında ortak.
class BrandHeader extends StatelessWidget {
  const BrandHeader({super.key, this.markSize = 96});
  final double markSize;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        BrandMark(size: markSize),
        const SizedBox(height: 20),
        Text('Tını',
            style: theme.textTheme.displayMedium
                ?.copyWith(fontWeight: FontWeight.w800, letterSpacing: 1)),
        const SizedBox(height: 8),
        Text(tiniSlogan,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
      ],
    );
  }
}

/// Açılışta oturum ve tema okunurken görünen ekran: işaret hafifçe nefes alır.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))
        ..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ScaleTransition(
        scale: Tween(begin: 0.94, end: 1.04)
            .animate(CurvedAnimation(parent: _c, curve: Curves.easeInOut)),
        child: const BrandHeader(),
      ),
    );
  }
}
