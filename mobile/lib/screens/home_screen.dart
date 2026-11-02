import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import 'feedback_screen.dart';
import 'fresh_screen.dart';
import 'list_screen.dart' show reasonText;
import '../widgets/cover_art.dart';

Future<bool> _launchExternal(String url) =>
    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.api,
    required this.onLogout,
    this.themeMode = ThemeMode.system,
    this.onThemeChanged,
    this.launch = _launchExternal,
  });

  /// Testte değiştirilebilir; varsayılan servis uygulamasını açar.
  final Future<bool> Function(String url) launch;
  final Api api;
  final VoidCallback onLogout;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode>? onThemeChanged;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  List<Connection>? _connections;
  String? _message;
  bool _busy = false;
  DailySong? _daily;

  bool get _spotifyConnected => _connections?.any((c) => c.service == 'spotify') ?? false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();
    _loadDaily();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // Tarayıcıdan dönünce bağlantı durumunu yeniler.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refresh();
  }

  Future<void> _guard(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await action();
    } on ApiException catch (e) {
      if (e.status == 401) return widget.onLogout();
      if (mounted) setState(() => _message = e.message);
    } catch (_) {
      if (mounted) setState(() => _message = 'Sunucuya ulaşılamadı');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _refresh() => _guard(() async {
        final c = await widget.api.connections();
        if (mounted) setState(() => _connections = c);
      });

  Future<void> _connectSpotify() => _guard(() async {
        final url = await widget.api.spotifyAuthorizeUrl();
        await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
      });

  Future<void> _import() => _guard(() async {
        final r = await widget.api.importLibrary();
        if (mounted) setState(() => _message = '${r.imported} şarkı aktarıldı, ${r.skipped} atlandı');
      });

  // Günün şarkısı yardımcı bir özelliktir: hata ya da profil yokluğu ana ekranı bozmaz.
  Future<void> _loadDaily() async {
    try {
      final d = await widget.api.dailySong();
      if (mounted) setState(() => _daily = d);
    } catch (_) {}
  }

  Future<void> _openDaily(DailySong d) async {
    try {
      final url = await widget.api.openUrl(d.listId, d.entry.position);
      await widget.launch(url);
    } catch (_) {
      if (mounted) setState(() => _message = 'Şarkı açılamadı');
    }
  }

  Widget _dailyCard(DailySong d) {
    final title = d.entry.title ?? d.entry.name;
    final artist = d.artists.isNotEmpty ? d.artists.join(', ') : (d.entry.title != null ? d.entry.name : null);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => _openDaily(d),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CoverArt(url: d.image, size: 96),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Günün şarkısı', style: Theme.of(context).textTheme.labelMedium),
                    const SizedBox(height: 4),
                    Text(title,
                        style: Theme.of(context).textTheme.titleMedium,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis),
                    if (artist != null) Text(artist, maxLines: 1, overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 4),
                    Text(reasonText(d.entry, top: 2),
                        style: Theme.of(context).textTheme.bodySmall, maxLines: 3),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _logout() async {
    await widget.api.logout();
    widget.onLogout();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tını'),
        actions: [IconButton(onPressed: _logout, icon: const Icon(Icons.logout), tooltip: 'Çıkış')],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_daily != null) ...[
            _dailyCard(_daily!),
            const SizedBox(height: 8),
          ],
          Card(
            child: ListTile(
              leading: const Icon(Icons.music_note),
              title: const Text('Spotify'),
              subtitle: Text(_spotifyConnected ? 'Bağlı' : 'Bağlı değil'),
              trailing: _spotifyConnected
                  ? FilledButton.tonal(
                      onPressed: _busy ? null : _import,
                      child: const Text('Kütüphaneyi aktar'),
                    )
                  : FilledButton(
                      onPressed: _busy ? null : _connectSpotify,
                      child: const Text('Bağla'),
                    ),
            ),
          ),
          if (_busy) const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
          if (_message != null) Padding(padding: const EdgeInsets.all(12), child: Text(_message!)),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                builder: (_) => FreshScreen(api: widget.api, onLogout: widget.onLogout))),
            icon: const Icon(Icons.new_releases),
            label: const Text('Yeni çıkanlar'),
          ),
          const SizedBox(height: 16),
          SegmentedButton<ThemeMode>(
            segments: const [
              ButtonSegment(value: ThemeMode.system, icon: Icon(Icons.brightness_auto), label: Text('Sistem')),
              ButtonSegment(value: ThemeMode.light, icon: Icon(Icons.light_mode), label: Text('Açık')),
              ButtonSegment(value: ThemeMode.dark, icon: Icon(Icons.dark_mode), label: Text('Koyu')),
            ],
            selected: {widget.themeMode},
            onSelectionChanged: (s) => widget.onThemeChanged?.call(s.first),
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                builder: (_) => FeedbackScreen(api: widget.api, onLogout: widget.onLogout))),
            child: const Text('Geri bildirim gönder'),
          ),
        ],
      ),
    );
  }
}
