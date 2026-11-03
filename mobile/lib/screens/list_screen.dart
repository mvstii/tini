import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show PlatformException;
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../theme/cosmic_colors.dart';
import '../widgets/artist_avatar.dart';
import '../widgets/preview_button.dart';
import '../widgets/studio.dart';

/// Gerekçe cümlesi: en büyük paylı çapalar, yüzdeyle (hesabın kendisinden gelir).
String reasonText(ListEntry e, {int top = 3}) {
  final sorted = [...e.reasons]..sort((a, b) => b.share.compareTo(a.share));
  final parts = sorted
      .take(top)
      .map((r) => '${r.isAnchor ? '★ ' : ''}${r.seedName} %${(r.share * 100).round()}');
  return 'Sevdiğin sanatçılara benzediği için: ${parts.join(', ')}';
}

Future<bool> _launchExternal(String url) =>
    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

class ListScreen extends StatefulWidget {
  const ListScreen({
    super.key,
    required this.api,
    this.onLogout,
    this.launch = _launchExternal,
    this.embedded = false,
  });
  final Api api;
  final VoidCallback? onLogout;

  /// Kabuk içinde sekme olarak: üst çubuk yok, alt menü için boşluk var.
  final bool embedded;

  /// Testte değiştirilebilir; varsayılan servis uygulamasını açar.
  final Future<bool> Function(String url) launch;

  @override
  State<ListScreen> createState() => _ListScreenState();
}

class _ListScreenState extends State<ListScreen> {
  DiscoveryList? _list;
  bool _busy = false;
  bool _exporting = false;
  String? _error;
  final Map<int, String?> _photos = {};

  /// Önbellekte olmayan sanatçı portrelerini arka planda ister; kartlar geldikçe güncellenir.
  void _loadPhotos(DiscoveryList l) {
    final missing = [
      for (final e in l.items)
        if (e.artistId != null && e.artistImage == null) e.artistId!,
    ];
    loadArtistPhotos(widget.api, missing, (found) {
      if (mounted) setState(() => _photos.addAll(found));
    }, alive: () => mounted);
  }

  Future<void> _generate() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final l = await widget.api.generateList();
      if (mounted) setState(() => _list = l);
      _loadPhotos(l);
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted && Navigator.of(context).canPop()) Navigator.of(context).pop();
        return widget.onLogout?.call();
      }
      if (mounted) {
        setState(() => _error = e.status == 404 ? 'Önce oylayıp profilini kur.' : e.message);
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _export() async {
    setState(() {
      _exporting = true;
      _busy = true;
      _error = null;
    });
    try {
      final r = await widget.api.exportList(_list!.id);
      if (!mounted) return;
      final named = r.skippedNames.where((n) => n.isNotEmpty).toList();
      final detail = named.isEmpty ? '' : ' (${named.join(', ')})';
      final msg = r.added == 0
          ? 'Bu listedeki öğelerin çalınabilir parçası bulunamadı.$detail'
          : "Spotify'a kaydedildi: ${r.added} parça"
              "${r.skipped > 0 ? ', ${r.skipped} öğe atlandı$detail' : ''}";
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    } on ApiException catch (ex) {
      if (mounted) {
        setState(() => _error = ex.status == 409
            ? "Spotify'ı (yeniden) bağla; çalma listesi izni gerekebilir."
            : ex.message);
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
          _exporting = false;
        });
      }
    }
  }

  Future<void> _open(ListEntry e) async {
    try {
      final url = await widget.api.openUrl(_list!.id, e.position);
      var opened = false;
      try {
        opened = await widget.launch(url);
      } on PlatformException {
        // Uygulama kurulu değilse launchUrl istisna fırlatabilir.
      }
      if (!opened && mounted) {
        setState(() => _error = 'Spotify açılamadı. Uygulama kurulu mu?');
      }
    } on ApiException catch (ex) {
      if (mounted) {
        setState(() => _error = ex.status == 409 ? "Önce Spotify'ı bağla." : ex.message);
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    }
  }

  Future<void> _object(ListEntry e) async {
    final list = _list!;
    // -1: tüm gerekçe; aksi halde itiraz edilen çapanın kimliği
    final picked = await showModalBottomSheet<int>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const ListTile(title: Text('Hangi gerekçe yanlış?')),
            ListTile(title: const Text('Tümü'), onTap: () => Navigator.pop(ctx, -1)),
            for (final r in e.reasons)
              ListTile(title: Text(r.seedName), onTap: () => Navigator.pop(ctx, r.seedId)),
          ],
        ),
      ),
    );
    if (picked == null) return;
    try {
      await widget.api.reasonFeedback(list.id, e.position, seedId: picked == -1 ? null : picked);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Geri bildirimin kaydedildi')));
      }
    } on ApiException catch (ex) {
      if (mounted) setState(() => _error = ex.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    }
  }

  @override
  Widget build(BuildContext context) {
    final list = _list;
    final c = TiniCosmicColors.of(context);
    final theme = Theme.of(context);
    return Scaffold(
      backgroundColor: widget.embedded ? Colors.transparent : c.scaffold,
      appBar: widget.embedded ? null : AppBar(title: const Text('Keşif listesi')),
      body: ListView(
        padding: EdgeInsets.fromLTRB(16, widget.embedded ? 24 : 16, 16, widget.embedded ? 96 : 16),
        children: [
          if (widget.embedded)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text('Sana Özel Tını Eşleşmeleri', style: theme.textTheme.headlineSmall),
            ),
          StudioButton(
            icon: list == null ? Icons.auto_awesome_rounded : Icons.refresh_rounded,
            label: list == null ? 'Liste üret' : 'Yeniden üret',
            busy: _busy && !_exporting,
            onPressed: _busy ? null : _generate,
          ),
          if (list != null && list.items.isNotEmpty) ...[
            const SizedBox(height: 10),
            StudioButton(
              primary: false,
              icon: Icons.playlist_add_rounded,
              label: "Spotify'a kaydet",
              busy: _exporting,
              onPressed: _busy ? null : _export,
            ),
          ],
          const SizedBox(height: 14),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: StudioSurface(
                padding: const EdgeInsets.all(12),
                child: Row(children: [
                  Icon(Icons.error_outline_rounded, color: theme.colorScheme.error),
                  const SizedBox(width: 10),
                  Expanded(child: Text(_error!, style: TextStyle(color: theme.colorScheme.error))),
                ]),
              ),
            ),
          if (_busy && !_exporting && list == null)
            for (var i = 0; i < 4; i++)
              const Padding(padding: EdgeInsets.only(bottom: 8), child: SkeletonCard(height: 120)),
          if (list != null && list.items.isEmpty)
            const Padding(padding: EdgeInsets.all(12), child: Text('Öneri çıkmadı.')),
          if (list != null)
            for (final (i, e) in list.items.indexed)
              StaggerIn(
                key: ValueKey('${list.id}-${e.position}'),
                index: i,
                child: Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: StudioSurface(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Gerekçe rozeti: metin hesabın kendisinden (PPR çapa payları) gelir.
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        decoration: BoxDecoration(
                          color: c.primary.withValues(alpha: 0.14),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.insights_rounded, size: 18, color: c.primary),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(reasonText(e),
                                  style: theme.textTheme.bodySmall
                                      ?.copyWith(color: theme.colorScheme.onSurface)),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 10),
                      Row(children: [
                        ArtistAvatar(
                            name: e.name, url: _photos[e.artistId] ?? e.artistImage, size: 64),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${e.position}. ${e.name}',
                                  style: studioTitle(context),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis),
                              if (e.title != null) Text(e.title!),
                              if (e.release != null)
                                Text(
                                    '${e.release!.title} · ${e.release!.type} · ${e.release!.released}'),
                            ],
                          ),
                        ),
                        if (e.artistId != null && e.release == null)
                          PreviewButton(
                              api: widget.api,
                              previewKey: 'list-${list.id}-${e.position}',
                              artistId: e.artistId),
                        const SizedBox(width: 6),
                        Chip(label: Text(e.slot)),
                      ]),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          TextButton(
                            onPressed: () => _object(e),
                            child: const Text('Bu gerekçe yanlış'),
                          ),
                          const SizedBox(width: 6),
                          SizedBox(
                            width: 150,
                            child: StudioButton(
                              dense: true,
                              icon: Icons.open_in_new_rounded,
                              label: "Spotify'da aç",
                              onPressed: () => _open(e),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                ),
              ),
              ),
        ],
      ),
    );
  }
}
