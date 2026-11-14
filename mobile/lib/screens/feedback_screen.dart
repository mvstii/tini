import 'package:flutter/material.dart';

import '../api.dart';
import '../strings.dart';

const feedbackKinds = <String, String>{'bug': 'Hata', 'idea': 'Öneri', 'other': 'Diğer'};

/// Kapalı test geri bildirimi: tür + serbest metin. Yalnızca kayıt olarak gider.
class FeedbackScreen extends StatefulWidget {
  const FeedbackScreen({super.key, required this.api, this.onLogout});
  final Api api;
  final VoidCallback? onLogout;

  @override
  State<FeedbackScreen> createState() => _FeedbackScreenState();
}

class _FeedbackScreenState extends State<FeedbackScreen> {
  final _text = TextEditingController();
  String _kind = 'bug';
  bool _busy = false;
  bool _sent = false;
  String? _error;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final msg = _text.text.trim();
    if (msg.length < 3) {
      setState(() => _error = 'En az 3 karakter yaz');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.sendFeedback(_kind, 'home', msg);
      if (mounted) setState(() => _sent = true);
    } on ApiException catch (e) {
      if (e.status == 401) {
        if (mounted) Navigator.of(context).pop();
        return widget.onLogout?.call();
      }
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = TiniStrings.unreachable);
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Geri bildirim')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: _sent
            ? Center(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Text('Teşekkürler, iletildi.'),
                  const SizedBox(height: 12),
                  FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Kapat')),
                ]),
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SegmentedButton<String>(
                    segments: [
                      for (final e in feedbackKinds.entries)
                        ButtonSegment(value: e.key, label: Text(e.value)),
                    ],
                    selected: {_kind},
                    onSelectionChanged: (s) => setState(() => _kind = s.first),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _text,
                    maxLines: 6,
                    maxLength: 2000,
                    decoration: const InputDecoration(
                        border: OutlineInputBorder(), hintText: 'Ne oldu, ne bekliyordun?'),
                  ),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: _busy ? null : _send,
                    child: const Text('Gönder'),
                  ),
                ],
              ),
      ),
    );
  }
}
