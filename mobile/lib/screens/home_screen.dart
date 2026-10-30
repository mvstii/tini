import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import 'rating_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.api, required this.onLogout});
  final Api api;
  final VoidCallback onLogout;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  List<Connection>? _connections;
  String? _message;
  bool _busy = false;

  bool get _spotifyConnected => _connections?.any((c) => c.service == 'spotify') ?? false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();
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
          OutlinedButton(
            onPressed: () => Navigator.of(context)
                .push(MaterialPageRoute<void>(builder: (_) => RatingScreen(api: widget.api, onLogout: widget.onLogout))),
            child: const Text('Oylamaya başla'),
          ),
        ],
      ),
    );
  }
}
