import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_preparo_mobile/core/errors/app_error.dart';
import 'package:video_preparo_mobile/models/compression_result.dart';
import 'package:video_preparo_mobile/models/selected_video.dart';
import 'package:video_preparo_mobile/services/automatic_compression_strategy.dart';
import 'package:video_preparo_mobile/services/video_processing_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('video_preparo_mobile/video_processing');
  const result = CompressionResult(
    outputName: 'video_comprimido.mp4',
    outputUri: 'content://output/1',
    outputLocationLabel: 'Movies/Preparo de Videos',
    originalSizeBytes: 1000,
    outputSizeBytes: 500,
    format: 'MP4',
  );

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test(
    'compressao envia configuracao automatica em MP4 para o Android',
    () async {
      late MethodCall capturedCall;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            capturedCall = call;
            return <String, Object?>{
              'outputName': 'evidencia_comprimido.mp4',
              'outputUri': 'content://output/automatic',
              'outputLocationLabel': 'Movies/Preparo de Videos',
              'originalSizeBytes': 4000,
              'outputSizeBytes': 1200,
              'format': 'MP4',
            };
          });

      const video = SelectedVideo(
        uri: 'content://video/automatic',
        displayName: 'evidencia.mov',
        sizeBytes: 4000,
        width: 1280,
        height: 720,
      );
      const strategy = AutomaticCompressionStrategy();
      final service = PlatformVideoProcessingService();

      final compressed = await service.compressVideo(
        video: video,
        settings: strategy.buildMaximumCompressionSettings(video),
      );

      final arguments = Map<Object?, Object?>.from(
        capturedCall.arguments as Map,
      );
      expect(capturedCall.method, 'compressVideo');
      expect(arguments['outputName'], 'evidencia_comprimido.mp4');
      expect(arguments['strategyName'], 'maximumCompression');
      expect(arguments['videoBitrate'], 1_200_000);
      expect(arguments['resolutionPolicy'], 'Original');
      expect(arguments['rotationPolicy'], 'Original');
      expect(arguments['keepAudio'], isTrue);
      expect(arguments.containsKey('profile'), isFalse);
      expect(arguments.containsKey('removeAudio'), isFalse);
      expect(compressed.format, 'MP4');
    },
  );

  test(
    'compartilhar propaga mensagem quando nenhum app compativel existe',
    () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            if (call.method == 'shareResult') {
              throw PlatformException(code: 'no_app');
            }
            return null;
          });

      final service = PlatformVideoProcessingService();

      await expectLater(
        () => service.shareResult(result),
        throwsA(
          isA<AppError>().having(
            (error) => error.userMessage,
            'userMessage',
            'Nenhum aplicativo compatível foi encontrado.',
          ),
        ),
      );
    },
  );

  test('compartilhar propaga mensagem generica em outras falhas', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'shareResult') {
            throw PlatformException(code: 'share_failed');
          }
          return null;
        });

    final service = PlatformVideoProcessingService();

    await expectLater(
      () => service.shareResult(result),
      throwsA(
        isA<AppError>().having(
          (error) => error.userMessage,
          'userMessage',
          'Não foi possível compartilhar o vídeo.',
        ),
      ),
    );
  });

  test(
    'abrir video propaga mensagem quando nenhum app compativel existe',
    () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            if (call.method == 'openResult') {
              throw PlatformException(code: 'no_app');
            }
            return null;
          });

      final service = PlatformVideoProcessingService();

      await expectLater(
        () => service.openResult(result),
        throwsA(
          isA<AppError>().having(
            (error) => error.userMessage,
            'userMessage',
            'Nenhum aplicativo compatível foi encontrado.',
          ),
        ),
      );
    },
  );

  test('abrir video propaga mensagem generica em outras falhas', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'openResult') {
            throw PlatformException(code: 'open_failed');
          }
          return null;
        });

    final service = PlatformVideoProcessingService();

    await expectLater(
      () => service.openResult(result),
      throwsA(
        isA<AppError>().having(
          (error) => error.userMessage,
          'userMessage',
          'Não foi possível abrir o vídeo.',
        ),
      ),
    );
  });
}
