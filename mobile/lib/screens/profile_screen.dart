import 'package:flutter/material.dart';

import '../api.dart';
import '../app_state.dart';
import '../theme/cosmic_colors.dart';
import 'history_screen.dart';
import 'home_screen.dart';

/// Profil sekmesi: seviye özeti, canlı oy dağılımı ve son oylananlar (hepsi [AppState]'ten).
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({
    super.key,
    required this.api,
    required this.state,
    required this.onLogout,
    this.themeMode = ThemeMode.system,
    this.onThemeChanged,
  });
  final Api api;
  final AppState state;
  final VoidCallback onLogout;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode>? onThemeChanged;

  /// Üstte açık sayfa varken çıkış yapılırsa yığın temizlenir (giriş ekranı üstte kalmasın).
  void _logout(BuildContext context) {
    Navigator.of(context).popUntil((r) => r.isFirst);
    onLogout();
  }

  Future<void> _change(BuildContext context, HistoryItem h) async {
    final c = TiniCosmicColors.of(context);
    final picked = await showModalBottomSheet<int>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(title: Text(h.title ?? 'Parça ${h.track}')),
            for (var v = 1; v <= 6; v++)
              ListTile(
                leading: Icon(c.votes[v]!.icon, color: c.votes[v]!.fg),
                title: Text('$v · ${c.votes[v]!.label}'),
                selected: v == h.vote,
                onTap: () => Navigator.pop(ctx, v),
              ),
          ],
        ),
      ),
    );
    if (picked == null || picked == h.vote) return;
    try {
      await api.castVote(h.track, picked); // yeni bir olay; eskisi silinmez
      state.recordChange(h, picked);
    } on ApiException catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Sunucuya ulaşılamadı')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final theme = Theme.of(context);
    const tab = [FontFeature.tabularFigures()];
    return Scaffold(
      backgroundColor: c.scaffold,
      body: SafeArea(
        bottom: false,
        child: ListenableBuilder(
          listenable: state,
          builder: (context, _) {
            final counts = state.counts;
            final max = counts.values.fold<int>(1, (m, v) => v > m ? v : m);
            final avg = state.average;
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 80 + 24),
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: _box(context, c.card),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Seviye ${state.level}',
                          style: theme.textTheme.headlineSmall?.copyWith(color: c.primary)),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          _Stat('${state.total}', 'Oylanan', tab),
                          _Stat('${state.unheardSession}', 'Dinlemedim\n(bu oturum)', tab),
                          _Stat(avg == null ? '–' : avg.toStringAsFixed(1), 'Ortalama', tab),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Text('Oy dağılımı', style: theme.textTheme.titleMedium),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: _box(context, c.card),
                  child: Column(
                    children: [
                      for (var v = 1; v <= 6; v++)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 5),
                          child: Row(
                            children: [
                              SizedBox(
                                width: 84,
                                child: Row(children: [
                                  Icon(c.votes[v]!.icon, size: 16, color: c.votes[v]!.fg),
                                  const SizedBox(width: 6),
                                  Flexible(
                                      child: Text('$v · ${c.votes[v]!.label}',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: theme.textTheme.labelMedium)),
                                ]),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: TweenAnimationBuilder<double>(
                                  tween: Tween(end: counts[v]! / max),
                                  duration: const Duration(milliseconds: 300),
                                  curve: Curves.easeOutCubic,
                                  builder: (_, t, _) => LinearProgressIndicator(
                                    value: t,
                                    minHeight: 10,
                                    borderRadius: BorderRadius.circular(5),
                                    color: c.votes[v]!.border,
                                    backgroundColor: c.votes[v]!.fill,
                                  ),
                                ),
                              ),
                              SizedBox(
                                width: 36,
                                child: Text('${counts[v]}',
                                    textAlign: TextAlign.right,
                                    key: ValueKey('count-$v'),
                                    style: theme.textTheme.labelMedium
                                        ?.copyWith(fontFeatures: tab)),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Text('Son oylananlar', style: theme.textTheme.titleMedium),
                const SizedBox(height: 8),
                if (state.recent.isEmpty)
                  const Padding(padding: EdgeInsets.all(12), child: Text('Henüz oy yok.')),
                for (final h in state.recent)
                  Container(
                    margin: const EdgeInsets.only(bottom: 6),
                    decoration: _box(context, c.card),
                    child: ListTile(
                      title: Text(h.title ?? 'Parça ${h.track}', maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text(h.artists.join(', '), maxLines: 1, overflow: TextOverflow.ellipsis),
                      trailing: _VoteBadge(style: c.votes[h.vote]!, vote: h.vote),
                      onTap: () => _change(context, h),
                    ),
                  ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                      builder: (_) => HistoryScreen(api: api, onLogout: onLogout))),
                  icon: const Icon(Icons.history_rounded),
                  label: const Text('Tüm oy geçmişi'),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                      builder: (_) => HomeScreen(
                            api: api,
                            onLogout: () => _logout(context),
                            themeMode: themeMode,
                            onThemeChanged: onThemeChanged,
                          ))),
                  icon: const Icon(Icons.settings_rounded),
                  label: const Text('Bağlantılar ve ayarlar'),
                ),
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: () async {
                    await api.logout();
                    if (context.mounted) _logout(context);
                  },
                  icon: const Icon(Icons.logout_rounded),
                  label: const Text('Çıkış'),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  BoxDecoration _box(BuildContext context, Color color) => BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      );
}

class _Stat extends StatelessWidget {
  const _Stat(this.value, this.label, this.features);
  final String value;
  final String label;
  final List<FontFeature> features;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Expanded(
      child: Column(
        children: [
          Text(value, style: theme.textTheme.headlineSmall?.copyWith(fontFeatures: features)),
          Text(label, textAlign: TextAlign.center, style: theme.textTheme.labelSmall),
        ],
      ),
    );
  }
}

class _VoteBadge extends StatelessWidget {
  const _VoteBadge({required this.style, required this.vote});
  final VoteStyle style;
  final int vote;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: style.fill,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: style.border, width: style.borderWidth),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(style.icon, size: 16, color: style.fg),
          const SizedBox(width: 4),
          Text('$vote', style: TextStyle(color: style.fg, fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}
