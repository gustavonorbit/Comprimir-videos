import 'package:flutter/services.dart';

import '../core/errors/app_error.dart';
import '../models/selected_video.dart';

/// Um dos 4 modos internos do benchmark controlado: o VBR atualmente usado em producao (controle
/// da comparacao) e 3 configuracoes experimentais de qualidade constante (CQ), cada uma pedindo
/// uma fracao diferente da faixa de qualidade real do encoder do aparelho (nunca um numero fixo
/// como "70", que nao tem o mesmo significado em aparelhos diferentes).
///
/// Esta ferramenta e estritamente para uso interno/debug: nenhuma dessas opcoes deve aparecer
/// como escolha de qualidade na UI publica do app.
enum BenchmarkMode { vbrAtual, cqConservador, cqAgressivo, cqExtremo }

extension BenchmarkModeWire on BenchmarkMode {
  String get wireValue {
    switch (this) {
      case BenchmarkMode.vbrAtual:
        return 'vbr_atual';
      case BenchmarkMode.cqConservador:
        return 'cq_conservador';
      case BenchmarkMode.cqAgressivo:
        return 'cq_agressivo';
      case BenchmarkMode.cqExtremo:
        return 'cq_extremo';
    }
  }

  String get label {
    switch (this) {
      case BenchmarkMode.vbrAtual:
        return 'VBR atual (controle)';
      case BenchmarkMode.cqConservador:
        return 'CQ conservador';
      case BenchmarkMode.cqAgressivo:
        return 'CQ agressivo';
      case BenchmarkMode.cqExtremo:
        return 'CQ extremo';
    }
  }
}

/// Resultado bruto de uma unica execucao de benchmark, espelhando exatamente os campos
/// registrados pelo lado nativo (ver `CompressionBenchmarkRunner.kt`). Nenhum campo e inventado
/// aqui: quando o Android nao consegue identificar um valor (por exemplo, a qualidade CQ
/// efetivamente aplicada, que o Android nao expoe via API publica), o campo chega como nulo.
class BenchmarkRunResult {
  const BenchmarkRunResult({
    required this.modoSolicitado,
    required this.modoUtilizado,
    required this.nomeEncoder,
    required this.mimeSaida,
    required this.suporteDeclaradoCq,
    required this.qualityRangeMin,
    required this.qualityRangeMax,
    required this.qualidadeSolicitada,
    required this.qualidadeEfetiva,
    required this.fallbackExecutado,
    required this.tamanhoOriginalBytes,
    required this.tamanhoFinalBytes,
    required this.percentualReducao,
    required this.duracaoVideoMs,
    required this.tempoProcessamentoMs,
    required this.resolucao,
    required this.fps,
    required this.bitrateMedioFinalBps,
    required this.sucesso,
    required this.mensagemErro,
    required this.notaTecnica,
    required this.outputName,
    required this.outputUri,
  });

  factory BenchmarkRunResult.fromMap(Map<Object?, Object?> data) {
    return BenchmarkRunResult(
      modoSolicitado: data['modoSolicitado'] as String? ?? 'desconhecido',
      modoUtilizado: data['modoUtilizado'] as String?,
      nomeEncoder: data['nomeEncoder'] as String?,
      mimeSaida: data['mimeSaida'] as String? ?? 'video/avc',
      suporteDeclaradoCq: data['suporteDeclaradoCq'] as bool?,
      qualityRangeMin: _asInt(data['qualityRangeMin']),
      qualityRangeMax: _asInt(data['qualityRangeMax']),
      qualidadeSolicitada: _asInt(data['qualidadeSolicitada']),
      qualidadeEfetiva: _asInt(data['qualidadeEfetiva']),
      fallbackExecutado: data['fallbackExecutado'] as bool?,
      tamanhoOriginalBytes: _asInt(data['tamanhoOriginalBytes']) ?? 0,
      tamanhoFinalBytes: _asInt(data['tamanhoFinalBytes']),
      percentualReducao: _asDouble(data['percentualReducao']),
      duracaoVideoMs: _asInt(data['duracaoVideoMs']),
      tempoProcessamentoMs: _asInt(data['tempoProcessamentoMs']),
      resolucao: data['resolucao'] as String?,
      fps: _asDouble(data['fps']),
      bitrateMedioFinalBps: _asInt(data['bitrateMedioFinalBps']),
      sucesso: data['sucesso'] as bool? ?? false,
      mensagemErro: data['mensagemErro'] as String?,
      notaTecnica: data['notaTecnica'] as String?,
      outputName: data['outputName'] as String?,
      outputUri: data['outputUri'] as String?,
    );
  }

  final String modoSolicitado;
  final String? modoUtilizado;
  final String? nomeEncoder;
  final String mimeSaida;
  final bool? suporteDeclaradoCq;
  final int? qualityRangeMin;
  final int? qualityRangeMax;
  final int? qualidadeSolicitada;
  final int? qualidadeEfetiva;
  final bool? fallbackExecutado;
  final int tamanhoOriginalBytes;
  final int? tamanhoFinalBytes;
  final double? percentualReducao;
  final int? duracaoVideoMs;
  final int? tempoProcessamentoMs;
  final String? resolucao;
  final double? fps;
  final int? bitrateMedioFinalBps;
  final bool sucesso;
  final String? mensagemErro;
  final String? notaTecnica;
  final String? outputName;
  final String? outputUri;

  static int? _asInt(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return null;
  }

  static double? _asDouble(Object? value) {
    if (value is double) return value;
    if (value is num) return value.toDouble();
    return null;
  }
}

abstract class CompressionBenchmarkService {
  /// Roda uma unica execucao do benchmark para [mode], usando o mesmo [video] e o mesmo
  /// [baseVbrBitrate] (a mesma escada de bitrate que a compressao automatica de producao usaria)
  /// em todos os 4 modos, para que a comparacao seja valida. Nunca inicia compressao automatica:
  /// cada modo precisa ser disparado manualmente.
  Future<BenchmarkRunResult> runBenchmark({
    required SelectedVideo video,
    required int baseVbrBitrate,
    required BenchmarkMode mode,
  });
}

class PlatformCompressionBenchmarkService implements CompressionBenchmarkService {
  static const MethodChannel _channel = MethodChannel(
    'video_preparo_mobile/compression_benchmark',
  );

  @override
  Future<BenchmarkRunResult> runBenchmark({
    required SelectedVideo video,
    required int baseVbrBitrate,
    required BenchmarkMode mode,
  }) async {
    try {
      final data = await _channel.invokeMapMethod<String, Object?>(
        'runBenchmark',
        {
          'uri': video.uri,
          'path': video.localPath,
          'mode': mode.wireValue,
          'baseVbrBitrate': baseVbrBitrate,
          'originalSizeBytes': video.sizeBytes,
        },
      );

      if (data == null) {
        throw const AppError(
          'O benchmark nao retornou resultado.',
          debugMessage: 'runBenchmark returned null.',
        );
      }

      return BenchmarkRunResult.fromMap(data);
    } on PlatformException catch (error) {
      throw AppError(
        _mapError(error),
        debugMessage: '${error.code}: ${error.message}',
      );
    } on AppError {
      rethrow;
    } catch (error) {
      throw AppError(
        'Erro inesperado ao rodar o benchmark.',
        debugMessage: error.toString(),
      );
    }
  }

  String _mapError(PlatformException error) {
    switch (error.code) {
      case 'debug_only':
        return 'Benchmark disponivel apenas em build debug.';
      case 'busy':
        return 'Ja existe um benchmark em andamento.';
      case 'invalid_arguments':
        return 'Parametros invalidos para o benchmark.';
      case 'probe_failed':
        return 'Nao foi possivel ler as informacoes tecnicas do video.';
      case 'storage_failed':
        return 'Nao foi possivel salvar o arquivo do benchmark.';
      case 'compression_failed':
        return 'Falha ao rodar a compressao de benchmark.';
      default:
        return 'Nao foi possivel concluir o benchmark.';
    }
  }
}
