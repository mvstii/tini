import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tini/strings.dart';
import 'package:tini/theme/cosmic_colors.dart';
import 'package:tini/theme/tini_tokens.dart';
import 'package:tini/ui/components/components.dart';

Widget host(Widget child, {Brightness b = Brightness.dark, double width = 390}) {
  final dark = b == Brightness.dark;
  return MaterialApp(
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      brightness: b,
      useMaterial3: true,
      fontFamily: 'Inter',
      extensions: [dark ? TiniCosmicColors.dark : TiniCosmicColors.light, dark ? TiniTokens.dark : TiniTokens.light],
    ),
    home: Scaffold(
      body: Center(child: SizedBox(width: width, child: child)),
    ),
  );
}

void main() {
  group('VoteButton / VoteRow', () {
    testWidgets('altı oy, anlamsal etiket "5, Çok iyi"', (tester) async {
      final handle = tester.ensureSemantics();
      int? got;
      await tester.pumpWidget(host(VoteRow(onVote: (v) => got = v)));
      expect(find.bySemanticsLabel('5, Çok iyi'), findsOneWidget);
      expect(find.bySemanticsLabel('6, Efsane'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('vote-4')));
      expect(got, 4);
      handle.dispose();
    });

    testWidgets('seçili oyda diğerleri pasifleşir, seçili %112 büyür', (tester) async {
      await tester.pumpWidget(host(VoteRow(selected: 5, onVote: (_) {})));
      await tester.pumpAndSettle();
      final scales = tester.widgetList<AnimatedScale>(find.byType(AnimatedScale)).map((e) => e.scale).toList();
      expect(scales, [1, 1, 1, 1, 1.12, 1]);
      final opac = tester.widgetList<Opacity>(find.byType(Opacity)).map((e) => e.opacity).toList();
      expect(opac, [0.45, 0.45, 0.45, 0.45, 1, 0.45]);
    });

    testWidgets('Efsane gradyandır', (tester) async {
      await tester.pumpWidget(host(const VoteButton(value: 6)));
      final box = tester.widget<AnimatedContainer>(find.byType(AnimatedContainer));
      expect((box.decoration as BoxDecoration).gradient, TiniVote.efsaneGradient);
    });

    testWidgets('VoteBadge ve PredictionPill etiketleri', (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(host(const Column(children: [VoteBadge(vote: 3), PredictionPill(vote: 4)])));
      expect(find.bySemanticsLabel('3, İdare eder'), findsOneWidget);
      expect(find.bySemanticsLabel('Tahmin: 4, İyi'), findsOneWidget);
      handle.dispose();
    });
  });

  group('UnheardButton', () {
    testWidgets('metin ve dokunma', (tester) async {
      var n = 0;
      await tester.pumpWidget(host(UnheardButton(onTap: () => n++)));
      expect(find.text(TiniStrings.unheardAdd), findsOneWidget);
      await tester.tap(find.byType(UnheardButton));
      expect(n, 1);
    });
  });

  group('TiniCover', () {
    test('aynı seed aynı renkleri verir, farklı seed farklılaşabilir', () {
      expect(TiniCover.colorsFor('a|b'), TiniCover.colorsFor('a|b'));
      expect(TiniCover.colorsFor('x').$1, isNot(TiniCover.colorsFor('x').$2));
    });
    testWidgets('url yoksa yedek kapak çizer', (tester) async {
      await tester.pumpWidget(host(const Align(alignment: Alignment.topLeft, child: TiniCover(seed: 's'))));
      expect(find.byIcon(Icons.music_note_rounded), findsOneWidget);
      expect(tester.getSize(find.byType(TiniCover)), const Size(50, 50));
    });
  });

  group('TrackRow', () {
    testWidgets('YENİ, gerekçe ve uyum yüzdesi; dokunuş çağırır', (tester) async {
      var n = 0;
      await tester.pumpWidget(host(TrackRow(
        title: 'T',
        artist: 'A',
        slot: TrackSlot.fresh,
        reason: 'gerekçe metni',
        fit: 88,
        isNew: true,
        onTap: () => n++,
      )));
      expect(find.text('YENİ'), findsOneWidget);
      expect(find.text('gerekçe metni'), findsOneWidget);
      expect(find.text('%88'), findsOneWidget);
      await tester.tap(find.byType(TrackRow));
      expect(n, 1);
    });
    testWidgets('fit yoksa yüzde gösterilmez', (tester) async {
      await tester.pumpWidget(host(const TrackRow(title: 'T', artist: 'A', slot: TrackSlot.fit, reason: 'r')));
      expect(find.text(TiniStrings.fitSuffix), findsNothing);
    });
  });

  group('ServiceSaveButton', () {
    testWidgets('dört durum metni', (tester) async {
      for (final (s, text) in [
        (SaveState.idle, TiniStrings.saveApple),
        (SaveState.saving, TiniStrings.saving),
        (SaveState.saved, TiniStrings.saved),
        (SaveState.notConnected, TiniStrings.connectApple),
      ]) {
        await tester.pumpWidget(host(ServiceSaveButton(service: ServiceKind.apple, state: s, onPressed: () {})));
        expect(find.text(text), findsOneWidget, reason: '$s');
      }
    });
    testWidgets('kaydediliyor/kaydedildi durumunda tıklanmaz; bağlı değilse bağlama çağrılır', (tester) async {
      var n = 0;
      for (final s in [SaveState.saving, SaveState.saved]) {
        await tester.pumpWidget(host(ServiceSaveButton(service: ServiceKind.spotify, state: s, onPressed: () => n++)));
        await tester.tap(find.byType(ServiceSaveButton));
      }
      expect(n, 0);
      await tester.pumpWidget(host(ServiceSaveButton(
          service: ServiceKind.spotify, state: SaveState.notConnected, onPressed: () => n++)));
      await tester.tap(find.byType(ServiceSaveButton));
      expect(n, 1);
    });
  });

  group('AnchorRow / TagChip / SlotBar', () {
    testWidgets('çapa yüzdesi ve oy', (tester) async {
      await tester.pumpWidget(host(const AnchorRow(title: 'T', artist: 'A', vote: 6, share: 0.54)));
      expect(find.text('%54'), findsOneWidget);
      expect(find.text('verdin'), findsOneWidget);
    });
    testWidgets('TagChip sayaç', (tester) async {
      await tester.pumpWidget(host(const TagChip(label: 'dream pop', count: 3)));
      expect(find.textContaining('×3', findRichText: true), findsOneWidget);
    });
    testWidgets('SlotBar 5 pt', (tester) async {
      await tester.pumpWidget(host(const SlotBar(value: 0.5)));
      expect(tester.getSize(find.byType(SlotBar)).height, 5);
    });
  });

  group('packCircles', () {
    test('çakışmaz, sınırlar içinde, deterministik', () {
      final radii = <double>[100, 70, 55, 40, 30];
      final a = packCircles(radii, width: 360, height: 300);
      final b = packCircles(radii, width: 360, height: 300);
      for (var i = 0; i < a.length; i++) {
        expect((a[i].x, a[i].y, a[i].r), (b[i].x, b[i].y, b[i].r));
        expect(a[i].x - a[i].r, greaterThanOrEqualTo(-1e-6));
        expect(a[i].x + a[i].r, lessThanOrEqualTo(360 + 1e-6));
        expect(a[i].y - a[i].r, greaterThanOrEqualTo(-1e-6));
        expect(a[i].y + a[i].r, lessThanOrEqualTo(300 + 1e-6));
        for (var j = i + 1; j < a.length; j++) {
          final d = Offset(a[i].x - a[j].x, a[i].y - a[j].y).distance;
          expect(d, greaterThanOrEqualTo(a[i].r + a[j].r - 1e-6), reason: '$i-$j');
        }
      }
    });
    test('sığmayan yarıçaplar küçültülür; sıra korunur', () {
      final p = packCircles(<double>[400, 300, 200], width: 300, height: 300);
      expect(p.length, 3);
      expect(p[0].r, greaterThan(p[1].r));
      expect(p[1].r, greaterThan(p[2].r));
      expect(p[0].r * 2, lessThanOrEqualTo(300 + 1e-6));
    });
    test('boş liste', () => expect(packCircles(const [], width: 10, height: 10), isEmpty));
  });

  group('modeKindFor', () {
    test('baskın etikete göre simge', () {
      expect(modeKindFor(['Dream Pop']), ModeKind.moon);
      expect(modeKindFor(['anadolu rock']), ModeKind.spiral);
      expect(modeKindFor(['trip-hop']), ModeKind.record);
      expect(modeKindFor(['funk']), ModeKind.bolt);
      expect(modeKindFor(['alt rock']), ModeKind.wave);
      expect(modeKindFor(const []), ModeKind.wave);
    });
  });

  group('ModeBubbleField / VoteDistributionChart', () {
    testWidgets('balonlar çizilir; anchors yoksa çapa satırı yok', (tester) async {
      await tester.pumpWidget(host(const ModeBubbleField(modes: [
        ModeData(name: 'Mod A', share: 0.6, anchors: 9),
        ModeData(name: 'Mod B', share: 0.4),
      ])));
      expect(find.byType(ModeBubble), findsNWidgets(2));
      expect(find.textContaining('9 çapa'), findsOneWidget);
    });
    testWidgets('grafik 6 çubuk etiketi', (tester) async {
      await tester.pumpWidget(host(const VoteDistributionChart(counts: [1, 2, 3, 4, 5, 6])));
      for (var i = 1; i <= 6; i++) {
        expect(find.text('$i'), findsOneWidget);
      }
    });
  });

  group('ClipPlayer', () {
    test('dalga formu deterministik ve aralıkta', () {
      final a = ClipPlayer.waveform('seed', 36);
      expect(a, ClipPlayer.waveform('seed', 36));
      expect(a.every((v) => v > 0.1 && v <= 1), isTrue);
    });
    testWidgets('süre ve oynat/duraklat', (tester) async {
      var n = 0;
      await tester.pumpWidget(host(ClipPlayer(seed: 's', progress: 0.5, playing: false, onToggle: () => n++)));
      expect(find.text('0:15 / 0:30'), findsOneWidget);
      await tester.tap(find.byIcon(Icons.play_arrow_rounded));
      expect(n, 1);
    });
  });

  group('MiniPlayer / TiniTabBar', () {
    testWidgets('MiniPlayer 58 pt yüksekliğinde', (tester) async {
      await tester.pumpWidget(host(MiniPlayer(
          title: 'T', artist: 'A', sourceLabel: 'S', vote: 5, progress: 0.3, playing: true, onToggle: () {})));
      expect(tester.getSize(find.byType(MiniPlayer)).height, MiniPlayer.height);
      expect(find.text('A · S'), findsOneWidget);
    });
    testWidgets('Tab çubuğu: bekleyen oy rozeti ve seçim', (tester) async {
      final handle = tester.ensureSemantics();
      int? sel;
      await tester.pumpWidget(host(TiniTabBar(index: 0, pendingVotes: 12, onSelect: (i) => sel = i)));
      expect(find.text('12'), findsOneWidget);
      expect(find.bySemanticsLabel('Oyla, 12 bekleyen'), findsOneWidget);
      await tester.tap(find.text(TiniStrings.tabProfile));
      expect(sel, 3);
      handle.dispose();
    });
    testWidgets('Rozet yalnızca Oyla sekmesinde ve 0 ise yok', (tester) async {
      await tester.pumpWidget(host(TiniTabBar(index: 1, onSelect: (_) {})));
      expect(find.text('0'), findsNothing);
    });
  });

  testWidgets('açık temada da çizilir', (tester) async {
    await tester.pumpWidget(host(
      Column(children: [
        VoteRow(selected: 6, onVote: (_) {}),
        const TrackRow(title: 'T', artist: 'A', slot: TrackSlot.unheard, reason: 'r', fit: 80),
        const ServiceSaveButton(service: ServiceKind.spotify),
      ]),
      b: Brightness.light,
    ));
    expect(tester.takeException(), isNull);
  });
}
