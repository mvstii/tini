import 'package:flutter/material.dart';

/// Oy kademesinin (veya "Dinlemedim"in) görünümü: dolgu, metin/simge, kenarlık.
class VoteStyle {
  const VoteStyle(this.fill, this.fg, this.border, this.icon, this.label, {this.borderWidth = 1.5});
  final Color fill;
  final Color fg;
  final Color border;
  final IconData icon;
  final String label;
  final double borderWidth;
}

/// "Kozmik Spektrum" paleti (buzdan altına geçiş); açık ve koyu temada tüm oylama
/// ekranı renkleri buradan gelir.
@immutable
class TiniCosmicColors extends ThemeExtension<TiniCosmicColors> {
  const TiniCosmicColors({
    required this.scaffold,
    required this.card,
    required this.raised,
    required this.highlight,
    required this.textSecondary,
    required this.textTertiary,
    required this.primary,
    required this.votes,
    required this.skip,
  });

  final Color scaffold;
  final Color card;

  /// Yüzey kademeleri: zemin < [card] < [raised] < [highlight]. Yükseklik gölgeyle değil,
  /// daha açık yüzeyle verilir (Spotify/Apple Music kuralı).
  final Color raised;
  final Color highlight;

  /// Metin kademeleri: birincil renk temadan, ikincil ve soluk buradan gelir.
  final Color textSecondary;
  final Color textTertiary;
  final Color primary;

  /// Anahtar 1..6.
  final Map<int, VoteStyle> votes;
  final VoteStyle skip;

  static const dark = TiniCosmicColors(
    scaffold: Color(0xFF0C0914),
    card: Color(0xFF171326),
    raised: Color(0xFF1F1A32),
    highlight: Color(0xFF2A2342),
    textSecondary: Color(0xFFB9B3C9),
    textTertiary: Color(0xFF767087),
    primary: Color(0xFFD0BCFF),
    votes: {
      1: VoteStyle(Color(0xFF162030), Color(0xFF99B8F0), Color(0xFF2E4566),
          Icons.heart_broken_rounded, 'Berbat'),
      2: VoteStyle(Color(0xFF1E2040), Color(0xFFB0B5F5), Color(0xFF3D4180),
          Icons.thumb_down_off_alt_rounded, 'Kötü'),
      3: VoteStyle(Color(0xFF2A223D), Color(0xFFC9B8EB), Color(0xFF534378),
          Icons.remove_circle_outline_rounded, 'Eh'),
      4: VoteStyle(Color(0xFF3E1F5E), Color(0xFFE2B8FF), Color(0xFF7B3FB8),
          Icons.thumb_up_off_alt_rounded, 'İyi'),
      5: VoteStyle(Color(0xFF59184A), Color(0xFFFFB0E8), Color(0xFFB33095),
          Icons.favorite_border_rounded, 'Harika'),
      6: VoteStyle(Color(0xFF4F3606), Color(0xFFFFE07D), Color(0xFFF5B82E),
          Icons.auto_awesome_rounded, 'Efsane',
          borderWidth: 2),
    },
    skip: VoteStyle(Color(0xFF14121D), Color(0xFF8A8496), Color(0xFF363242),
        Icons.skip_next_rounded, 'Dinlemedim · Geç'),
  );

  static const light = TiniCosmicColors(
    scaffold: Color(0xFFF7F4FC),
    card: Color(0xFFF0ECF9),
    raised: Color(0xFFE8E2F5),
    highlight: Color(0xFFDDD5EE),
    textSecondary: Color(0xFF4F495E),
    textTertiary: Color(0xFF7A7489),
    primary: Color(0xFF6750A4),
    votes: {
      1: VoteStyle(Color(0xFFDCE6F7), Color(0xFF0D1B33), Color(0xFF7A99C9),
          Icons.heart_broken_rounded, 'Berbat'),
      2: VoteStyle(Color(0xFFE1E2FA), Color(0xFF14163D), Color(0xFF858AD6),
          Icons.thumb_down_off_alt_rounded, 'Kötü'),
      3: VoteStyle(Color(0xFFEAE3F7), Color(0xFF221838), Color(0xFF9E8AC9),
          Icons.remove_circle_outline_rounded, 'Eh'),
      4: VoteStyle(Color(0xFFF3DCFF), Color(0xFF2D0A4E), Color(0xFFA86ADD),
          Icons.thumb_up_off_alt_rounded, 'İyi'),
      5: VoteStyle(Color(0xFFFFD9F2), Color(0xFF3D002E), Color(0xFFD959B8),
          Icons.favorite_border_rounded, 'Harika'),
      6: VoteStyle(Color(0xFFFFECB3), Color(0xFF261900), Color(0xFFD49B00),
          Icons.auto_awesome_rounded, 'Efsane',
          borderWidth: 2),
    },
    skip: VoteStyle(Color(0xFFE6E2EE), Color(0xFF4D4857), Color(0xFF9993A6),
        Icons.skip_next_rounded, 'Dinlemedim · Geç'),
  );

  /// Temaya kayıtlı uzantıyı verir; kayıtlı değilse (ör. düz `MaterialApp`) parlaklığa göre seçer.
  static TiniCosmicColors of(BuildContext context) {
    final theme = Theme.of(context);
    return theme.extension<TiniCosmicColors>() ??
        (theme.brightness == Brightness.dark ? dark : light);
  }

  @override
  TiniCosmicColors copyWith({Color? scaffold, Color? card, Color? primary}) => TiniCosmicColors(
        scaffold: scaffold ?? this.scaffold,
        card: card ?? this.card,
        raised: raised,
        highlight: highlight,
        textSecondary: textSecondary,
        textTertiary: textTertiary,
        primary: primary ?? this.primary,
        votes: votes,
        skip: skip,
      );

  @override
  TiniCosmicColors lerp(ThemeExtension<TiniCosmicColors>? other, double t) {
    if (other is! TiniCosmicColors) return this;
    return t < 0.5 ? this : other;
  }
}
