import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../theme/cosmic_colors.dart';
import 'rating_screen.dart' show openInSpotify;

String _msg(Object e) => e is ApiException ? e.message : 'Bağlantı hatası, tekrar dene';

class _Thumb extends StatelessWidget {
  const _Thumb(this.url);
  final String? url;

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    final fallback = Container(
        width: 48, height: 48, color: c.card, child: const Icon(Icons.music_note_rounded));
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: url == null
          ? fallback
          : Image.network(url!,
              width: 48, height: 48, fit: BoxFit.cover, errorBuilder: (_, _, _) => fallback),
    );
  }
}

String _title(TrackCard t) => t.title ?? 'Parça ${t.track}';

/// Servis aramasından şarkı bulur; sonuca dokununca yorum sayfası açılır.
class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key, required this.api});
  final Api api;

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _ctl = TextEditingController();
  Timer? _debounce;
  List<TrackCard>? _results;
  bool _busy = false;
  String? _error;
  int _gen = 0; // geç gelen eski yanıt yenisini ezmesin

  @override
  void dispose() {
    _debounce?.cancel();
    _ctl.dispose();
    super.dispose();
  }

  void _changed(String v) {
    _debounce?.cancel();
    if (v.trim().length < 2) {
      setState(() {
        _results = null;
        _error = null;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 500), _run);
  }

  Future<void> _run() async {
    final q = _ctl.text.trim();
    if (q.length < 2) return;
    final gen = ++_gen;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await widget.api.searchTracks(q);
      if (mounted && gen == _gen) setState(() => _results = r);
    } catch (e) {
      if (mounted && gen == _gen) setState(() => _error = _msg(e));
    } finally {
      if (mounted && gen == _gen) setState(() => _busy = false);
    }
  }

  Future<void> _later(TrackCard t) async {
    final m = ScaffoldMessenger.of(context);
    try {
      await widget.api.addLater(t.track);
      m.showSnackBar(const SnackBar(content: Text('Sonra dinle listesine eklendi')));
    } catch (e) {
      m.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final r = _results;
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          key: const ValueKey('search-field'),
          controller: _ctl,
          autofocus: true,
          textInputAction: TextInputAction.search,
          decoration: const InputDecoration(hintText: 'Şarkı ya da sanatçı ara', border: InputBorder.none),
          onChanged: _changed,
          onSubmitted: (_) {
            _debounce?.cancel();
            _run();
          },
        ),
        bottom: _busy ? const PreferredSize(
            preferredSize: Size.fromHeight(2), child: LinearProgressIndicator(minHeight: 2)) : null,
      ),
      body: _error != null
          ? Center(child: Text(_error!, style: TextStyle(color: theme.colorScheme.error)))
          : r == null
              ? const Center(child: Text('Dinlediğin ya da merak ettiğin şarkıyı ara'))
              : r.isEmpty
                  ? const Center(child: Text('Sonuç yok'))
                  : ListView.builder(
                      itemCount: r.length,
                      itemBuilder: (_, i) {
                        final t = r[i];
                        return ListTile(
                          leading: _Thumb(t.image),
                          title: Text(_title(t), maxLines: 1, overflow: TextOverflow.ellipsis),
                          subtitle:
                              Text(t.artistLine, maxLines: 1, overflow: TextOverflow.ellipsis),
                          trailing: IconButton(
                            icon: const Icon(Icons.bookmark_add_outlined),
                            tooltip: 'Sonra dinle',
                            onPressed: () => _later(t),
                          ),
                          onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
                              builder: (_) => TrackScreen(api: widget.api, card: t))),
                        );
                      },
                    ),
    );
  }
}

/// "Sonra dinle" listesi: yorum sayfasına geç, Spotify'da aç, listeden çıkar, Spotify'a aktar.
class LaterScreen extends StatefulWidget {
  const LaterScreen({super.key, required this.api});
  final Api api;

  @override
  State<LaterScreen> createState() => _LaterScreenState();
}

class _LaterScreenState extends State<LaterScreen> {
  List<TrackCard>? _items;
  String? _error;
  bool _exporting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = await widget.api.laterList();
      if (mounted) setState(() => _items = r);
    } catch (e) {
      if (mounted) setState(() => _error = _msg(e));
    }
  }

  Future<void> _remove(TrackCard t) async {
    final m = ScaffoldMessenger.of(context);
    try {
      await widget.api.removeLater(t.track);
      if (mounted) setState(() => _items = _items!.where((e) => e.track != t.track).toList());
    } catch (e) {
      m.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
  }

  Future<void> _export() async {
    final m = ScaffoldMessenger.of(context);
    setState(() => _exporting = true);
    try {
      final r = await widget.api.exportLater();
      m.showSnackBar(SnackBar(
          content: Text(r.added == 0
              ? 'Spotify’da bulunan şarkı yok'
              : '${r.added} şarkı Spotify çalma listesine yazıldı'
                  '${r.skipped > 0 ? ' (${r.skipped} atlandı)' : ''}')));
    } catch (e) {
      m.showSnackBar(SnackBar(content: Text(_msg(e))));
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sonra dinle'),
        actions: [
          TextButton.icon(
            onPressed: _exporting || items == null || items.isEmpty ? null : _export,
            icon: const Icon(Icons.playlist_add_rounded),
            label: const Text('Spotify’a aktar'),
          ),
        ],
      ),
      body: _error != null
          ? Center(child: Text(_error!))
          : items == null
              ? const Center(child: CircularProgressIndicator())
              : items.isEmpty
                  ? const Center(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text('Liste boş. Oylama ekranında bir kartı sağa kaydırınca '
                            'buraya eklenir.', textAlign: TextAlign.center),
                      ),
                    )
                  : ListView.builder(
                      itemCount: items.length,
                      itemBuilder: (_, i) {
                        final t = items[i];
                        return ListTile(
                          leading: _Thumb(t.image),
                          title: Text(_title(t), maxLines: 1, overflow: TextOverflow.ellipsis),
                          subtitle:
                              Text(t.artistLine, maxLines: 1, overflow: TextOverflow.ellipsis),
                          trailing: PopupMenuButton<String>(
                            onSelected: (v) => v == 'open'
                                ? openInSpotify(_title(t), t.artistLine)
                                : _remove(t),
                            itemBuilder: (_) => const [
                              PopupMenuItem(value: 'open', child: Text('Spotify’da aç')),
                              PopupMenuItem(value: 'remove', child: Text('Listeden çıkar')),
                            ],
                          ),
                          onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
                              builder: (_) => TrackScreen(api: widget.api, card: t))),
                        );
                      },
                    ),
    );
  }
}

/// Parça sayfası: kısa künye + herkese açık yorumlar (test kullanıcıları arasında).
class TrackScreen extends StatefulWidget {
  const TrackScreen({super.key, required this.api, required this.card});
  final Api api;
  final TrackCard card;

  @override
  State<TrackScreen> createState() => _TrackScreenState();
}

class _TrackScreenState extends State<TrackScreen> {
  final _ctl = TextEditingController();
  late TrackCard _card = widget.card;
  List<TrackComment>? _items;
  String? _error;
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final r = await widget.api.comments(_card.track);
      if (mounted) {
        setState(() {
          _items = r.items;
          if (r.track.title != null) _card = r.track;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = _msg(e));
    }
  }

  Future<void> _send() async {
    final text = _ctl.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() => _sending = true);
    final m = ScaffoldMessenger.of(context);
    try {
      await widget.api.addComment(_card.track, text);
      _ctl.clear();
      await _load();
    } catch (e) {
      m.showSnackBar(SnackBar(content: Text(_msg(e))));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _edit(TrackComment c) async {
    final ctl = TextEditingController(text: c.body);
    final text = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Yorumu düzenle'),
        content: TextField(controller: ctl, maxLines: 4, maxLength: 1000, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Vazgeç')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, ctl.text.trim()), child: const Text('Kaydet')),
        ],
      ),
    );
    ctl.dispose();
    if (text == null || text.isEmpty || text == c.body) return;
    try {
      await widget.api.editComment(c.id, text);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_msg(e))));
    }
  }

  Future<void> _delete(TrackComment c) async {
    try {
      await widget.api.deleteComment(c.id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_msg(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final items = _items;
    return Scaffold(
      appBar: AppBar(title: const Text('Şarkı')),
      body: Column(
        children: [
          ListTile(
            leading: _Thumb(_card.image),
            title: Text(_title(_card), maxLines: 2, overflow: TextOverflow.ellipsis),
            subtitle: Text(_card.artistLine, maxLines: 1, overflow: TextOverflow.ellipsis),
            trailing: TextButton.icon(
              key: const ValueKey('track-open-spotify'),
              onPressed: () => openInSpotify(_title(_card), _card.artistLine),
              icon: const Icon(Icons.open_in_new_rounded, size: 18),
              label: const Text('Spotify’da aç'),
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: _error != null
                ? Center(child: Text(_error!, style: TextStyle(color: theme.colorScheme.error)))
                : items == null
                    ? const Center(child: CircularProgressIndicator())
                    : items.isEmpty
                        ? const Center(child: Text('Henüz yorum yok. İlk yorumu sen yaz.'))
                        : ListView.separated(
                            itemCount: items.length,
                            separatorBuilder: (_, _) => const Divider(height: 1),
                            itemBuilder: (_, i) {
                              final c = items[i];
                              final d = c.createdAt.toLocal();
                              return ListTile(
                                title: Text(c.body),
                                subtitle: Text(
                                    '${c.mine ? 'Sen' : c.author} · '
                                    '${d.day.toString().padLeft(2, '0')}.'
                                    '${d.month.toString().padLeft(2, '0')}.${d.year}'
                                    '${c.edited ? ' · düzenlendi' : ''}'),
                                trailing: c.mine
                                    ? PopupMenuButton<String>(
                                        onSelected: (v) => v == 'edit' ? _edit(c) : _delete(c),
                                        itemBuilder: (_) => const [
                                          PopupMenuItem(value: 'edit', child: Text('Düzenle')),
                                          PopupMenuItem(value: 'delete', child: Text('Sil')),
                                        ],
                                      )
                                    : null,
                              );
                            },
                          ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 6, 4, 8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      key: const ValueKey('comment-field'),
                      controller: _ctl,
                      minLines: 1,
                      maxLines: 4,
                      maxLength: 1000,
                      decoration: const InputDecoration(
                          hintText: 'Bu şarkı hakkında ne düşünüyorsun?', counterText: ''),
                    ),
                  ),
                  IconButton(
                    key: const ValueKey('comment-send'),
                    onPressed: _sending ? null : _send,
                    icon: const Icon(Icons.send_rounded),
                    tooltip: 'Gönder',
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
