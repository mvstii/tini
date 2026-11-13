import 'package:flutter/material.dart';

import '../strings.dart';
import '../theme/tini_tokens.dart';

/// Kısa açıklama alt sayfası ("?" simgesinden açılır).
Future<void> showTiniInfoSheet(BuildContext context, {required String title, required String body}) {
  final t = TiniTokens.of(context);
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: t.sheet,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(TiniTokens.rSheet)),
    ),
    builder: (ctx) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: TiniTokens.section.copyWith(color: t.text)),
            const SizedBox(height: 10),
            Text(body, style: TiniTokens.body.copyWith(color: t.muted)),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text(TiniStrings.infoClose),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

/// Başlık yanına konan küçük "?" düğmesi.
class InfoIconButton extends StatelessWidget {
  const InfoIconButton({super.key, required this.title, required this.body});
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final t = TiniTokens.of(context);
    return IconButton(
      tooltip: TiniStrings.infoTooltip,
      visualDensity: VisualDensity.compact,
      icon: Icon(Icons.help_outline_rounded, size: 20, color: t.muted),
      onPressed: () => showTiniInfoSheet(context, title: title, body: body),
    );
  }
}
