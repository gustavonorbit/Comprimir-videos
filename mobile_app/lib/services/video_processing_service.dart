import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../core/errors/app_error.dart';
import '../models/compression_result.dart';
import '../models/compression_settings.dart';
import '../models/selected_video.dart';
import '../models/video_processing_progress.dart';

abstract class VideoProcessingService {
  Stream<VideoProcessingProgress> get progressStream;

  Future<CompressionResult> compressVideo({
    required SelectedVideo video,
    required CompressionSettings settings,
  });

  Future<void> cancelProcessing();

  Future<void> shareResult(CompressionResult result);

  Future<void> openResult(CompressionResult result);
}

class PlatformVideoProcessingService implements VideoProcessingService {
  static const MethodChannel _channel = MethodChannel(
    'video_preparo_mobile/video_processing',
  );
  static const EventChannel _progressChannel = EventChannel(
    'video_preparo_mobile/video_processing_progress',
  );

  Stream<VideoProcessingProgress>? _progressStream;

  @override
  Stream<VideoProcessingProgress> get progressStream {
    return _progressStream ??= _progressChannel.receiveBroadcastStream().map((
      event,
    ) {
      final data = Map<Object?, Object?>.from(event as Map);
      return VideoProcessingProgress(
        stage: _stageFromString(data['stage'] as String?),
        percent: _asInt(data['percent']),
        message: data['message'] as String?,
      );
    });
  }

  @override
  Future<CompressionResult> compressVideo({
    required SelectedVideo video,
    required CompressionSettings settings,
  }) async {
    try {
      final data = await _channel
          .invokeMapMethod<String, Object?>('compressVideo', {
            'uri': video.uri,
            'path': video.localPath,
            'displayName': video.displayName,
            'outputName': settings.outputFileNameFor(video),
            'originalSizeBytes': video.sizeBytes,
            'strategyName': settings.strategyName,
            'videoBitrate': settings.videoBitrate,
            'resolutionPolicy': settings.resolutionPolicy,
            'rotationPolicy': settings.rotationPolicy,
            'keepAudio': settings.keepAudio,
          });

      if (data == null) {
        throw const AppError(
          'Nao foi possivel concluir a compressao.',
          debugMessage: 'Native compressVideo returned null.',
        );
      }

      return CompressionResult(
        outputName:
            data['outputName'] as String? ?? settings.outputFileNameFor(video),
        outputUri: data['outputUri'] as String? ?? '',
        outputLocationLabel:
            data['outputLocationLabel'] as String? ?? 'Destino automatico',
        originalSizeBytes:
            _asInt(data['originalSizeBytes']) ?? video.sizeBytes ?? 0,
        outputSizeBytes: _asInt(data['outputSizeBytes']) ?? 0,
        format: data['format'] as String? ?? 'MP4',
      );
    } on PlatformException catch (error) {
      if (kDebugMode) {
        debugPrint(
          'Compression PlatformException: ${error.code} ${error.message}',
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
        debugPrint('Compression unexpected error: $error');
      }
      throw AppError(
        'Erro inesperado ao comprimir o video.',
        debugMessage: error.toString(),
      );
    }
  }

  @override
  Future<void> cancelProcessing() async {
    await _channel.invokeMethod<void>('cancelCompression');
  }

  @override
  Future<void> shareResult(CompressionResult result) async {
    try {
      await _channel.invokeMethod<void>('shareResult', {
        'uri': result.outputUri,
        'mimeType': 'video/mp4',
      });
    } on PlatformException catch (error) {
      if (kDebugMode) {
        debugPrint('Share PlatformException: ${error.code} ${error.message}');
      }
      throw AppError(
        _mapResultActionError(error, 'Não foi possível compartilhar o vídeo.'),
        debugMessage: '${error.code}: ${error.message}',
      );
    } catch (error) {
      if (kDebugMode) {
        debugPrint('Share unexpected error: $error');
      }
      throw AppError(
        'Não foi possível compartilhar o vídeo.',
        debugMessage: error.toString(),
      );
    }
  }

  @override
  Future<void> openResult(CompressionResult result) async {
    try {
      await _channel.invokeMethod<void>('openResult', {
        'uri': result.outputUri,
        'mimeType': 'video/mp4',
      });
    } on PlatformException catch (error) {
      if (kDebugMode) {
        debugPrint('Open PlatformException: ${error.code} ${error.message}');
      }
      throw AppError(
        _mapResultActionError(error, 'Não foi possível abrir o vídeo.'),
        debugMessage: '${error.code}: ${error.message}',
      );
    } catch (error) {
      if (kDebugMode) {
        debugPrint('Open unexpected error: $error');
      }
      throw AppError(
        'Não foi possível abrir o vídeo.',
        debugMessage: error.toString(),
      );
    }
  }

  String _mapResultActionError(PlatformException error, String defaultMessage) {
    switch (error.code) {
      case 'no_app':
        return 'Nenhum aplicativo compatível foi encontrado.';
      default:
        return defaultMessage;
    }
  }

  VideoProcessingStage _stageFromString(String? value) {
    switch (value) {
      case 'preparing':
        return VideoProcessingStage.preparing;
      case 'saving':
        return VideoProcessingStage.saving;
      case 'completed':
        return VideoProcessingStage.completed;
      case 'cancelled':
        return VideoProcessingStage.cancelled;
      case 'processing':
      default:
        return VideoProcessingStage.processing;
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

  String _mapPlatformError(PlatformException error) {
    switch (error.code) {
      case 'cancelled':
        return 'Compressao cancelada.';
      case 'unsupported_settings':
        return 'Esta combinacao de opcoes ainda nao esta disponivel no Android.';
      case 'file_not_found':
        return 'O video selecionado nao esta mais disponivel.';
      case 'storage_failed':
        return 'Nao foi possivel salvar o video comprimido.';
      case 'compression_failed':
        return 'Nao foi possivel comprimir este video no dispositivo.';
      case 'busy':
        return 'Ja existe uma compressao em andamento.';
      default:
        return 'Nao foi possivel concluir a compressao.';
    }
  }
}
