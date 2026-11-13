import 'package:flutter_test/flutter_test.dart';
import 'package:tini/badges.dart';

void main() {
  Set<String> earned(int total, List<int> counts) => {
        for (final b in computeBadges(total: total, counts: counts))
          if (b.earned) b.id,
      };

  test('no votes earns nothing', () {
    expect(earned(0, [0, 0, 0, 0, 0, 0]), isEmpty);
  });

  test('milestones follow the total vote count', () {
    expect(earned(1, [0, 0, 0, 1, 0, 0]), {'first'});
    expect(earned(30, [5, 5, 5, 5, 5, 5]), containsAll({'first', 'warmup', 'tour', 'scale'}));
    expect(earned(99, [0, 0, 0, 99, 0, 0]), isNot(contains('hundred')));
    expect(earned(100, [0, 0, 0, 100, 0, 0]), contains('hundred'));
    expect(earned(500, [0, 0, 0, 500, 0, 0]), contains('ear'));
  });

  test('amazing, harsh and scale badges read the distribution', () {
    expect(earned(10, [0, 0, 0, 0, 0, 1]), contains('amazing1'));
    expect(earned(10, [0, 0, 0, 0, 0, 10]), contains('amazing10'));
    expect(earned(10, [6, 4, 0, 0, 0, 0]), contains('critic'));
    expect(earned(10, [1, 1, 1, 1, 1, 0]), isNot(contains('scale')));
  });

  test('progress is clamped and deterministic', () {
    final a = computeBadges(total: 37, counts: [0, 0, 0, 37, 0, 0]);
    final b = computeBadges(total: 37, counts: [0, 0, 0, 37, 0, 0]);
    final hundred = a.firstWhere((x) => x.id == 'hundred');
    expect(hundred.progress, closeTo(0.37, 1e-9));
    expect(a.firstWhere((x) => x.id == 'first').progress, 1.0);
    expect([for (final x in a) x.value], [for (final x in b) x.value]);
  });
}
