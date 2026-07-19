import 'selected_video.dart';

class CompressionSettings {
  const CompressionSettings({
    required this.strategyName,
    required this.videoBitrate,
    required this.resolutionPolicy,
    required this.rotationPolicy,
    required this.keepAudio,
    required this.outputExtension,
  });

  final String strategyName;
  final int videoBitrate;
  final String resolutionPolicy;
  final String rotationPolicy;
  final bool keepAudio;
  final String outputExtension;

  String outputFileNameFor(SelectedVideo video) {
    final name = video.displayName;
    final dotIndex = name.lastIndexOf('.');
    final stem = dotIndex > 0 ? name.substring(0, dotIndex) : name;
    final safeStem = stem.trim().isEmpty ? 'video' : stem.trim();
    return '${safeStem}_comprimido.$outputExtension';
  }
}
