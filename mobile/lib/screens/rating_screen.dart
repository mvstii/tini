import 'package:flutter/material.dart';

import '../api.dart';

/// Başlangıç turu: ilk bu kadar oydan sonra profil kurulabilir.
const tourVotes = 30;

/// Sağa kaydırma "Great" oyudur; sola kaydırma "Unheard" olayı yazar (oy değildir).
const swipeRightVote = 5;

const voteLabels = <int, String>{
  1: 'Awful',
  2: 'Bad',
  3: 'Meh',
  4: 'Good',
  5: 'Great',
  6: 'Amazing',
};

class RatingScreen extends StatefulWidget {
  const RatingScreen({super.key, required this.api, this.onLogout});
  final Api api;
  final VoidCallback? onLogout;

  @override
  State<RatingScreen> createState() => _RatingScreenState();
}

/// Geri alınabilir tek adım. Oy olayı silinmez; geri alınan kart yeniden gösterilir ve
/// verilecek yeni oy, yeni bir olay olarak öncekinin yerini alır.
class _Step {
  _Step(this.item, this.vote);
  final QueueItem item;
  final int? vote; // null: Unheard
}

class _RatingScreenState extends State<RatingScreen> {
  final List<QueueItem> _cards = [];
  final Set<int> _skipped = {};
  final List<_Step> _history = [];
  int _seed = 0;
  int _total = 0;
  int _stale = 0;
  bool _loading = true;
  bool _busy = false;
  bool _profileBuilt = false;
  String? _error;

  QueueItem? get _current => _cards.isEmpty ? null : _cards.first;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _guard(Future<void> Function() action) async {
    try {
      await action();
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

  Future<void> _init() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    await _guard(() async {
      _total = await widget.api.voteTotal();
      await _fill();
    });
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _fill() async {
    final q = await widget.api.voteQueue(seed: _seed);
    _stale = q.stale;
    final seen = _cards.map((c) => c.track).toSet();
    final fresh = q.items.where((i) => !_skipped.contains(i.track) && !seen.contains(i.track));
    if (mounted) setState(() => _cards.addAll(fresh));
  }

  Future<void> _refreshLibrary() async {
    setState(() => _loading = true);
    await _guard(() async {
      await widget.api.importLibrary();
      await _fill();
    });
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _answer(int? vote) async {
    final item = _current;
    if (item == null || _busy) return;
    // Dismissible kartı ağaçtan hemen çıkarmayı bekler; sunucu yanıtı beklenirse debug'da
    // "dismissed Dismissible is still part of the tree" hatası (kırmızı ekran) çıkar.
    setState(() {
      _busy = true;
      _error = null;
      _cards.removeAt(0);
    });
    var saved = false;
    await _guard(() async {
      if (vote != null) {
        await widget.api.castVote(item.track, vote);
        _total++;
      } else {
        await widget.api.markUnheard(item.track);
        _skipped.add(item.track);
      }
      saved = true;
      _history.add(_Step(item, vote));
      if (_cards.length < 3) {
        _seed++;
        await _fill();
      }
    });
    if (mounted) {
      setState(() {
        if (!saved) _cards.insert(0, item); // kayıt başarısızsa kart geri gelir
        _busy = false;
      });
    }
  }

  void _undo() {
    if (_history.isEmpty || _busy) return;
    final step = _history.removeLast();
    setState(() {
      _skipped.remove(step.item.track);
      _cards.insert(0, step.item);
    });
  }

  Future<void> _buildProfile() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    await _guard(() async {
      await widget.api.rebuildProfile();
      if (mounted) setState(() => _profileBuilt = true);
    });
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final progress = (_total / tourVotes).clamp(0.0, 1.0);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Oylama'),
        actions: [
          IconButton(
            onPressed: _history.isEmpty || _busy ? null : _undo,
            icon: const Icon(Icons.undo),
            tooltip: 'Geri al',
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Text(_total >= tourVotes
                ? '$_total oy · tur tamam'
                : 'Başlangıç turu: $_total / $tourVotes oy'),
            const SizedBox(height: 8),
            LinearProgressIndicator(value: progress),
            if (_total >= tourVotes) ...[
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _busy ? null : _buildProfile,
                child: Text(_profileBuilt ? 'Profil güncellendi' : 'Profili kur'),
              ),
            ],
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            Expanded(child: _body()),
          ],
        ),
      ),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    final item = _current;
    if (item == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_stale > 0
                ? '$_stale şarkının bilgisi eskidi. Kütüphaneyi yenile.'
                : 'Oylanacak şarkı yok.'),
            const SizedBox(height: 12),
            if (_stale > 0)
              FilledButton(onPressed: _refreshLibrary, child: const Text('Kütüphaneyi yenile'))
            else
              OutlinedButton(onPressed: _init, child: const Text('Yeniden dene')),
          ],
        ),
      );
    }
    return Column(
      children: [
        Expanded(
          child: Dismissible(
            key: ValueKey(item.track),
            direction: _busy ? DismissDirection.none : DismissDirection.horizontal,
            onDismissed: (d) => _answer(d == DismissDirection.startToEnd ? swipeRightVote : null),
            background: _hint(Icons.thumb_up, 'Great', Alignment.centerLeft),
            secondaryBackground: _hint(Icons.skip_next, 'Unheard', Alignment.centerRight),
            child: Card(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.album, size: 96),
                      const SizedBox(height: 16),
                      Text(item.title,
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.headlineSmall),
                      const SizedBox(height: 8),
                      Text(item.artistLine, textAlign: TextAlign.center),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final e in voteLabels.entries)
              FilledButton.tonal(
                onPressed: _busy ? null : () => _answer(e.key),
                child: Text('${e.key} · ${e.value}'),
              ),
            OutlinedButton(
              onPressed: _busy ? null : () => _answer(null),
              child: const Text('Unheard'),
            ),
          ],
        ),
      ],
    );
  }

  Widget _hint(IconData icon, String text, Alignment align) => Container(
        alignment: align,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [Icon(icon), Text(text)]),
      );
}
