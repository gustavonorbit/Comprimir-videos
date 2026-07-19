String formatBytes(int? bytes) {
  if (bytes == null) {
    return 'Nao informado';
  }
  if (bytes < 0) {
    return 'Nao informado';
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  var size = bytes.toDouble();
  var unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  final hasFraction = size % 1 != 0;
  final value = hasFraction && size < 10
      ? size.toStringAsFixed(1)
      : size.toStringAsFixed(0);
  return '$value ${units[unitIndex]}';
}

String formatDuration(Duration? duration) {
  if (duration == null) {
    return 'Nao informada';
  }

  final totalSeconds = duration.inSeconds;
  final hours = totalSeconds ~/ 3600;
  final minutes = (totalSeconds % 3600) ~/ 60;
  final seconds = totalSeconds % 60;

  if (hours > 0) {
    return '$hours:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  return '$minutes:${seconds.toString().padLeft(2, '0')}';
}
