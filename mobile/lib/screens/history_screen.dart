import 'package:flutter/material.dart';

import '../api.dart';
import 'rating_screen.dart' show voteLabels;

/// Oy geçmişi: parça başına güncel oy. Oy değiştirmek yeni bir olay yazar (eski olay silinmez).
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key, required this.api, this.onLogout});
  final Api api;
  final VoidCallback? onLogout;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<HistoryItem>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await widget.api.voteHistory();
      if (mounted) setState(() => _items = items);
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted) Navigator.of(context).pop();
        return widget.onLogout?.call();
      }
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    }
  }

  Future<void> _change(HistoryItem item) async {
    final picked = await showModalBottomSheet<int>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => SafeArea(
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(title: Text(item.title ?? 'Parça ${item.track}')),
              for (final v in voteLabels.entries)
                ListTile(
                  title: Text('${v.key} · ${v.value}'),
                  selected: v.key == item.vote,
                  onTap: () => Navigator.pop(ctx, v.key),
                ),
            ],
          ),
        ),
      ),
    );
    if (picked == null || picked == item.vote) return;
    try {
      await widget.api.castVote(item.track, picked);
      if (mounted) await _load();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Sunucuya ulaşılamadı');
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return Scaffold(
      appBar: AppBar(title: const Text('Oy geçmişi')),
      body: items == null && _error == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(_error!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ),
                if (items != null && items.isEmpty)
                  const Padding(padding: EdgeInsets.all(16), child: Text('Henüz oy yok.')),
                for (final i in items ?? <HistoryItem>[])
                  ListTile(
                    title: Text(i.title ?? 'Parça ${i.track}'),
                    subtitle: Text(i.artists.join(', ')),
                    trailing: Chip(label: Text('${i.vote} · ${voteLabels[i.vote]}')),
                    onTap: () => _change(i),
                  ),
              ],
            ),
    );
  }
}
