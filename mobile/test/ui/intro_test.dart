import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tini/screens/intro_screen.dart';
import 'package:tini/strings.dart';
import 'package:tini/theme/cosmic_colors.dart';
import 'package:tini/theme/tini_tokens.dart';
import 'package:tini/widgets/info_sheet.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: ThemeData(extensions: [TiniCosmicColors.light, TiniTokens.light]),
      home: child,
    );

void main() {
  testWidgets('skip calls onDone from the first page', (tester) async {
    var done = 0;
    await tester.pumpWidget(_wrap(IntroScreen(onDone: () => done++)));
    expect(find.text(TiniStrings.introSkip), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('intro-skip')));
    expect(done, 1);
  });

  testWidgets('next walks all pages then Başla finishes', (tester) async {
    var done = 0;
    await tester.pumpWidget(_wrap(IntroScreen(onDone: () => done++)));
    for (var i = 0; i < TiniStrings.introPages.length - 1; i++) {
      await tester.tap(find.byKey(const ValueKey('intro-next')));
      await tester.pumpAndSettle();
    }
    expect(find.text(TiniStrings.introStart), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('intro-next')));
    expect(done, 1);
  });

  testWidgets('info icon opens sheet and closes', (tester) async {
    await tester.pumpWidget(_wrap(const Scaffold(
      body: InfoIconButton(title: 'T', body: 'Gövde metni'),
    )));
    await tester.tap(find.byType(InfoIconButton));
    await tester.pumpAndSettle();
    expect(find.text('Gövde metni'), findsOneWidget);
    await tester.tap(find.text(TiniStrings.infoClose));
    await tester.pumpAndSettle();
    expect(find.text('Gövde metni'), findsNothing);
  });
}
