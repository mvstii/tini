import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../api.dart';
import '../app_state.dart';
import '../preview_player.dart';
import '../theme/cosmic_colors.dart';
import '../ui/components/components.dart';
import '../ui/components/gallery_screen.dart';
import '../theme/transitions.dart';
import '../widgets/preview_widgets.dart';
import '../widgets/studio.dart';
import 'discover_screen.dart';
import 'profile_screen.dart';
import 'rating_screen.dart';
import 'recommendations_screen.dart';

/// Giriş yapılmış uygulamanın kabuğu: 4 sekme + alt tab çubuğu + tek şarkılık mini oynatıcı, ortak [AppState].
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

class _AppShellState extends State<AppShell> with WidgetsBindingObserver {
  late final AppState _state = AppState(widget.api);
  int _tab = 1; // açılışta Oylama; Keşfet solda (0)
  final _visited = <int>{
    1,
  }; // sekmeler ilk açıldıklarında kurulur (açılışta yalnızca Oylama)

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
    _visited.add(i);
  });

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final content = Column(
      children: [
        Expanded(
          child: Stack(
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
                    ),
                    RatingScreen(
                      api: widget.api,
                      state: _state,
                      onLogout: widget.onLogout,
                      onOpenRecommendations: () => _go(2),
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
                    TabPane(
                      active: _tab == i,
                      child: _visited.contains(i) ? w : const SizedBox.shrink(),
                    ),
                ],
              ),
              const Positioned(
                top: 8,
                left: 24,
                right: 24,
                child: _WakingHint(),
              ),
            ],
          ),
        ),
        // Çalan önizleme tab çubuğunun hemen üstünde; Oyla'da kendi oynatıcısı olduğundan gizlenir.
        PreviewMiniPlayer(
          state: _state,
          hideForPrefix: _tab == 1 ? 'vote-' : null,
        ),
        ListenableBuilder(
          listenable: _state,
          builder: (_, _) => TiniTabBar(
            index: _tab,
            onSelect: _go,
            pendingVotes: _state.pendingVotes,
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
                    child: _DebugBar(
                      state: _state,
                      onThemeChanged: widget.onThemeChanged,
                    ),
                  ),
                  Expanded(
                    child: MediaQuery.removePadding(
                      context: context,
                      removeTop: true,
                      child: content,
                    ),
                  ),
                ],
              )
            : content,
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
                for (final e in _names.entries)
                  PopupMenuItem(value: e.key, child: Text(e.value)),
              ],
            ),
            IconButton(
              tooltip: 'Bileşen galerisi',
              iconSize: 20,
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const ComponentGalleryScreen(),
                ),
              ),
              icon: const Icon(Icons.grid_view_rounded),
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
                  : () => onThemeChanged!(
                      dark ? ThemeMode.light : ThemeMode.dark,
                    ),
              icon: Icon(
                dark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Sunucu soğuk başlangıçtayken (istek uzun sürerse) üstte kısa bir bilgi şeridi.
class _WakingHint extends StatelessWidget {
  const _WakingHint();

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    return SafeArea(
      bottom: false,
      child: ValueListenableBuilder<int>(
        valueListenable: slowRequests,
        builder: (_, n, _) => IgnorePointer(
          child: AnimatedOpacity(
            opacity: n > 0 ? 1 : 0,
            duration: const Duration(milliseconds: 200),
            child: Semantics(
              liveRegion: true,
              label: n > 0 ? 'Sunucu uyanıyor, birkaç saniye daha' : null,
              excludeSemantics: true,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: c.card,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: c.primary.withValues(alpha: 0.4)),
                ),
                child: Text(
                  'Sunucu uyanıyor, birkaç saniye daha…',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
