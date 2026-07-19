import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:mime/mime.dart';

import '../core/errors/app_error.dart';
import '../models/selected_video.dart';

abstract class VideoInfoService {
  Future<SelectedVideo> loadInfo(SelectedVideo video);
}

class PlatformVideoInfoService implements VideoInfoService {
  static const MethodChannel _channel = MethodChannel(
    'video_preparo_mobile/video_info',
  );

  @override
  Future<SelectedVideo> loadInfo(SelectedVideo video) async {
    try {
      final data = await _channel.invokeMapMethod<String, Object?>(
        'getVideoInfo',
        {
          'uri': video.uri,
          'path': video.localPath,
          'displayName': video.displayName,
        },
      );

      if (data == null) {
        throw const AppError(
          'Nao foi possivel ler os dados deste video.',
          debugMessage: 'Native getVideoInfo returned null.',
        );
      }

      final durationMs = _asInt(data['durationMs']);
      final sizeBytes = _asInt(data['sizeBytes']) ?? video.sizeBytes;
      final width = _asInt(data['width']);
      final height = _asInt(data['height']);
      final rotation = _asInt(data['rotation']);
      final mimeType =
          _asString(data['mimeType']) ??
          video.mimeType ??
          lookupMimeType(video.displayName);
      final displayName = _asString(data['displayName']) ?? video.displayName;

      return video.copyWith(
        displayName: displayName,
        mimeType: mimeType,
        sizeBytes: sizeBytes,
        duration: durationMs == null
            ? null
            : Duration(milliseconds: durationMs),
        width: width,
        height: height,
        rotation: rotation,
      );
    } on PlatformException catch (error) {
      if (kDebugMode) {
        debugPrint(
          'VideoInfo PlatformException: ${error.code} ${error.message}',
        );
      }
      throw AppError(
        _mapPlatformError(error),
        debugMessage: '${error.code}: ${error.message}',
      );
    } on AppError {
      rethrow;
    } catch (error) {
      if (kDebugMode) {
        debugPrint('VideoInfo unexpected error: $error');
      }
      throw AppError(
        'Erro inesperado ao ler o video selecionado.',
        debugMessage: error.toString(),
      );
    }
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

  String? _asString(Object? value) {
    if (value is String && value.isNotEmpty) {
      return value;
    }
    return null;
  }

  String _mapPlatformError(PlatformException error) {
    switch (error.code) {
      case 'permission_denied':
        return 'Permissao negada. Autorize o acesso ao video e tente novamente.';
      case 'file_not_found':
        return 'O video selecionado nao esta mais disponivel.';
      case 'unsupported':
        return 'Este formato nao foi reconhecido pelo dispositivo.';
      case 'metadata_failed':
        return 'Nao foi possivel ler os metadados deste video.';
      default:
        return 'Nao foi possivel ler o video selecionado.';
    }
  }
}
