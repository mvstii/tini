import 'package:flutter/material.dart';

import '../../theme/tini_tokens.dart';
import 'components.dart';

/// Yalnızca hata ayıklama: tüm bileşenleri örnek (yer tutucu) verilerle gösterir.
/// Üretimde gösterilmez; shell'deki debug çubuğundan açılır.
class ComponentGalleryScreen extends StatefulWidget {
  const ComponentGalleryScreen({super.key});

  @override
  State<ComponentGalleryScreen> createState() => _ComponentGalleryScreenState();
}

class _ComponentGalleryScreenState extends State<ComponentGalleryScreen> {
  int? _vote = 5;
  int _tab = 1;
  bool _playing = true;
  bool _added = false;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    Widget h(String s) => Padding(
          padding: const EdgeInsets.only(top: TiniTokens.sectionGap, bottom: 10),
          child: Text(s, style: TiniTokens.section.copyWith(color: t.text)),
        );
    return Scaffold(
      appBar: AppBar(title: const Text('Bileşen galerisi (debug)')),
      body: ListView(
        padding: const EdgeInsets.all(TiniTokens.pageMargin),
        children: [
          h('VoteRow'),
          VoteRow(selected: _vote, onVote: (v) => setState(() => _vote = v)),
          h('VoteBadge · PredictionPill'),
          Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            for (var v = 1; v <= 6; v++) VoteBadge(vote: v),
            const PredictionPill(vote: 4),
          ]),
          h('UnheardButton'),
          UnheardButton(onTap: () => setState(() => _added = !_added), added: _added),
          h('ClipPlayer'),
          ClipPlayer(
            seed: 'galeri',
            progress: 0.45,
            playing: _playing,
            onToggle: () => setState(() => _playing = !_playing),
            onOpenExternal: () {},
          ),
          h('TrackRow'),
          const TrackRow(title: 'Örnek şarkı', artist: 'Örnek sanatçı', slot: TrackSlot.fit, reason: 'Örnek gerekçe', fit: 94),
          const TrackRow(title: 'İkinci şarkı', artist: 'Başka sanatçı', slot: TrackSlot.fresh, reason: 'Örnek gerekçe', fit: 88, isNew: true),
          const TrackRow(title: 'Üçüncü şarkı', artist: 'Üçüncü sanatçı', slot: TrackSlot.unheard, reason: 'Örnek gerekçe', fit: 86),
          const TrackRow(title: 'Dördüncü şarkı', artist: 'Dördüncü sanatçı', slot: TrackSlot.explore, reason: 'Örnek gerekçe', fit: 72),
          h('ServiceSaveButton'),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final s in SaveState.values) ServiceSaveButton(service: ServiceKind.apple, state: s, onPressed: () {}),
            for (final s in SaveState.values) ServiceSaveButton(service: ServiceKind.spotify, state: s, onPressed: () {}),
          ]),
          h('AnchorRow · TagChip · SlotBar'),
          const AnchorRow(title: 'Örnek çapa', artist: 'Sanatçı', vote: 6, share: 0.54),
          const SizedBox(height: 10),
          const Wrap(spacing: 8, runSpacing: 8, children: [
            TagChip(label: 'etiket', count: 3),
            TagChip(label: 'başka'),
            TagChip(label: 'kaçınılan', danger: true),
          ]),
          h('ModeBubbleField'),
          const ModeBubbleField(modes: [
            ModeData(name: 'Mod A', share: 0.34, anchors: 9, tags: ['dream pop']),
            ModeData(name: 'Mod B', share: 0.22, anchors: 5, tags: ['psychedelic']),
            ModeData(name: 'Mod C', share: 0.18, tags: ['trip-hop']),
            ModeData(name: 'Mod D', share: 0.11, tags: ['funk']),
            ModeData(name: 'Mod E', share: 0.09),
          ]),
          h('VoteDistributionChart'),
          const VoteDistributionChart(counts: [4, 9, 20, 40, 32, 12]),
          h('MiniPlayer'),
          MiniPlayer(
            title: 'Örnek şarkı',
            artist: 'Örnek sanatçı',
            sourceLabel: 'önizleme',
            vote: 5,
            progress: 0.4,
            playing: _playing,
            onToggle: () => setState(() => _playing = !_playing),
          ),
          h('TiniTabBar'),
          TiniTabBar(index: _tab, pendingVotes: 12, onSelect: (i) => setState(() => _tab = i)),
        ],
      ),
    );
  }
}
