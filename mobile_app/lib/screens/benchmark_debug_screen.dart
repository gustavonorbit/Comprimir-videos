import 'package:flutter/material.dart';

import '../core/errors/app_error.dart';
import '../models/selected_video.dart';
import '../services/compression_benchmark_service.dart';

/// Tela interna de benchmark controlado, acessivel apenas em build debug (ver o gate
/// `kDebugMode` em `app.dart` e o gate `BuildConfig.DEBUG` no lado nativo). Nunca aparece em
/// build release e nunca deve ser exposta como escolha de qualidade para o usuario final: cada
/// um dos 4 modos e disparado manualmente, um de cada vez, e o resultado bruto retornado pelo
/// Android e mostrado sem reinterpretacao (nenhum numero e inventado aqui).
class BenchmarkDebugScreen extends StatefulWidget {
  const BenchmarkDebugScreen({
    required this.video,
    required this.baseVbrBitrate,
    required this.benchmarkService,
    super.key,
  });

  final SelectedVideo video;
  final int baseVbrBitrate;
  final CompressionBenchmarkService benchmarkService;

  @override
  State<BenchmarkDebugScreen> createState() => _BenchmarkDebugScreenState();
}

class _BenchmarkDebugScreenState extends State<BenchmarkDebugScreen> {
  final Map<BenchmarkMode, BenchmarkRunResult> _results = {};
  final Map<BenchmarkMode, String> _errors = {};
  BenchmarkMode? _running;

  Future<void> _runMode(BenchmarkMode mode) async {
    if (_running != null) {
      return;
    }
    setState(() {
      _running = mode;
      _errors.remove(mode);
    });

    try {
      final result = await widget.benchmarkService.runBenchmark(
        video: widget.video,
        baseVbrBitrate: widget.baseVbrBitrate,
        mode: mode,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _results[mode] = result;
        _running = null;
      });
    } on AppError catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errors[mode] = error.userMessage;
        _running = null;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errors[mode] = 'Erro inesperado: $error';
        _running = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Benchmark CQ (debug)')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              'Ferramenta interna. Roda uma compressao completa por modo, com o mesmo video '
              '(${widget.video.displayName}). Nao substitui o pipeline de producao (VBR), que '
              'continua sendo o unico usado fora desta tela.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            for (final mode in BenchmarkMode.values) ...[
              _ModeCard(
                mode: mode,
                isRunning: _running == mode,
                isBusy: _running != null,
                result: _results[mode],
                errorMessage: _errors[mode],
                onRun: () => _runMode(mode),
              ),
              const SizedBox(height: 12),
            ],
          ],
        ),
      ),
    );
  }
}

class _ModeCard extends StatelessWidget {
  const _ModeCard({
    required this.mode,
    required this.isRunning,
    required this.isBusy,
    required this.result,
    required this.errorMessage,
    required this.onRun,
  });

  final BenchmarkMode mode;
  final bool isRunning;
  final bool isBusy;
  final BenchmarkRunResult? result;
  final String? errorMessage;
  final VoidCallback onRun;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    mode.label,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                FilledButton(
                  onPressed: isBusy ? null : onRun,
                  child: isRunning
                      ? const SizedBox.square(
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Rodar'),
                ),
              ],
            ),
            if (errorMessage != null) ...[
              const SizedBox(height: 8),
              Text(
                errorMessage!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ],
            if (result != null) ...[
              const SizedBox(height: 8),
              _ResultTable(result: result!),
            ],
          ],
        ),
      ),
    );
  }
}

class _ResultTable extends StatelessWidget {
  const _ResultTable({required this.result});

  final BenchmarkRunResult result;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final rows = <MapEntry<String, String>>[
      MapEntry('Modo utilizado', result.modoUtilizado ?? 'nao disponivel'),
      MapEntry('Encoder', result.nomeEncoder ?? 'nao identificado'),
      MapEntry('MIME de saida', result.mimeSaida),
      MapEntry(
        'Suporte declarado a CQ',
        _boolLabel(result.suporteDeclaradoCq),
      ),
      MapEntry(
        'Faixa de qualidade (qualityRange)',
        result.qualityRangeMin != null && result.qualityRangeMax != null
            ? '${result.qualityRangeMin}-${result.qualityRangeMax}'
            : 'nao disponivel',
      ),
      MapEntry(
        'Qualidade solicitada',
        result.qualidadeSolicitada?.toString() ?? 'nao aplicavel (VBR)',
      ),
      MapEntry(
        'Qualidade efetiva',
        result.qualidadeEfetiva?.toString() ??
            'nao identificavel (sem API publica)',
      ),
      MapEntry('Fallback executado', _boolLabel(result.fallbackExecutado)),
      MapEntry(
        'Tamanho original',
        '${result.tamanhoOriginalBytes} bytes',
      ),
      MapEntry(
        'Tamanho final',
        result.tamanhoFinalBytes != null
            ? '${result.tamanhoFinalBytes} bytes'
            : 'nao disponivel',
      ),
      MapEntry(
        'Reducao',
        result.percentualReducao != null
            ? '${result.percentualReducao!.toStringAsFixed(1)}%'
            : 'nao disponivel',
      ),
      MapEntry(
        'Duracao do video',
        result.duracaoVideoMs != null
            ? '${(result.duracaoVideoMs! / 1000).toStringAsFixed(1)}s'
            : 'nao disponivel',
      ),
      MapEntry(
        'Tempo de processamento',
        result.tempoProcessamentoMs != null
            ? '${(result.tempoProcessamentoMs! / 1000).toStringAsFixed(1)}s'
            : 'nao disponivel',
      ),
      MapEntry('Resolucao', result.resolucao ?? 'nao disponivel'),
      MapEntry('FPS', result.fps?.toStringAsFixed(1) ?? 'nao disponivel'),
      MapEntry(
        'Bitrate medio final',
        result.bitrateMedioFinalBps != null
            ? '${(result.bitrateMedioFinalBps! / 1000).round()} kbps'
            : 'nao disponivel',
      ),
      MapEntry('Sucesso', _boolLabel(result.sucesso)),
      if (result.mensagemErro != null)
        MapEntry('Mensagem tecnica', result.mensagemErro!),
      if (result.notaTecnica != null)
        MapEntry('Nota tecnica', result.notaTecnica!),
      if (result.outputName != null)
        MapEntry('Arquivo salvo', result.outputName!),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: rows
          .map(
            (entry) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: RichText(
                text: TextSpan(
                  style: theme.textTheme.bodySmall,
                  children: [
                    TextSpan(
                      text: '${entry.key}: ',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    TextSpan(text: entry.value),
                  ],
                ),
              ),
            ),
          )
          .toList(),
    );
  }

  String _boolLabel(bool? value) {
    if (value == null) return 'nao disponivel';
    return value ? 'sim' : 'nao';
  }
}
