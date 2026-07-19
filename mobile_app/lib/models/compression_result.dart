class CompressionResult {
  const CompressionResult({
    required this.outputName,
    required this.outputUri,
    required this.outputLocationLabel,
    required this.originalSizeBytes,
    required this.outputSizeBytes,
    required this.format,
  });

  final String outputName;
  final String outputUri;
  final String outputLocationLabel;
  final int originalSizeBytes;
  final int outputSizeBytes;
  final String format;

  double get savingsPercent {
    if (originalSizeBytes <= 0) {
      return 0;
    }
    final saved = originalSizeBytes - outputSizeBytes;
    return (saved / originalSizeBytes) * 100;
  }
}
