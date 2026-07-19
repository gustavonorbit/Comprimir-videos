class SelectedVideo {
  const SelectedVideo({
    required this.uri,
    required this.displayName,
    this.mimeType,
    this.sizeBytes,
    this.duration,
    this.width,
    this.height,
    this.rotation,
    this.localPath,
  });

  final String uri;
  final String displayName;
  final String? mimeType;
  final int? sizeBytes;
  final Duration? duration;
  final int? width;
  final int? height;
  final int? rotation;
  final String? localPath;

  String get extension {
    final cleanName = displayName.split('?').first;
    final dotIndex = cleanName.lastIndexOf('.');
    if (dotIndex < 0 || dotIndex == cleanName.length - 1) {
      return 'Nao informado';
    }
    return cleanName.substring(dotIndex + 1).toUpperCase();
  }

  String get friendlyResolution {
    if (width == null || height == null) {
      return 'Nao informada';
    }
    return '${width}x$height';
  }

  SelectedVideo copyWith({
    String? uri,
    String? displayName,
    String? mimeType,
    int? sizeBytes,
    Duration? duration,
    int? width,
    int? height,
    int? rotation,
    String? localPath,
  }) {
    return SelectedVideo(
      uri: uri ?? this.uri,
      displayName: displayName ?? this.displayName,
      mimeType: mimeType ?? this.mimeType,
      sizeBytes: sizeBytes ?? this.sizeBytes,
      duration: duration ?? this.duration,
      width: width ?? this.width,
      height: height ?? this.height,
      rotation: rotation ?? this.rotation,
      localPath: localPath ?? this.localPath,
    );
  }
}
