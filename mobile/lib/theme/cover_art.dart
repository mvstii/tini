import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Yedek kapak türleri: hepsi şarkı kimliğinden deterministik türetilir.
enum CoverArtKind { rings, bokeh, stripes, horizon, orb }

/// Üretilmiş kapak çizimi: tasarımdaki beş yer tutucu tarzı. Boyuta göre ölçeklenir.
class TiniCoverArtPainter extends CustomPainter {
  const TiniCoverArtPainter(this.kind, this.variant);
  final CoverArtKind kind;
  final int variant;

  @override
  void paint(Canvas canvas, Size s) {
    final r = Offset.zero & s;
    final v = variant == 0;
    switch (kind) {
      case CoverArtKind.rings:
        final inner = v ? const Color(0xFFF2A9C8) : const Color(0xFF8FD3FF);
        final mid = v ? const Color(0xFF7B6CF0) : const Color(0xFF4A6CF0);
        final outer = v ? const Color(0xFF1E1650) : const Color(0xFF10204F);
        canvas.drawRect(r, Paint()..color = outer);
        final c = Offset(s.width * 0.58, s.height * 0.42);
        final maxR = s.longestSide;
        for (var i = 11; i >= 0; i--) {
          final t = i / 11;
          final col = Color.lerp(inner, i.isEven ? mid : outer, 0.25 + t * 0.7)!;
          canvas.drawCircle(c, maxR * (0.06 + t * 0.94), Paint()..color = col);
        }
      case CoverArtKind.bokeh:
        canvas.drawRect(r, Paint()..color = const Color(0xFF12071A));
        void blob(Offset at, double rad, Color col) {
          canvas.drawCircle(
              at,
              rad,
              Paint()
                ..shader = RadialGradient(
                  colors: [col, col.withValues(alpha: 0.55), col.withValues(alpha: 0)],
                  stops: const [0, 0.45, 1],
                ).createShader(Rect.fromCircle(center: at, radius: rad)));
        }

        blob(Offset(s.width * 0.34, s.height * 0.3), s.width * 0.34,
            v ? const Color(0xFFE8B84A) : const Color(0xFFD9E8F5));
        blob(Offset(s.width * 0.68, s.height * 0.66), s.width * 0.32,
            v ? const Color(0xFFE8457A) : const Color(0xFF5F86C9));
      case CoverArtKind.stripes:
        final a = v ? const Color(0xFFFFC24B) : const Color(0xFFFF7BC8);
        final b = v ? const Color(0xFFE0502A) : const Color(0xFF7B4DE0);
        canvas.drawRect(
            r,
            Paint()
              ..shader = LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [a, b],
              ).createShader(r));
        final p = Paint()..color = const Color(0x22000000);
        final step = s.width / 6;
        for (var x = -s.height; x < s.width * 1.2; x += step) {
          final path = Path()
            ..moveTo(x, s.height)
            ..lineTo(x + step * 0.5, s.height)
            ..lineTo(x + step * 0.5 + s.height * 0.6, 0)
            ..lineTo(x + s.height * 0.6, 0)
            ..close();
          canvas.drawPath(path, p);
        }
      case CoverArtKind.horizon:
        final top = v ? const Color(0xFFFF5FA8) : const Color(0xFFFFD27A);
        final bottom = v ? const Color(0xFF24102E) : const Color(0xFF1A1230);
        final dot = v ? const Color(0xFFC9A4FF) : const Color(0xFFFF9AD5);
        canvas.drawRect(r, Paint()..color = bottom);
        canvas.drawRect(Rect.fromLTWH(0, 0, s.width, s.height * 0.55), Paint()..color = top);
        canvas.drawCircle(Offset(s.width / 2, s.height * 0.55), s.width * 0.18, Paint()..color = dot);
      case CoverArtKind.orb:
        canvas.drawRect(r, Paint()..color = v ? const Color(0xFF0E2447) : const Color(0xFF111A22));
        final c = Offset(s.width / 2, s.height / 2);
        final rad = s.width * 0.2;
        canvas.drawCircle(
            c,
            rad,
            Paint()
              ..shader = RadialGradient(
                center: const Alignment(-0.3, -0.4),
                colors: v
                    ? const [Color(0xFFBDE8FF), Color(0xFF2A7BFF), Color(0xFF123A9A)]
                    : const [Color(0xFFE9EEF3), Color(0xFF7C8A9A), Color(0xFF2A323C)],
              ).createShader(Rect.fromCircle(center: c, radius: rad)));
    }
    // Hafif parlama katmanı (üst sol).
    canvas.drawRect(
        r,
        Paint()
          ..shader = RadialGradient(
            center: const Alignment(-0.8, -0.9),
            radius: math.sqrt2,
            colors: const [Color(0x22FFFFFF), Color(0x00FFFFFF)],
          ).createShader(r));
  }

  @override
  bool shouldRepaint(TiniCoverArtPainter old) => old.kind != kind || old.variant != variant;
}
