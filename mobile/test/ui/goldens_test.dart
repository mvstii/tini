// Altın (golden) testleri: VoteButton 6 oy × 3 durum, TrackRow 4 slot,
// ServiceSaveButton 4 durum × 2 servis. Görseller test/ui/goldens/ altında.
// Yenilemek için: flutter test --update-goldens test/ui/goldens_test.dart
// Not: görseller Inter yazı tipiyle Windows'ta üretildi; başka platformda piksel farkı olabilir.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tini/theme/cosmic_colors.dart';
import 'package:tini/theme/tini_tokens.dart';
import 'package:tini/ui/components/components.dart';

Widget _frame(Widget child, {double w = 390}) => MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        fontFamily: 'Inter',
        extensions: [TiniCosmicColors.dark, TiniTokens.dark],
      ),
      home: Scaffold(
        backgroundColor: TiniTokens.dark.bg,
        body: Align(
          alignment: Alignment.topLeft,
          child: RepaintBoundary(
            child: Container(
              width: w,
              color: TiniTokens.dark.bg,
              padding: const EdgeInsets.all(16),
              child: child,
            ),
          ),
        ),
      ),
    );

void main() {
  // Görseller Windows'ta üretildi ve yazı tipi yolu Windows'a özgü; CI (Linux) bu testleri atlar.
  final skip = Platform.isWindows ? null : 'Windows için üretilmiş görseller';
  setUpAll(() async {
    if (skip != null) return;
    final inter = FontLoader('Inter')
      ..addFont(Future.value(ByteData.view(File('assets/fonts/Inter.ttf').readAsBytesSync().buffer)));
    await inter.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(Future.value(ByteData.view(
          File('C:/dev/flutter/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf').readAsBytesSync().buffer)));
    await icons.load();
  });

  Future<void> shot(WidgetTester tester, Widget w, String name, {Size size = const Size(420, 400)}) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_frame(w, w: size.width));
    await tester.pump(const Duration(milliseconds: 400));
    await expectLater(find.byType(RepaintBoundary).first, matchesGoldenFile('goldens/$name.png'));
  }

  testWidgets('VoteButton 6 oy × 3 durum', (tester) async {
    await shot(
      tester,
      Column(
        children: [
          for (final st in VoteButtonState.values) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [for (var v = 1; v <= 6; v++) VoteButton(value: v, state: st)],
              ),
            ),
          ],
        ],
      ),
      'vote_button',
      size: const Size(420, 290),
    );
  }, skip: skip != null);

  testWidgets('TrackRow 4 slot', (tester) async {
    await shot(
      tester,
      const Column(
        children: [
          TrackRow(title: 'Örnek A', artist: 'Sanatçı', slot: TrackSlot.fit, reason: 'Gerekçe satırı', fit: 94),
          TrackRow(title: 'Örnek B', artist: 'Sanatçı', slot: TrackSlot.fresh, reason: 'Gerekçe satırı', fit: 88, isNew: true),
          TrackRow(title: 'Örnek C', artist: 'Sanatçı', slot: TrackSlot.unheard, reason: 'Gerekçe satırı', fit: 86),
          TrackRow(title: 'Örnek D', artist: 'Sanatçı', slot: TrackSlot.explore, reason: 'Gerekçe satırı', fit: 72),
        ],
      ),
      'track_row',
      size: const Size(420, 380),
    );
  }, skip: skip != null);

  testWidgets('ServiceSaveButton 4 durum × 2 servis', (tester) async {
    await shot(
      tester,
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final svc in ServiceKind.values)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [for (final s in SaveState.values) ServiceSaveButton(service: svc, state: s, compact: true)],
              ),
            ),
        ],
      ),
      'service_save_button',
      size: const Size(420, 260),
    );
  }, skip: skip != null);
}
