import 'package:flutter/material.dart';

import 'cosmic_colors.dart';
import 'tini_tokens.dart';

/// Şekil ve boşluk ölçüsü: 4'ün katları, tek kaynak. Yeni yarıçaplar [TiniTokens] içindedir.
abstract final class TiniShape {
  static const double card = 12;
  static const double cover = 8;
  static const double gutter = 16;
  static const double s1 = 4, s2 = 8, s3 = 12, s4 = 16, s5 = 24;
}

/// Tip ölçeği [TiniTokens] yazı stillerinden gelir (Inter / Inter Display).
/// Metin üç kademe: birincil, [TiniCosmicColors.textSecondary], [TiniCosmicColors.textTertiary].
TextTheme tiniTextTheme(TextTheme base, TiniCosmicColors c) {
  TextStyle? t(TextStyle? s, TextStyle token, {Color? color}) =>
      s?.merge(token).copyWith(color: color);
  return base.copyWith(
    headlineSmall: t(base.headlineSmall, TiniTokens.screenTitle),
    titleLarge: t(base.titleLarge, TiniTokens.section),
    titleMedium: t(base.titleMedium, TiniTokens.cardTitle.copyWith(fontSize: 16)),
    titleSmall: t(base.titleSmall, TiniTokens.bodyStrong),
    bodyLarge: t(base.bodyLarge, TiniTokens.body.copyWith(fontSize: 16)),
    bodyMedium: t(base.bodyMedium, TiniTokens.body, color: c.textSecondary),
    bodySmall: t(base.bodySmall, TiniTokens.secondary, color: c.textTertiary),
    labelMedium: t(base.labelMedium, TiniTokens.secondary.copyWith(fontWeight: FontWeight.w600), color: c.textSecondary),
    labelSmall: t(base.labelSmall, TiniTokens.caption, color: c.textTertiary),
  ).apply(fontFamily: 'Inter');
}
