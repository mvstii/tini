import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../api.dart';
import '../app_state.dart';
import '../preview_player.dart';
import '../theme/cosmic_colors.dart';
import '../theme/transitions.dart';
import '../widgets/studio.dart';
import 'discover_screen.dart';
import 'profile_screen.dart';
import 'rating_screen.dart';
import 'recommendations_screen.dart';

/// Giriş yapılmış uygulamanın kabuğu: 3 sekme + yüzen "sliding pill" menü, ortak [AppState].
class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.api,
    required this.onLogout,
    this.themeMode = ThemeMode.system,
    this.onThemeChanged,
  });
  final Api api;
  final VoidCallback onLogout;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode>? onThemeChanged;

  @override
  State<AppShell> createState() => _AppShellState();
}

const _navHeight = 56.0;
const _navBottom = 12.0;

/// Sekme içeriğinin menünün altında kalmaması için ayrılan alt boşluk.
const navInset = _navHeight + _navBottom + 12;

class _AppShellState extends State<AppShell> with WidgetsBindingObserver {
  late final AppState _state = AppState(widget.api);
  int _tab = 1; // açılışta Oylama; Keşfet solda (0)
  bool _seenRecs = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  /// Uygulama arka plana alınınca (ya da kilit/uygulama değiştirici açılınca) önizleme susar.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) PreviewController.instance.stop();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    PreviewController.instance.stop();
    _state.dispose();
    super.dispose();
  }

  void _go(int i) => setState(() {
        if (i != _tab) PreviewController.instance.stop();
        _tab = i;
        if (i == 2) _seenRecs = true;
      });

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final content = Stack(
      children: [
        Stack(
          fit: StackFit.expand,
          children: [
            for (final (i, w) in [
              DiscoverScreen(
              api: widget.api,
              state: _state,
              onLogout: widget.onLogout,
              onOpenRating: () => _go(1),
              onOpenProfile: () => _go(3),
              bottomInset: navInset,
            ),
            RatingScreen(
              api: widget.api,
              state: _state,
              onLogout: widget.onLogout,
              onOpenRecommendations: () => _go(2),
              bottomInset: navInset,
            ),
            RecommendationsScreen(
              api: widget.api,
              state: _state,
              onLogout: widget.onLogout,
              onContinue: () => _go(1),
            ),
            ProfileScreen(
              api: widget.api,
              state: _state,
              onLogout: widget.onLogout,
              themeMode: widget.themeMode,
              onThemeChanged: widget.onThemeChanged,
            ),
            ].indexed)
              TabPane(active: _tab == i, child: w),
          ],
        ),
        Positioned(
          left: 24,
          right: 24,
          bottom: _navBottom,
          child: ListenableBuilder(
            listenable: _state,
            builder: (_, _) =>
                PillNav(index: _tab, onTap: _go, badge: _state.unlocked && !_seenRecs),
          ),
        ),
      ],
    );
    return Scaffold(
      backgroundColor: c.scaffold,
      body: AmbientBackground(
        child: kDebugMode
          ? Column(
              children: [
                SafeArea(
                  bottom: false,
                  child: _DebugBar(state: _state, onThemeChanged: widget.onThemeChanged),
                ),
                Expanded(
                  child: MediaQuery.removePadding(
                      context: context, removeTop: true, child: content),
                ),
              ],
            )
          : content,
      ),
    );
  }
}

/// Yüzen kapsül menü; seçili sekmenin altındaki vurgu `AnimatedAlign` ile kayar.
class PillNav extends StatelessWidget {
  const PillNav({super.key, required this.index, required this.onTap, this.badge = false});
  final int index;
  final ValueChanged<int> onTap;
  final bool badge;

  static const _tabs = [
    (Icons.explore_rounded, 'Keşfet'),
    (Icons.tune_rounded, 'Oylama'),
    (Icons.auto_awesome_motion_rounded, 'Öneriler'),
    (Icons.person_outline_rounded, 'Profil'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final theme = Theme.of(context);
    return Container(
      height: _navHeight,
      decoration: BoxDecoration(
        color: theme.brightness == Brightness.dark
            ? theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.92)
            : Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(
            color: theme.brightness == Brightness.dark
                ? theme.colorScheme.outlineVariant
                : c.primary.withValues(alpha: 0.14)),
        boxShadow: [
          BoxShadow(
              color: theme.brightness == Brightness.dark
                  ? const Color(0x33000000)
                  : const Color(0xFF4A3A8C).withValues(alpha: 0.16),
              blurRadius: 20,
              offset: const Offset(0, 6)),
        ],
      ),
      child: Stack(
        children: [
          AnimatedAlign(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutCubic,
            alignment: Alignment(-1 + 2 * index / (_tabs.length - 1), 0),
            child: FractionallySizedBox(
              widthFactor: 1 / _tabs.length,
              heightFactor: 1,
              child: Padding(
                padding: const EdgeInsets.all(4),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: c.primary.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(24),
                  ),
                ),
              ),
            ),
          ),
          Row(
            children: [
              for (var i = 0; i < _tabs.length; i++)
                Expanded(
                  child: Semantics(
                    button: true,
                    selected: i == index,
                    label: i == 2 && badge ? '${_tabs[i].$2}, yeni öneriler var' : _tabs[i].$2,
                    excludeSemantics: true,
                    onTap: () => onTap(i),
                    child: InkWell(
                    key: ValueKey('tab-$i'),
                    customBorder: const StadiumBorder(),
                    onTap: () => onTap(i),
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Stack(
                            clipBehavior: Clip.none,
                            children: [
                              Icon(_tabs[i].$1,
                                  size: 22,
                                  color: i == index ? c.primary : theme.colorScheme.onSurfaceVariant),
                              if (i == 2 && badge)
                                Positioned(
                                  key: const ValueKey('recs-badge'),
                                  right: -3,
                                  top: -1,
                                  child: Container(
                                    width: 6,
                                    height: 6,
                                    decoration: BoxDecoration(
                                      color: c.votes[6]!.fg,
                                      shape: BoxShape.circle,
                                      boxShadow: [
                                        BoxShadow(
                                            color: c.votes[6]!.fg.withValues(alpha: 0.7),
                                            blurRadius: 4),
                                      ],
                                    ),
                                  ),
                                ),
                            ],
                          ),
                          Text(_tabs[i].$2,
                              style: theme.textTheme.labelSmall?.copyWith(
                                  height: 1.2,
                                  color: i == index
                                      ? c.primary
                                      : theme.colorScheme.onSurfaceVariant)),
                        ],
                      ),
                    ),
                  ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Yalnızca debug yapıda: ekran durumunu zorlama, hızlı 30 oy ve tema anahtarı.
class _DebugBar extends StatelessWidget {
  const _DebugBar({required this.state, required this.onThemeChanged});
  final AppState state;
  final ValueChanged<ThemeMode>? onThemeChanged;

  static const _names = {
    UiState.normal: 'Normal',
    UiState.loading: 'Loading (Skeleton)',
    UiState.queueFetching: 'QueueFetching (Kuyruk Doluyor)',
    UiState.error: 'Error (Bağlantı Hatası)',
  };

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    return ListenableBuilder(
      listenable: state,
      builder: (_, _) => Container(
        height: 36,
        color: c.card,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(
          children: [
            Text('DEBUG', style: Theme.of(context).textTheme.labelSmall),
            const Spacer(),
            PopupMenuButton<UiState>(
              tooltip: 'Ekran durumu',
              initialValue: state.forced,
              icon: const Icon(Icons.tune_rounded, size: 20),
              onSelected: state.setForced,
              itemBuilder: (_) => [
                for (final e in _names.entries) PopupMenuItem(value: e.key, child: Text(e.value)),
              ],
            ),
            IconButton(
              tooltip: 'Hızlı 30 oy',
              iconSize: 20,
              onPressed: state.debugUnlock,
              icon: const Icon(Icons.bolt_rounded),
            ),
            IconButton(
              tooltip: 'Tema',
              iconSize: 20,
              onPressed: onThemeChanged == null
                  ? null
                  : () => onThemeChanged!(dark ? ThemeMode.light : ThemeMode.dark),
              icon: Icon(dark ? Icons.light_mode_rounded : Icons.dark_mode_rounded),
            ),
          ],
        ),
      ),
    );
  }
}

