import 'package:flutter/material.dart';

/// Faz 2'de oylama kuyruğu burada olacak; şimdilik boş ekran.
class RatingScreen extends StatelessWidget {
  const RatingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Oylama')),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('Oylanacak şarkı yok. Oylama kuyruğu Faz 2\'de gelecek.'),
        ),
      ),
    );
  }
}
