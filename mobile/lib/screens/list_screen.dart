import 'package:flutter/material.dart';

import '../api.dart';

/// Gerekçe cümlesi: en büyük paylı çapalar, yüzdeyle (hesabın kendisinden gelir).
String reasonText(ListEntry e, {int top = 3}) {
  final sorted = [...e.reasons]..sort((a, b) => b.share.compareTo(a.share));
  final parts = sorted
      .take(top)
      .map((r) => '${r.isAnchor ? '★ ' : ''}${r.seedName} %${(r.share * 100).round()}');
  return 'Sevdiğin sanatçılara benzediği için: ${parts.join(', ')}';
}

class ListScreen extends StatefulWidget {
  const ListScreen({super.key, required this.api, this.onLogout});
  final Api api;
  final VoidCallback? onLogout;

  @override
  State<ListScreen> createState() => _ListScreenState();
}

class _ListScreenState extends State<ListScreen> {
  DiscoveryList? _list;
  bool _busy = false;
  String? _error;

  Future<void> _generate() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final l = await widget.api.generateList();
      if (mounted) setState(() => _list = l);
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted) Navigator.of(context).pop();
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
    return Scaffold(
      appBar: AppBar(title: const Text('Keşif listesi')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          FilledButton(
            onPressed: _busy ? null : _generate,
            child: Text(list == null ? 'Liste üret' : 'Yeniden üret'),
          ),
          if (_busy) const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (list != null && list.items.isEmpty)
            const Padding(padding: EdgeInsets.all(12), child: Text('Öneri çıkmadı.')),
          if (list != null)
            for (final e in list.items)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        Expanded(
                            child: Text('${e.position}. ${e.name}',
                                style: Theme.of(context).textTheme.titleMedium)),
                        Chip(label: Text(e.slot)),
                      ]),
                      if (e.title != null) Text(e.title!),
                      const SizedBox(height: 4),
                      Text(reasonText(e)),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                          onPressed: () => _object(e),
                          child: const Text('Bu gerekçe yanlış'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
        ],
      ),
    );
  }
}
