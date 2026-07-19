import 'package:flutter_test/flutter_test.dart';
import 'package:video_preparo_mobile/models/compression_result.dart';
import 'package:video_preparo_mobile/models/selected_video.dart';
import 'package:video_preparo_mobile/services/automatic_compression_strategy.dart';

void main() {
  const strategy = AutomaticCompressionStrategy();

  test('configuracao automatica usa compressao maxima aceitavel em MP4', () {
    const video = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'evidencia.mov',
      width: 1920,
      height: 1080,
    );
    final settings = strategy.buildMaximumCompressionSettings(video);

    expect(settings.strategyName, 'maximumCompression');
    expect(settings.videoBitrate, 2_200_000);
    expect(settings.resolutionPolicy, 'Original');
    expect(settings.rotationPolicy, 'Original');
    expect(settings.keepAudio, isTrue);
    expect(settings.outputExtension, 'mp4');
  });

  test('saida sempre usa MP4 e nao sobrescreve o nome original', () {
    const video = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'evidencia.mov',
    );
    final settings = strategy.buildMaximumCompressionSettings(video);

    expect(settings.outputFileNameFor(video), 'evidencia_comprimido.mp4');
  });

  test('bitrate automatico cresce conforme a resolucao do video', () {
    final small = strategy.buildMaximumCompressionSettings(
      const SelectedVideo(
        uri: 'content://video/small',
        displayName: 'small.mp4',
        width: 640,
        height: 360,
      ),
    );
    final hd = strategy.buildMaximumCompressionSettings(
      const SelectedVideo(
        uri: 'content://video/hd',
        displayName: 'hd.mp4',
        width: 1280,
        height: 720,
      ),
    );
    final fullHd = strategy.buildMaximumCompressionSettings(
      const SelectedVideo(
        uri: 'content://video/full-hd',
        displayName: 'full-hd.mp4',
        width: 1920,
        height: 1080,
      ),
    );
    final ultraHd = strategy.buildMaximumCompressionSettings(
      const SelectedVideo(
        uri: 'content://video/uhd',
        displayName: 'uhd.mp4',
        width: 3840,
        height: 2160,
      ),
    );

    expect(small.videoBitrate, 700_000);
    expect(hd.videoBitrate, 1_200_000);
    expect(fullHd.videoBitrate, 2_200_000);
    expect(ultraHd.videoBitrate, 5_500_000);
  });

  test('video pequeno mantem resolucao original e nao recebe upscale', () {
    const video = SelectedVideo(
      uri: 'content://video/low',
      displayName: 'low.mp4',
      width: 320,
      height: 240,
    );
    final settings = strategy.buildMaximumCompressionSettings(video);

    expect(settings.videoBitrate, 700_000);
    expect(settings.resolutionPolicy, 'Original');
  });

  test('calcula percentual de economia', () {
    const result = CompressionResult(
      outputName: 'saida.mp4',
      outputUri: 'content://saida',
      outputLocationLabel: 'Movies/Preparo de Videos',
      originalSizeBytes: 4000,
      outputSizeBytes: 1000,
      format: 'MP4',
    );

    expect(result.savingsPercent, 75);
  });
}
