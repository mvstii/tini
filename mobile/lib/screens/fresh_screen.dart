import 'package:flutter/material.dart';

import '../api.dart';
import 'list_screen.dart' show reasonText;

/// "Yeni çıkanlar": takip edilen sanatçıların son yayınları ve haftalık Taze liste.
class FreshScreen extends StatefulWidget {
  const FreshScreen({super.key, required this.api, this.onLogout});
  final Api api;
  final VoidCallback? onLogout;

  @override
  State<FreshScreen> createState() => _FreshScreenState();
}

class _FreshScreenState extends State<FreshScreen> {
  List<NewRelease>? _feed;
  DiscoveryList? _fresh;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _run(() async => _feed = await widget.api.newReleases());
  }

  Future<void> _run(Future<void> Function() job) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await job();
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted) Navigator.of(context).pop();
        return widget.onLogout?.call();
      }
      if (mounted) {
        setState(() => _error = switch (e.status) {
              404 => 'Önce oylayıp profilini kur.',
              409 => 'Takip ettiğin sanatçıların yeni yayını yok.',
              _ => e.message,
            });
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final feed = _feed;
    final fresh = _fresh;
    return Scaffold(
      appBar: AppBar(title: const Text('Yeni çıkanlar')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          FilledButton(
            onPressed: _busy
                ? null
                : () => _run(() async => _fresh = await widget.api.generateFresh()),
            child: Text(fresh == null ? 'Taze liste üret' : 'Yeniden üret'),
          ),
          if (_busy) const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (fresh != null)
            for (final e in fresh.items)
              Card(
                child: ListTile(
                  title: Text('${e.position}. ${e.release?.title ?? e.name}'),
                  subtitle: Text(
                      '${e.name} · ${e.release?.type ?? ''} · ${e.release?.released ?? ''}\n'
                      '${reasonText(e)}'),
                  isThreeLine: true,
                ),
              ),
          const SizedBox(height: 8),
          Text('Takip ettiklerin', style: Theme.of(context).textTheme.titleMedium),
          if (feed != null && feed.isEmpty)
            const Padding(padding: EdgeInsets.all(12), child: Text('Henüz yeni yayın yok.')),
          if (feed != null)
            for (final r in feed)
              ListTile(
                title: Text(r.title),
                subtitle: Text('${r.artist} · ${r.type} · ${r.released}'),
              ),
        ],
      ),
    );
  }
}
