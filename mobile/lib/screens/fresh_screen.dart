import 'package:flutter/material.dart';

import '../api.dart';
import '../widgets/artist_avatar.dart';
import '../widgets/studio.dart';
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
  final Map<int, String?> _photos = {};

  void _loadPhotos(DiscoveryList l) {
    final missing = [
      for (final e in l.items)
        if (e.artistId != null && e.artistImage == null) e.artistId!,
    ];
    loadArtistPhotos(widget.api, missing, (found) {
      if (mounted) setState(() => _photos.addAll(found));
    }, alive: () => mounted);
  }

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
          StudioButton(
            icon: fresh == null ? Icons.auto_awesome_rounded : Icons.refresh_rounded,
            label: fresh == null ? 'Taze liste üret' : 'Yeniden üret',
            busy: _busy,
            onPressed: _busy
                ? null
                : () => _run(() async {
                      _fresh = await widget.api.generateFresh();
                      _loadPhotos(_fresh!);
                    }),
          ),
          const SizedBox(height: 14),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: StateNote.error(_error!),
            ),
          if (_busy && fresh == null && feed != null)
            for (var i = 0; i < 3; i++)
              const Padding(padding: EdgeInsets.only(bottom: 8), child: SkeletonCard()),
          if (fresh != null)
            for (final (i, e) in fresh.items.indexed)
              StaggerIn(
                key: ValueKey('${fresh.id}-${e.position}'),
                index: i,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: StudioSurface(
                    padding: const EdgeInsets.all(14),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ArtistAvatar(
                            name: e.name, url: _photos[e.artistId] ?? e.artistImage, size: 56),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${e.position}. ${e.release?.title ?? e.name}',
                                  style: studioTitle(context)),
                              const SizedBox(height: 2),
                              Text(
                                  '${e.name} · ${e.release?.type ?? ''} · ${e.release?.released ?? ''}'),
                              const SizedBox(height: 6),
                              Text(reasonText(e), style: Theme.of(context).textTheme.bodySmall),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          const SizedBox(height: 8),
          Text('Takip ettiklerin', style: Theme.of(context).textTheme.titleMedium),
          if (feed != null && feed.isEmpty)
            const StateNote.empty('Henüz yeni yayın yok.', icon: Icons.album_outlined),
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
