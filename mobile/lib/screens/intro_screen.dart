import 'package:flutter/material.dart';

import '../strings.dart';
import '../theme/tini_tokens.dart';

/// İlk açılış eğitimi: kaydırmalı sayfalar. Her sayfada "Eğitimi atla" vardır; bitince ya da
/// atlanınca [onDone] çağrılır.
class IntroScreen extends StatefulWidget {
  const IntroScreen({super.key, required this.onDone});
  final VoidCallback onDone;

  @override
  State<IntroScreen> createState() => _IntroScreenState();
}

class _IntroScreenState extends State<IntroScreen> {
  static const _icons = [
    Icons.graphic_eq_rounded,
    Icons.star_rate_rounded,
    Icons.hearing_rounded,
    Icons.bookmark_add_rounded,
    Icons.auto_awesome_rounded,
  ];
  final _controller = PageController();
  int _page = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _last => _page == TiniStrings.introPages.length - 1;

  void _next() {
    if (_last) {
      widget.onDone();
    } else {
      _controller.nextPage(duration: const Duration(milliseconds: 260), curve: Curves.easeOut);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    final primary = Theme.of(context).colorScheme.primary;
    final pages = TiniStrings.introPages;
    return Scaffold(
      backgroundColor: t.bg,
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                key: const ValueKey('intro-skip'),
                onPressed: widget.onDone,
                child: const Text(TiniStrings.introSkip),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _controller,
                itemCount: pages.length,
                onPageChanged: (i) => setState(() => _page = i),
                itemBuilder: (_, i) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(_icons[i], size: 84, color: primary),
                      const SizedBox(height: 28),
                      Text(
                        pages[i].$1,
                        textAlign: TextAlign.center,
                        style: TiniTokens.screenTitle.copyWith(color: t.text),
                      ),
                      const SizedBox(height: 14),
                      Text(
                        pages[i].$2,
                        textAlign: TextAlign.center,
                        style: TiniTokens.body.copyWith(color: t.muted, fontSize: 15),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < pages.length; i++)
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    width: i == _page ? 20 : 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: i == _page ? primary : t.line,
                      borderRadius: BorderRadius.circular(TiniTokens.rPill),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  key: const ValueKey('intro-next'),
                  onPressed: _next,
                  child: Text(_last ? TiniStrings.introStart : TiniStrings.introNext),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
