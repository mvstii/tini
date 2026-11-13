import 'package:flutter/material.dart';

import 'app_state.dart' show tourVotes;

/// Oy geçmişinden türetilen rozet: ad, ipucu, hedef ve mevcut değer.
/// Hiçbir şey saklanmaz; aynı oy sayıları her zaman aynı rozetleri verir.
@immutable
class TiniBadge {
  const TiniBadge({
    required this.id,
    required this.title,
    required this.hint,
    required this.icon,
    required this.goal,
    required this.value,
  });

  final String id;
  final String title;
  final String hint;
  final IconData icon;
  final int goal;
  final int value;

  bool get earned => value >= goal;

  /// 0–1 arası ilerleme.
  double get progress => goal <= 0 ? 1 : (value / goal).clamp(0.0, 1.0);
}

/// [counts]: 1–6 oy sayıları (indeks 0 = oy 1). Rozetler kazanım sırasına göre dizilir.
List<TiniBadge> computeBadges({required int total, required List<int> counts}) {
  assert(counts.length == 6);
  final amazing = counts[5];
  final harsh = counts[0] + counts[1];
  final usedLevels = counts.where((c) => c > 0).length;
  return [
    TiniBadge(
      id: 'first',
      title: 'İlk adım',
      hint: 'İlk oyunu ver',
      icon: Icons.flag_rounded,
      goal: 1,
      value: total,
    ),
    TiniBadge(
      id: 'warmup',
      title: 'Isınma',
      hint: '10 şarkı oyla',
      icon: Icons.whatshot_rounded,
      goal: 10,
      value: total,
    ),
    TiniBadge(
      id: 'tour',
      title: 'İlk tur',
      hint: '$tourVotes şarkı oyla',
      icon: Icons.route_rounded,
      goal: tourVotes,
      value: total,
    ),
    TiniBadge(
      id: 'hundred',
      title: 'Yüzlük',
      hint: '100 şarkı oyla',
      icon: Icons.looks_one_rounded,
      goal: 100,
      value: total,
    ),
    TiniBadge(
      id: 'ear',
      title: 'Usta kulak',
      hint: '500 şarkı oyla',
      icon: Icons.hearing_rounded,
      goal: 500,
      value: total,
    ),
    TiniBadge(
      id: 'amazing1',
      title: 'İlk Efsane',
      hint: 'Bir şarkıya 6 ver',
      icon: Icons.auto_awesome_rounded,
      goal: 1,
      value: amazing,
    ),
    TiniBadge(
      id: 'amazing10',
      title: 'Efsane avcısı',
      hint: '10 şarkıya 6 ver',
      icon: Icons.diamond_rounded,
      goal: 10,
      value: amazing,
    ),
    TiniBadge(
      id: 'critic',
      title: 'Titiz kulak',
      hint: '10 şarkıya 1 ya da 2 ver',
      icon: Icons.thumb_down_alt_rounded,
      goal: 10,
      value: harsh,
    ),
    TiniBadge(
      id: 'scale',
      title: 'Tam skala',
      hint: '1’den 6’ya her oyu kullan',
      icon: Icons.equalizer_rounded,
      goal: 6,
      value: usedLevels,
    ),
  ];
}
