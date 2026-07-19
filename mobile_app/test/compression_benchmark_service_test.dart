import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_preparo_mobile/core/errors/app_error.dart';
import 'package:video_preparo_mobile/models/selected_video.dart';
import 'package:video_preparo_mobile/services/compression_benchmark_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('video_preparo_mobile/compression_benchmark');
  const video = SelectedVideo(
    uri: 'content://video/benchmark',
    displayName: 'evidencia.mp4',
    sizeBytes: 4000,
    width: 1920,
    height: 1080,
  );

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test(
    'runBenchmark envia modo, bitrate base e dados do video para o canal correto',
    () async {
      late MethodCall capturedCall;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            capturedCall = call;
            return <String, Object?>{
              'modoSolicitado': 'cq_conservador',
              'modoUtilizado': 'cq',
              'nomeEncoder': 'c2.android.avc.encoder',
              'mimeSaida': 'video/avc',
              'suporteDeclaradoCq': true,
              'qualityRangeMin': 0,
              'qualityRangeMax': 100,
              'qualidadeSolicitada': 85,
              'qualidadeEfetiva': null,
              'fallbackExecutado': false,
              'tamanhoOriginalBytes': 4000,
              'tamanhoFinalBytes': 1800,
              'percentualReducao': 55.0,
              'duracaoVideoMs': 300000,
              'tempoProcessamentoMs': 12000,
              'resolucao': '1920x1080',
              'fps': 30.0,
              'bitrateMedioFinalBps': 48000,
              'sucesso': true,
              'mensagemErro': null,
              'notaTecnica': 'Qualidade efetiva nao legivel via API publica.',
              'outputName': 'benchmark_cq_conservador_123.mp4',
              'outputUri': 'content://output/benchmark/1',
            };
          });

      final service = PlatformCompressionBenchmarkService();

      final result = await service.runBenchmark(
        video: video,
        baseVbrBitrate: 2_200_000,
        mode: BenchmarkMode.cqConservador,
      );

      final arguments = Map<Object?, Object?>.from(
        capturedCall.arguments as Map,
      );
      expect(capturedCall.method, 'runBenchmark');
      expect(arguments['uri'], 'content://video/benchmark');
      expect(arguments['mode'], 'cq_conservador');
      expect(arguments['baseVbrBitrate'], 2_200_000);
      expect(arguments['originalSizeBytes'], 4000);

      expect(result.modoUtilizado, 'cq');
      expect(result.nomeEncoder, 'c2.android.avc.encoder');
      expect(result.suporteDeclaradoCq, isTrue);
      expect(result.qualityRangeMin, 0);
      expect(result.qualityRangeMax, 100);
      expect(result.qualidadeSolicitada, 85);
      expect(result.qualidadeEfetiva, isNull);
      expect(result.fallbackExecutado, isFalse);
      expect(result.percentualReducao, 55.0);
      expect(result.sucesso, isTrue);
    },
  );

  test(
    'runBenchmark nunca declara CQ quando o resultado indica fallback para VBR',
    () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            return <String, Object?>{
              'modoSolicitado': 'cq_extremo',
              'modoUtilizado': 'vbr',
              'nomeEncoder': null,
              'mimeSaida': 'video/avc',
              'suporteDeclaradoCq': false,
              'qualityRangeMin': null,
              'qualityRangeMax': null,
              'qualidadeSolicitada': null,
              'qualidadeEfetiva': null,
              'fallbackExecutado': true,
              'tamanhoOriginalBytes': 4000,
              'tamanhoFinalBytes': 2200,
              'percentualReducao': 45.0,
              'duracaoVideoMs': 300000,
              'tempoProcessamentoMs': 9000,
              'resolucao': '1920x1080',
              'fps': 30.0,
              'bitrateMedioFinalBps': 58000,
              'sucesso': true,
              'mensagemErro': null,
              'notaTecnica':
                  'CQ foi solicitado mas o pipeline caiu para VBR: nenhum encoder suportado.',
              'outputName': 'benchmark_cq_extremo_456.mp4',
              'outputUri': 'content://output/benchmark/2',
            };
          });

      final service = PlatformCompressionBenchmarkService();
      final result = await service.runBenchmark(
        video: video,
        baseVbrBitrate: 2_200_000,
        mode: BenchmarkMode.cqExtremo,
      );

      expect(result.modoUtilizado, 'vbr');
      expect(result.fallbackExecutado, isTrue);
      expect(result.suporteDeclaradoCq, isFalse);
    },
  );

  test('runBenchmark propaga mensagem quando disponivel apenas em debug', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          throw PlatformException(code: 'debug_only');
        });

    final service = PlatformCompressionBenchmarkService();

    await expectLater(
      () => service.runBenchmark(
        video: video,
        baseVbrBitrate: 2_200_000,
        mode: BenchmarkMode.vbrAtual,
      ),
      throwsA(
        isA<AppError>().having(
          (error) => error.userMessage,
          'userMessage',
          'Benchmark disponivel apenas em build debug.',
        ),
      ),
    );
  });

  test('runBenchmark propaga mensagem quando ja ha benchmark em andamento', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          throw PlatformException(code: 'busy');
        });

    final service = PlatformCompressionBenchmarkService();

    await expectLater(
      () => service.runBenchmark(
        video: video,
        baseVbrBitrate: 2_200_000,
        mode: BenchmarkMode.vbrAtual,
      ),
      throwsA(
        isA<AppError>().having(
          (error) => error.userMessage,
          'userMessage',
          'Ja existe um benchmark em andamento.',
        ),
      ),
    );
  });
}
