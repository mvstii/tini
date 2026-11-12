import 'package:flutter/material.dart';

import '../strings.dart';
import 'tini_tokens.dart';

/// Oy kademesinin (veya "Dinlemedim"in) görünümü: dolgu, metin/simge, kenarlık.
class VoteStyle {
  const VoteStyle(this.fill, this.fg, this.border, this.icon, this.label, {this.borderWidth = 1.5, this.gradient});
  final Color fill;
  final Color fg;
  final Color border;
  final IconData icon;
  final String label;
  final double borderWidth;

  /// Efsane (6) için marka gradyanı; diğer kademelerde null. Doluysa dolgu yerine bu çizilir.
  final Gradient? gradient;
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
    scaffold: Color(0xFF050309),
    card: Color(0xFF110B22),
    raised: Color(0xFF1A1233),
    highlight: Color(0xFF2B1D50),
    textSecondary: Color(0xFFBCB4D2),
    textTertiary: Color(0xFF7B7396),
    primary: Color(0xFFD0BCFF),
    votes: {
      1: VoteStyle(Color(0xFF3C172D), Color(0xFFFF9DA6), Color(0xFFFF4D5E),
          Icons.heart_broken_rounded, TiniStrings.voteN1),
      2: VoteStyle(Color(0xFF3C222A), Color(0xFFFFBF9D), Color(0xFFFF8A4C),
          Icons.thumb_down_off_alt_rounded, TiniStrings.voteN2),
      3: VoteStyle(Color(0xFF3C2C29), Color(0xFFFFDD9C), Color(0xFFFFC24B),
          Icons.remove_circle_outline_rounded, TiniStrings.voteN3),
      4: VoteStyle(Color(0xFF2B312C), Color(0xFFCCEEA5), Color(0xFFA3E05C),
          Icons.thumb_up_off_alt_rounded, TiniStrings.voteN4),
      5: VoteStyle(Color(0xFF19303C), Color(0xFF94EAD6), Color(0xFF3DD9B5),
          Icons.favorite_border_rounded, TiniStrings.voteN5),
      6: VoteStyle(Color(0xFF271C4A), Color(0xFFFFFFFF), Color(0xFF8A6BFF),
          Icons.auto_awesome_rounded, TiniStrings.voteN6,
          gradient: TiniVote.efsaneGradient, borderWidth: 2),
    },
    skip: VoteStyle(Color(0xFF14121D), Color(0xFF8A8496), Color(0xFF363242),
        Icons.skip_next_rounded, TiniStrings.skip),
  );

  static const light = TiniCosmicColors(
    scaffold: Color(0xFFF3EEFC),
    card: Color(0xFFFFFFFF),
    raised: Color(0xFFEAE2F8),
    highlight: Color(0xFFDCD0F2),
    textSecondary: Color(0xFF4F495E),
    textTertiary: Color(0xFF7A7489),
    primary: Color(0xFF6750A4),
    votes: {
      1: VoteStyle(Color(0xFFFFDBDF), Color(0xFF52191E), Color(0xFFFF4D5E),
          Icons.heart_broken_rounded, TiniStrings.voteN1),
      2: VoteStyle(Color(0xFFFFE8DB), Color(0xFF522C18), Color(0xFFFF8A4C),
          Icons.thumb_down_off_alt_rounded, TiniStrings.voteN2),
      3: VoteStyle(Color(0xFFFFF3DB), Color(0xFF523E18), Color(0xFFFFC24B),
          Icons.remove_circle_outline_rounded, TiniStrings.voteN3),
      4: VoteStyle(Color(0xFFEDF9DE), Color(0xFF34481D), Color(0xFFA3E05C),
          Icons.thumb_up_off_alt_rounded, TiniStrings.voteN4),
      5: VoteStyle(Color(0xFFD8F7F0), Color(0xFF14453A), Color(0xFF3DD9B5),
          Icons.favorite_border_rounded, TiniStrings.voteN5),
      6: VoteStyle(Color(0xFFE8E1FF), Color(0xFFFFFFFF), Color(0xFF8A6BFF),
          Icons.auto_awesome_rounded, TiniStrings.voteN6,
          gradient: TiniVote.efsaneGradient, borderWidth: 2),
    },
    skip: VoteStyle(Color(0xFFE6E2EE), Color(0xFF4D4857), Color(0xFF9993A6),
        Icons.skip_next_rounded, TiniStrings.skip),
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
