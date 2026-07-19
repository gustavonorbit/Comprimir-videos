import 'dart:async';

import 'package:flutter/services.dart';

import '../models/selected_video.dart';

/// Recebe referencias de video entregues por outro app via "Compartilhar"
/// (ACTION_SEND no Android). A tela nao conhece detalhes de Intent/Uri: aqui a
/// referencia ja chega pronta como [SelectedVideo], do mesmo jeito que o
/// seletor de arquivos entrega.
abstract class SharedVideoService {
  /// Video que estava pendente quando o app foi aberto (cold start) a partir
  /// de um compartilhamento. Retorna null quando nao havia nenhum. So retorna
  /// um valor uma unica vez por compartilhamento.
  Future<SelectedVideo?> consumeInitialSharedVideo();

  /// Videos recebidos por compartilhamento enquanto o app ja esta aberto.
  Stream<SelectedVideo> get sharedVideoStream;
}

class PlatformSharedVideoService implements SharedVideoService {
  static const MethodChannel _channel = MethodChannel(
    'video_preparo_mobile/shared_intent',
  );
  static const EventChannel _eventChannel = EventChannel(
    'video_preparo_mobile/shared_intent_stream',
  );

  Stream<SelectedVideo>? _sharedVideoStream;

  @override
  Future<SelectedVideo?> consumeInitialSharedVideo() async {
    try {
      final data = await _channel.invokeMapMethod<String, Object?>(
        'consumeInitialSharedVideo',
      );
      return _toSelectedVideo(data);
    } on PlatformException {
      return null;
    } on MissingPluginException {
      return null;
    }
  }

  @override
  Stream<SelectedVideo> get sharedVideoStream {
    return _sharedVideoStream ??= _eventChannel
        .receiveBroadcastStream()
        .map((event) {
          final raw = Map<Object?, Object?>.from(event as Map);
          final data = raw.map((key, value) => MapEntry(key as String, value));
          return _toSelectedVideo(data);
        })
        .where((video) => video != null)
        .cast<SelectedVideo>();
  }

  SelectedVideo? _toSelectedVideo(Map<String, Object?>? data) {
    if (data == null) {
      return null;
    }

    final uri = data['uri'] as String?;
    final displayName = data['displayName'] as String?;
    if (uri == null ||
        uri.isEmpty ||
        displayName == null ||
        displayName.isEmpty) {
      return null;
    }

    return SelectedVideo(
      uri: uri,
      displayName: displayName,
      mimeType: data['mimeType'] as String?,
      sizeBytes: _asInt(data['sizeBytes']),
    );
  }

  int? _asInt(Object? value) {
    if (value is int) {
      return value;
    }
    if (value is num) {
      return value.toInt();
    }
    if (value is String) {
      return int.tryParse(value);
    }
    return null;
  }
}
