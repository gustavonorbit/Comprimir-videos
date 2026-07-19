import 'package:flutter_test/flutter_test.dart';
import 'package:video_preparo_mobile/core/utils/formatters.dart';

void main() {
  group('formatBytes', () {
    test('formata bytes em unidades amigaveis', () {
      expect(formatBytes(500), '500 B');
      expect(formatBytes(1024 * 2), '2 KB');
      expect(formatBytes(1024 * 1024 * 5), '5 MB');
    });

    test('trata valor ausente', () {
      expect(formatBytes(null), 'Nao informado');
    });
  });

  group('formatDuration', () {
    test('formata duracao curta', () {
      expect(formatDuration(const Duration(seconds: 75)), '1:15');
    });

    test('formata duracao com horas', () {
      expect(
        formatDuration(const Duration(hours: 1, minutes: 2, seconds: 3)),
        '1:02:03',
      );
    });

    test('trata duracao ausente', () {
      expect(formatDuration(null), 'Nao informada');
    });
  });
}
