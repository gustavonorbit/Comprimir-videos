import '../models/compression_settings.dart';
import '../models/selected_video.dart';

class AutomaticCompressionStrategy {
  const AutomaticCompressionStrategy();

  CompressionSettings buildMaximumCompressionSettings(SelectedVideo video) {
    final bitrate = _targetBitrateFor(video);

    return CompressionSettings(
      strategyName: 'maximumCompression',
      videoBitrate: bitrate,
      resolutionPolicy: 'Original',
      rotationPolicy: 'Original',
      keepAudio: true,
      outputExtension: 'mp4',
    );
  }

  int _targetBitrateFor(SelectedVideo video) {
    final width = video.width;
    final height = video.height;
    if (width == null || height == null || width <= 0 || height <= 0) {
      return 2_500_000;
    }

    final longEdge = width > height ? width : height;
    final pixels = width * height;

    if (longEdge <= 640 || pixels <= 640 * 480) {
      return 700_000;
    }
    if (longEdge <= 1280 || pixels <= 1280 * 720) {
      return 1_200_000;
    }
    if (longEdge <= 1920 || pixels <= 1920 * 1080) {
      return 2_200_000;
    }
    if (longEdge <= 2560 || pixels <= 2560 * 1440) {
      return 3_800_000;
    }
    return 5_500_000;
  }
}
