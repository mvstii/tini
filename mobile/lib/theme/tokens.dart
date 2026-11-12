import 'package:flutter/material.dart';

import 'cosmic_colors.dart';

/// Şekil ve boşluk ölçüsü: 4'ün katları, tek kaynak.
abstract final class TiniShape {
  static const double card = 12;
  static const double cover = 8;
  static const double gutter = 16;
  static const double s1 = 4, s2 = 8, s3 = 12, s4 = 16, s5 = 24;
}

/// Tip ölçeği: ekran başlığı 28/700, bölüm 20/700, kart başlığı 16/600, gövde 14, caption 12.
/// Metin üç kademe: birincil, [TiniCosmicColors.textSecondary], [TiniCosmicColors.textTertiary].
TextTheme tiniTextTheme(TextTheme base, TiniCosmicColors c) {
  TextStyle? t(TextStyle? s, double size, FontWeight w, {Color? color, double? height}) =>
      s?.copyWith(fontFamily: 'PlusJakartaSans', fontSize: size, fontWeight: w, color: color, height: height, letterSpacing: 0);
  return base.copyWith(
    headlineSmall: t(base.headlineSmall, 28, FontWeight.w700, height: 1.15),
    titleLarge: t(base.titleLarge, 20, FontWeight.w700, height: 1.2),
    titleMedium: t(base.titleMedium, 16, FontWeight.w600, height: 1.25),
    titleSmall: t(base.titleSmall, 14, FontWeight.w600),
    bodyLarge: t(base.bodyLarge, 16, FontWeight.w400, height: 1.4),
    bodyMedium: t(base.bodyMedium, 14, FontWeight.w400, color: c.textSecondary, height: 1.4),
    bodySmall: t(base.bodySmall, 12, FontWeight.w400, color: c.textTertiary),
    labelMedium: t(base.labelMedium, 12, FontWeight.w600, color: c.textSecondary),
    labelSmall: t(base.labelSmall, 11, FontWeight.w500, color: c.textTertiary),
  ).apply(fontFamily: 'PlusJakartaSans');
}
