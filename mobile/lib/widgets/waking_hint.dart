import 'package:flutter/material.dart';

import '../api.dart';
import '../theme/cosmic_colors.dart';

/// Sunucu soğuk başlangıçtayken (istek uzun sürerse) üstte kısa bir bilgi şeridi.
class WakingHint extends StatelessWidget {
  const WakingHint({super.key});

  @override
  Widget build(BuildContext context) {
    final c = TiniCosmicColors.of(context);
    return SafeArea(
      bottom: false,
      child: ValueListenableBuilder<int>(
        valueListenable: slowRequests,
        builder: (_, n, _) => IgnorePointer(
          child: AnimatedOpacity(
            opacity: n > 0 ? 1 : 0,
            duration: const Duration(milliseconds: 200),
            child: Semantics(
              liveRegion: true,
              label: n > 0 ? 'Sunucu uyanıyor, birkaç saniye daha' : null,
              excludeSemantics: true,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: c.card,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: c.primary.withValues(alpha: 0.4)),
                ),
                child: Text(
                  'Sunucu uyanıyor, birkaç saniye daha…',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
