import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../api.dart';
import '../app_state.dart';
import '../theme/cosmic_colors.dart';
import 'list_screen.dart';

/// Öneriler sekmesi: 30 oydan önce kilitli, sonra gerçek keşif listesi ([ListScreen]).
class RecommendationsScreen extends StatelessWidget {
  const RecommendationsScreen({
    super.key,
    required this.api,
    required this.state,
    required this.onContinue,
    this.onLogout,
  });
  final Api api;
  final AppState state;
  final VoidCallback onContinue;
  final VoidCallback? onLogout;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: state,
      builder: (context, _) => state.unlocked
          ? ListScreen(api: api, onLogout: onLogout, embedded: true)
          : _Locked(state: state, onContinue: onContinue),
    );
  }
}

class _Locked extends StatelessWidget {
  const _Locked({required this.state, required this.onContinue});
  final AppState state;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final theme = Theme.of(context);
    final left = tourVotes - state.total;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(32, 24, 32, 96),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 120,
                  height: 120,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox.expand(
                        child: CircularProgressIndicator(
                          value: state.total / tourVotes,
                          strokeWidth: 8,
                          strokeCap: StrokeCap.round,
                          color: c.primary,
                          backgroundColor: c.card,
                        ),
                      ),
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.lock_outline_rounded, color: c.primary),
                          Text('${state.total} / $tourVotes Oy',
                              style: theme.textTheme.titleSmall?.copyWith(
                                  fontFeatures: const [FontFeature.tabularFigures()])),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'Müzik DNA\'nı çıkarmamız için $left şarkı daha oylamalısın',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.titleMedium,
                ),
                const SizedBox(height: 20),
                FilledButton(onPressed: onContinue, child: const Text('Oylamaya Devam Et')),
                if (kDebugMode) ...[
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: state.debugUnlock,
                    child: const Text('Test: Hemen 30 Oya Tamamla'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
