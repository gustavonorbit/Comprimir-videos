import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_preparo_mobile/services/shared_video_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const methodChannel = MethodChannel('video_preparo_mobile/shared_intent');

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(methodChannel, null);
  });

  test('retorna video quando a intent inicial contem dados validos', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(methodChannel, (call) async {
          expect(call.method, 'consumeInitialSharedVideo');
          return {
            'uri': 'content://media/shared/1',
            'displayName': 'compartilhado.mp4',
            'mimeType': 'video/mp4',
            'sizeBytes': 2048,
          };
        });

    final service = PlatformSharedVideoService();
    final video = await service.consumeInitialSharedVideo();

    expect(video, isNotNull);
    expect(video!.uri, 'content://media/shared/1');
    expect(video.displayName, 'compartilhado.mp4');
    expect(video.mimeType, 'video/mp4');
    expect(video.sizeBytes, 2048);
  });

  test('retorna nulo quando nao ha video pendente', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(methodChannel, (call) async => null);

    final service = PlatformSharedVideoService();
    final video = await service.consumeInitialSharedVideo();

    expect(video, isNull);
  });

  test('retorna nulo quando os dados nao tem uri', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(methodChannel, (call) async {
          return {'uri': '', 'displayName': 'sem_uri.mp4'};
        });

    final service = PlatformSharedVideoService();
    final video = await service.consumeInitialSharedVideo();

    expect(video, isNull);
  });

  test('retorna nulo quando os dados nao tem nome de exibicao', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(methodChannel, (call) async {
          return {'uri': 'content://media/shared/2', 'displayName': ''};
        });

    final service = PlatformSharedVideoService();
    final video = await service.consumeInitialSharedVideo();

    expect(video, isNull);
  });
}
