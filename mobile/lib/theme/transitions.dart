import 'package:flutter/material.dart';

/// Tını sayfa geçişi: yeni sayfa hafifçe sağdan kayarak belirir, eski sayfa geriye çekilip solar.
/// Platform bağımsızdır (Android ve iOS aynı hissi verir); geri hareketi tersine oynar.
class TiniPageTransitionsBuilder extends PageTransitionsBuilder {
  const TiniPageTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    final enter = CurvedAnimation(
        parent: animation, curve: Curves.easeOutCubic, reverseCurve: Curves.easeInCubic);
    final exit = CurvedAnimation(parent: secondaryAnimation, curve: Curves.easeInOutCubic);
    return FadeTransition(
      opacity: Tween<double>(begin: 1, end: 0.0).animate(exit),
      child: SlideTransition(
        position: Tween<Offset>(begin: Offset.zero, end: const Offset(-0.06, 0)).animate(exit),
        child: FadeTransition(
          opacity: enter,
          child: SlideTransition(
            position: Tween<Offset>(begin: const Offset(0.08, 0), end: Offset.zero).animate(enter),
            child: child,
          ),
        ),
      ),
    );
  }
}

const tiniPageTransitions = PageTransitionsTheme(builders: {
  TargetPlatform.android: TiniPageTransitionsBuilder(),
  TargetPlatform.iOS: TiniPageTransitionsBuilder(),
  TargetPlatform.windows: TiniPageTransitionsBuilder(),
  TargetPlatform.linux: TiniPageTransitionsBuilder(),
  TargetPlatform.macOS: TiniPageTransitionsBuilder(),
});

/// Sekme gövdesi: etkin değilken gizlenir ama durumu korunur; etkinleşince solarak ve hafif
/// yukarı kayarak belirir. Gizliyken (animasyon bitince) `Offstage`'dir, bu yüzden test ve
/// erişilebilirlik ağacında yinelenmez.
class TabPane extends StatefulWidget {
  const TabPane({super.key, required this.active, required this.child});
  final bool active;
  final Widget child;

  @override
  State<TabPane> createState() => _TabPaneState();
}

class _TabPaneState extends State<TabPane> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 260),
    value: widget.active ? 1 : 0,
  )..addStatusListener((_) => setState(() {}));
  late final Animation<double> _curve = CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);

  @override
  void didUpdateWidget(TabPane old) {
    super.didUpdateWidget(old);
    if (widget.active != old.active) widget.active ? _c.forward() : _c.reverse();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Offstage(
      offstage: !widget.active && _c.isDismissed,
      child: IgnorePointer(
        ignoring: !widget.active,
        child: FadeTransition(
          opacity: _curve,
          child: SlideTransition(
            position: Tween<Offset>(begin: const Offset(0, 0.025), end: Offset.zero)
                .animate(_curve),
            child: widget.child,
          ),
        ),
      ),
    );
  }
}
