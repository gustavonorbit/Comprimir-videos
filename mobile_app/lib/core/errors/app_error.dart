class AppError implements Exception {
  const AppError(this.userMessage, {this.debugMessage});

  final String userMessage;
  final String? debugMessage;

  @override
  String toString() => debugMessage ?? userMessage;
}
