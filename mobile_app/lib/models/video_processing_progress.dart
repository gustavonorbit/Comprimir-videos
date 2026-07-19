enum VideoProcessingStage {
  preparing,
  processing,
  saving,
  completed,
  cancelled,
}

class VideoProcessingProgress {
  const VideoProcessingProgress({
    required this.stage,
    this.percent,
    this.message,
  });

  final VideoProcessingStage stage;
  final int? percent;
  final String? message;

  bool get hasPercent => percent != null;
}
