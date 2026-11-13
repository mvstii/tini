import 'package:flutter/material.dart';

import 'cosmic_colors.dart';

/// Oy skalası (1–6): renk ve gradyan tek yerden; her ekranda aynıdır.
abstract final class TiniVote {
  static const c1 = Color(0xFFFF4D5E);
  static const c2 = Color(0xFFFF8A4C);
  static const c3 = Color(0xFFFFC24B);
  static const c4 = Color(0xFFA3E05C);
  static const c5 = Color(0xFF3DD9B5);
  static const efsaneStart = Color(0xFF8A6BFF);
  static const efsaneEnd = Color(0xFFFF4FD8);

  /// 120°: sol üstten sağ alta.
  static const efsaneGradient = LinearGradient(
    begin: Alignment(-0.866, -0.5),
    end: Alignment(0.866, 0.5),
    colors: [efsaneStart, efsaneEnd],
  );

  /// 1–5 için düz renk; 6 (Efsane) gradyandır, düz renk olarak başlangıç tonu döner.
  static Color color(int vote) => switch (vote) {
        1 => c1,
        2 => c2,
        3 => c3,
        4 => c4,
        5 => c5,
        _ => efsaneStart,
      };

  /// Efsane için gradyan, diğerleri için null.
  static Gradient? gradient(int vote) => vote == 6 ? efsaneGradient : null;
}

/// Tasarım tokenları: yüzey rolleri, oy/slot/servis renkleri, tipografi, yarıçap ve boşluk.
/// Ekran kodunda sabit renk, yazı boyu veya yarıçap yazılmaz; hepsi buradan gelir.
/// Yüzey rolleri galaksi paletine (koyu) ve lavanta paletine (açık) eşlenir.
@immutable
class TiniTokens extends ThemeExtension<TiniTokens> {
  const TiniTokens({
    required this.bg,
    required this.surface1,
    required this.surface2,
    required this.sheet,
    required this.line,
    required this.text,
    required this.muted,
    required this.muted2,
    required this.tabBar,
    required this.miniPlayer,
    required this.scrim,
  });

  // --- Yüzey rolleri ---
  final Color bg;
  final Color surface1;
  final Color surface2;
  final Color sheet;
  final Color line;
  final Color text;
  final Color muted;
  final Color muted2;

  /// %90 opaklık; arkasına 20 blur uygulanır.
  final Color tabBar;

  /// %96 opaklık; arkasına 20 blur uygulanır.
  final Color miniPlayer;
  final Color scrim;

  static final dark = TiniTokens(
    bg: TiniCosmicColors.dark.scaffold,
    surface1: TiniCosmicColors.dark.card,
    surface2: TiniCosmicColors.dark.raised,
    sheet: const Color(0xFF131316),
    line: const Color(0x14FFFFFF),
    text: const Color(0xFFF6F4FB),
    muted: TiniCosmicColors.dark.textSecondary,
    muted2: TiniCosmicColors.dark.textTertiary,
    tabBar: const Color(0xE6050309),
    miniPlayer: const Color(0xF516131F),
    scrim: const Color(0x99000000),
  );

  static final light = TiniTokens(
    bg: TiniCosmicColors.light.scaffold,
    surface1: TiniCosmicColors.light.card,
    surface2: TiniCosmicColors.light.raised,
    sheet: const Color(0xFFFBF8FF),
    line: const Color(0x14000000),
    text: const Color(0xFF1B1530),
    muted: TiniCosmicColors.light.textSecondary,
    muted2: TiniCosmicColors.light.textTertiary,
    tabBar: const Color(0xE6F3EEFC),
    miniPlayer: const Color(0xF5FFFFFF),
    scrim: const Color(0x66000000),
  );

  // --- Marka ---
  /// Marka gradyanı = Efsane gradyanı; yalnızca logo, etkin sekme simgesi, ilerleme
  /// çubukları, avatar ve Efsane düğmesinde kullanılır.
  static const brandGradient = TiniVote.efsaneGradient;
  static const activeTab = Color(0xFFFF6FD0);

  // --- Slot renkleri ---
  static const slotFit = Color(0xFF3DD9B5);
  static const slotUnheard = Color(0xFFFFC24B);
  static const slotExplore = Color(0xFF8A6BFF);
  static const slotFresh = Color(0xFFFF4FD8);

  // --- Servis renkleri (logo yok; ad + simge rengiyle ayrışır) ---
  static const apple = Color(0xFFFA2D48);
  static const spotify = Color(0xFF1ED760);

  // --- Zevk modu simge renkleri ---
  static const modeMoon = Color(0xFF8A6BFF);
  static const modeSpiral = Color(0xFFFFC24B);
  static const modeRecord = Color(0xFF3DD9B5);
  static const modeBolt = Color(0xFFFF4FD8);
  static const modeWave = Color(0xFFFF8A4C);

  // --- Yüzey efektleri (ortak gölge, nebula, yıldız tozu) ---
  static const shadowDeep = Color(0x99000000);
  static const shadowDeeper = Color(0xCC000000);
  static const shadowTintLight = Color(0xFF4A3A8C);
  static const nebulaTopDark = Color(0xFF4B1F8C);
  static const nebulaBottomDark = Color(0xFF7A1B6B);
  static const nebulaTopLight = Color(0xFFB9A4E8);
  static const nebulaBottomLight = Color(0xFFF2B5D4);
  static const starDark = Color(0xFFE9DEFF);
  static const starLight = Color(0xFF8B6FD6);
  static const lightCardTop = Color(0xFFFFFFFF);
  static const lightCardBottom = Color(0xFFFAF8FF);
  static const lightAccent = Color(0xFF6750A4);
  static const onLightFill = Color(0xFF1B1030);
  static const pink = Color(0xFFE0479E);

  // Günün şarkısı kartı (keşfet kahramanı)
  static const heroFillDark = [Color(0xFF3E1F5E), Color(0xFF2A143D)];
  static const heroFillLight = [Color(0xFFF1EAFF), Color(0xFFE2D6FA)];
  static const heroEdgeDarkHi = Color(0xFFE8C98A);
  static const heroEdgeDarkLo = Color(0xFFB9A4E8);
  static const heroEdgeLightHi = Color(0xFFB08A3E);
  static const heroEdgeLightLo = Color(0xFF8E73D0);

  // Spotify bağlantı vurgusu: koyuda marka yeşili, açıkta okunur koyu ton
  static const spotifyOnLight = Color(0xFF138A3D);

  // --- Yarıçaplar ---
  static const double rCoverSmall = 8;
  static const double rCard = 16;
  static const double rHero = 22;
  static const double rVote = 26;
  static const double rSheet = 28;
  static const double rPill = 999;

  // --- Boşluk ---
  static const double pageMargin = 16;
  static const double listMargin = 16;
  static const double sectionGap = 20;

  // --- Bulanıklık ---
  static const double blur = 20;

  // --- Tipografi: Inter; başlıklar Inter Display (opsz ekseni 32), -%2,5 harf aralığı ---
  static TextStyle _inter(double size, double weight,
      {bool display = false, double spacing = 0, double? height}) {
    return TextStyle(
      fontFamily: 'Inter',
      fontSize: size,
      fontWeight: FontWeight.values[((weight / 100).round() - 1).clamp(0, 8)],
      fontVariations: [FontVariation('wght', weight), FontVariation('opsz', display ? 32 : 14)],
      letterSpacing: spacing * size,
      height: height,
    );
  }

  static final largeTitle = _inter(34, 800, display: true, spacing: -0.025, height: 1.1);
  static final heroTitle = _inter(34, 900, display: true, spacing: -0.025, height: 1.05);
  static final screenTitle = _inter(26, 800, display: true, spacing: -0.025, height: 1.12);
  static final section = _inter(18, 800, display: true, spacing: -0.025, height: 1.2);
  static final cardTitle = _inter(16, 800, display: true, spacing: -0.025, height: 1.2);
  static final body = _inter(13.5, 400, height: 1.4);
  static final bodyStrong = _inter(13.5, 600, height: 1.4);
  static final secondary = _inter(12, 500, height: 1.35);
  static final caption = _inter(11, 500, height: 1.3);

  /// Büyük harfe çevirmeyi çağıran yapar (`toUpperCase`).
  static final kicker = _inter(10.5, 700, spacing: 0.12);
  static final tabLabel = _inter(10.5, 600);

  /// Küçük rozet yazısı (ör. "YENİ"): 9 pt, kalın, geniş aralık.
  static final badge = _inter(9, 800, spacing: 0.11);

  /// Başlık üstü etiketi, 11 pt.
  static final kickerLarge = _inter(11, 700, spacing: 0.127);

  /// Avatar baş harfi: boyuta orantılı.
  static TextStyle initial(double box) => _inter(box * 0.42, 700);

  /// Logo harfi: boyuta orantılı.
  static TextStyle logoLetter(double box) => _inter(box * 0.52, 800, display: true, height: 1);

  /// Temaya kayıtlı tokenları verir; kayıtlı değilse parlaklığa göre seçer.
  static TiniTokens of(BuildContext context) {
    final theme = Theme.of(context);
    return theme.extension<TiniTokens>() ??
        (theme.brightness == Brightness.dark ? dark : light);
  }

  @override
  TiniTokens copyWith({Color? bg, Color? surface1, Color? surface2}) => TiniTokens(
        bg: bg ?? this.bg,
        surface1: surface1 ?? this.surface1,
        surface2: surface2 ?? this.surface2,
        sheet: sheet,
        line: line,
        text: text,
        muted: muted,
        muted2: muted2,
        tabBar: tabBar,
        miniPlayer: miniPlayer,
        scrim: scrim,
      );

  @override
  TiniTokens lerp(ThemeExtension<TiniTokens>? other, double t) {
    if (other is! TiniTokens) return this;
    return TiniTokens(
      bg: Color.lerp(bg, other.bg, t)!,
      surface1: Color.lerp(surface1, other.surface1, t)!,
      surface2: Color.lerp(surface2, other.surface2, t)!,
      sheet: Color.lerp(sheet, other.sheet, t)!,
      line: Color.lerp(line, other.line, t)!,
      text: Color.lerp(text, other.text, t)!,
      muted: Color.lerp(muted, other.muted, t)!,
      muted2: Color.lerp(muted2, other.muted2, t)!,
      tabBar: Color.lerp(tabBar, other.tabBar, t)!,
      miniPlayer: Color.lerp(miniPlayer, other.miniPlayer, t)!,
      scrim: Color.lerp(scrim, other.scrim, t)!,
    );
  }
}
