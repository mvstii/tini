import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tini/widgets/studio.dart';

void main() {
  testWidgets('Hoverable grows on hover and shrinks back', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Center(child: Hoverable(child: SizedBox(key: Key('t'), width: 40, height: 40))),
    ));
    double scale() => tester.widget<AnimatedScale>(find.byType(AnimatedScale)).scale;
    expect(scale(), 1);

    final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
    await mouse.addPointer(location: Offset.zero);
    await mouse.moveTo(tester.getCenter(find.byKey(const Key('t'))));
    await tester.pump();
    expect(scale(), 1.04);

    await mouse.moveTo(const Offset(500, 500));
    await tester.pump();
    expect(scale(), 1);
  });

  testWidgets('Hoverable stays still when disabled', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Center(
          child: Hoverable(enabled: false, child: SizedBox(key: Key('t'), width: 40, height: 40))),
    ));
    final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
    await mouse.addPointer(location: Offset.zero);
    await mouse.moveTo(tester.getCenter(find.byKey(const Key('t'))));
    await tester.pump();
    expect(tester.widget<AnimatedScale>(find.byType(AnimatedScale)).scale, 1);
  });

  testWidgets('StateNote.error shows retry; empty does not', (tester) async {
    var retried = 0;
    await tester.pumpWidget(MaterialApp(
      home: Column(children: [
        StateNote.error('Sunucuya ulaşılamadı', onRetry: () => retried++),
        const StateNote.empty('Henüz oy yok.'),
      ]),
    ));
    expect(find.text('Yeniden dene'), findsOneWidget);
    await tester.tap(find.text('Yeniden dene'));
    expect(retried, 1);
    expect(find.text('Henüz oy yok.'), findsOneWidget);
  });
}
