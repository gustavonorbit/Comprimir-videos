import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/errors/app_error.dart';
import '../core/utils/formatters.dart';
import '../models/compression_result.dart';
import '../models/compression_settings.dart';
import '../models/selected_video.dart';
import '../models/video_processing_progress.dart';
import '../services/automatic_compression_strategy.dart';
import '../services/compression_benchmark_service.dart';
import '../services/media_picker_service.dart';
import '../services/shared_video_service.dart';
import '../services/video_info_service.dart';
import '../services/video_processing_service.dart';
import '../widgets/selected_video_card.dart';
import 'benchmark_debug_screen.dart';

enum HomeFlowStatus {
  initial,
  selecting,
  ready,
  processing,
  cancelling,
  completed,
  error,
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    required this.mediaPickerService,
    required this.videoInfoService,
    required this.videoProcessingService,
    required this.sharedVideoService,
    this.benchmarkService,
    super.key,
  });

  final MediaPickerService mediaPickerService;
  final VideoInfoService videoInfoService;
  final VideoProcessingService videoProcessingService;
  final SharedVideoService sharedVideoService;
  // Ferramenta interna de benchmark CQ (debug-only). So e passado quando kDebugMode e verdade
  // (ver app.dart); em release chega como null e nenhum ponto de entrada e exibido.
  final CompressionBenchmarkService? benchmarkService;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  HomeFlowStatus _status = HomeFlowStatus.initial;
  SelectedVideo? _selectedVideo;
  CompressionResult? _compressionResult;
  VideoProcessingProgress? _progress;
  String? _errorMessage;
  StreamSubscription<VideoProcessingProgress>? _progressSubscription;
  StreamSubscription<SelectedVideo>? _sharedVideoSubscription;
  Timer? _elapsedTimer;
  int _elapsedSeconds = 0;

  final AutomaticCompressionStrategy _compressionStrategy =
      const AutomaticCompressionStrategy();

  bool get _isBusy =>
      _status == HomeFlowStatus.selecting ||
      _status == HomeFlowStatus.processing ||
      _status == HomeFlowStatus.cancelling;

  @override
  void initState() {
    super.initState();
    _progressSubscription = widget.videoProcessingService.progressStream.listen(
      (progress) {
        if (!mounted) {
          return;
        }
        setState(() {
          _progress = progress;
        });
      },
    );
    _sharedVideoSubscription = widget.sharedVideoService.sharedVideoStream
        .listen(_handleSharedVideo);
    unawaited(_checkInitialSharedVideo());
  }

  @override
  void dispose() {
    _progressSubscription?.cancel();
    _sharedVideoSubscription?.cancel();
    _elapsedTimer?.cancel();
    super.dispose();
  }

  Future<void> _checkInitialSharedVideo() async {
    final shared = await widget.sharedVideoService.consumeInitialSharedVideo();
    if (shared == null || !mounted) {
      return;
    }
    _handleSharedVideo(shared);
  }

  void _handleSharedVideo(SelectedVideo video) {
    // Um video compartilhado enquanto uma compressao esta em andamento nao
    // interrompe o fluxo atual; o usuario pode compartilhar de novo depois.
    if (_isBusy) {
      return;
    }
    unawaited(_loadVideo(video));
  }

  Future<void> _selectVideo() async {
    if (_isBusy) {
      return;
    }

    setState(() {
      _status = HomeFlowStatus.selecting;
      _errorMessage = null;
      _compressionResult = null;
      _progress = null;
    });

    try {
      final pickedVideo = await widget.mediaPickerService.pickVideo();
      if (!mounted) {
        return;
      }

      if (pickedVideo == null) {
        setState(() {
          _status = _selectedVideo == null
              ? HomeFlowStatus.initial
              : HomeFlowStatus.ready;
        });
        return;
      }

      await _loadVideo(pickedVideo);
    } on AppError catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = error.userMessage;
        _status = HomeFlowStatus.error;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = 'Erro inesperado ao selecionar o video.';
        _status = HomeFlowStatus.error;
      });
    }
  }

  /// Carrega os metadados de um video e o coloca pronto para compressao.
  /// Usado tanto pelo seletor de arquivos quanto por um video recebido via
  /// compartilhamento (ACTION_SEND), para que os dois fluxos convirjam para o
  /// mesmo comportamento. Nunca inicia a compressao automaticamente.
  Future<void> _loadVideo(SelectedVideo raw) async {
    setState(() {
      _status = HomeFlowStatus.selecting;
      _errorMessage = null;
      _compressionResult = null;
      _progress = null;
    });

    try {
      final videoWithInfo = await widget.videoInfoService.loadInfo(raw);
      if (!mounted) {
        return;
      }

      setState(() {
        _selectedVideo = videoWithInfo;
        _status = HomeFlowStatus.ready;
      });
    } on AppError catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = error.userMessage;
        _status = HomeFlowStatus.error;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = 'Erro inesperado ao selecionar o video.';
        _status = HomeFlowStatus.error;
      });
    }
  }

  Future<void> _compressVideo() async {
    final video = _selectedVideo;
    if (video == null || _isBusy) {
      return;
    }

    unawaited(HapticFeedback.mediumImpact());
    _startElapsedTimer();

    setState(() {
      _status = HomeFlowStatus.processing;
      _errorMessage = null;
      _compressionResult = null;
      _progress = const VideoProcessingProgress(
        stage: VideoProcessingStage.preparing,
        message: 'Preparando video...',
      );
    });

    try {
      final result = await widget.videoProcessingService.compressVideo(
        video: video,
        settings: _compressionStrategy.buildMaximumCompressionSettings(video),
      );
      if (!mounted) {
        return;
      }

      _stopElapsedTimer();
      unawaited(HapticFeedback.lightImpact());
      setState(() {
        _compressionResult = result;
        _status = HomeFlowStatus.completed;
        _progress = const VideoProcessingProgress(
          stage: VideoProcessingStage.completed,
          percent: 100,
          message: 'Compressao concluida.',
        );
      });
    } on AppError catch (error) {
      _stopElapsedTimer();
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = error.userMessage;
        _status = error.userMessage == 'Compressao cancelada.'
            ? HomeFlowStatus.ready
            : HomeFlowStatus.error;
      });
    } catch (_) {
      _stopElapsedTimer();
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = 'Erro inesperado ao comprimir o video.';
        _status = HomeFlowStatus.error;
      });
    }
  }

  Future<void> _cancelCompression() async {
    if (_status != HomeFlowStatus.processing) {
      return;
    }

    setState(() {
      _status = HomeFlowStatus.cancelling;
      _progress = const VideoProcessingProgress(
        stage: VideoProcessingStage.cancelled,
        message: 'Cancelando...',
      );
    });

    try {
      await widget.videoProcessingService.cancelProcessing();
    } finally {
      _stopElapsedTimer();
      if (mounted) {
        setState(() {
          _status = HomeFlowStatus.ready;
          _progress = null;
        });
      }
    }
  }

  void _startElapsedTimer() {
    _elapsedTimer?.cancel();
    _elapsedSeconds = 0;
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) {
        _elapsedTimer?.cancel();
        return;
      }
      setState(() {
        _elapsedSeconds += 1;
      });
    });
  }

  void _stopElapsedTimer() {
    _elapsedTimer?.cancel();
    _elapsedTimer = null;
  }

  void _clearSelection() {
    if (_isBusy) {
      return;
    }
    setState(() {
      _selectedVideo = null;
      _compressionResult = null;
      _progress = null;
      _errorMessage = null;
      _status = HomeFlowStatus.initial;
    });
  }

  Future<void> _shareResult() async {
    final result = _compressionResult;
    if (result == null) {
      return;
    }
    try {
      await widget.videoProcessingService.shareResult(result);
    } on AppError catch (error) {
      _showSnackBar(error.userMessage);
    } catch (_) {
      _showSnackBar('Não foi possível compartilhar o vídeo.');
    }
  }

  Future<void> _openResult() async {
    final result = _compressionResult;
    if (result == null) {
      return;
    }
    try {
      await widget.videoProcessingService.openResult(result);
    } on AppError catch (error) {
      _showSnackBar(error.userMessage);
    } catch (_) {
      _showSnackBar('Não foi possível abrir o vídeo.');
    }
  }

  void _openBenchmark(CompressionSettings settings) {
    final video = _selectedVideo;
    final benchmarkService = widget.benchmarkService;
    if (video == null || benchmarkService == null || _isBusy) {
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => BenchmarkDebugScreen(
          video: video,
          baseVbrBitrate: settings.videoBitrate,
          benchmarkService: benchmarkService,
        ),
      ),
    );
  }

  void _showSnackBar(String message) {
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final selectedVideo = _selectedVideo;
    final settings = selectedVideo == null
        ? null
        : _compressionStrategy.buildMaximumCompressionSettings(selectedVideo);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Preparo de Videos'),
        centerTitle: false,
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final maxWidth = constraints.maxWidth >= 720
                ? 680.0
                : double.infinity;

            return SingleChildScrollView(
              padding: EdgeInsets.symmetric(
                horizontal: constraints.maxWidth >= 720 ? 28 : 18,
                vertical: 20,
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: maxWidth),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _Header(status: _status),
                      const SizedBox(height: 20),
                      FilledButton.icon(
                        onPressed: _isBusy ? null : _selectVideo,
                        icon: _status == HomeFlowStatus.selecting
                            ? const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.video_file_outlined),
                        label: Text(
                          _selectedVideo == null
                              ? 'Selecionar video'
                              : 'Trocar video',
                        ),
                      ),
                      const SizedBox(height: 16),
                      if (_errorMessage != null) ...[
                        _ErrorBanner(message: _errorMessage!),
                        const SizedBox(height: 16),
                      ],
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 240),
                        switchInCurve: Curves.easeOutCubic,
                        switchOutCurve: Curves.easeInCubic,
                        child: selectedVideo == null || settings == null
                            ? const _EmptyState()
                            : Column(
                                key: ValueKey(selectedVideo.uri),
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  SelectedVideoCard(
                                    video: selectedVideo,
                                    onClear: _isBusy ? null : _clearSelection,
                                    onReplace: _isBusy ? null : _selectVideo,
                                  ),
                                  const SizedBox(height: 14),
                                  _ExtraOptionsCard(
                                    settings: settings,
                                    outputName: settings.outputFileNameFor(
                                      selectedVideo,
                                    ),
                                  ),
                                  if (kDebugMode &&
                                      widget.benchmarkService != null) ...[
                                    const SizedBox(height: 10),
                                    Align(
                                      alignment: Alignment.centerLeft,
                                      child: TextButton.icon(
                                        onPressed: _isBusy
                                            ? null
                                            : () => _openBenchmark(settings),
                                        icon: const Icon(Icons.science_outlined),
                                        label: const Text('Benchmark CQ (debug)'),
                                      ),
                                    ),
                                  ],
                                  const SizedBox(height: 18),
                                  if (_status == HomeFlowStatus.processing ||
                                      _status == HomeFlowStatus.cancelling) ...[
                                    _ProgressCard(
                                      progress: _progress,
                                      isCancelling:
                                          _status == HomeFlowStatus.cancelling,
                                      onCancel: _cancelCompression,
                                      elapsedSeconds: _elapsedSeconds,
                                    ),
                                    const SizedBox(height: 18),
                                  ],
                                  FilledButton.icon(
                                    onPressed: _isBusy ? null : _compressVideo,
                                    icon: const Icon(Icons.compress),
                                    label: const Text('Comprimir agora'),
                                  ),
                                  if (_compressionResult != null) ...[
                                    const SizedBox(height: 18),
                                    _ResultCard(
                                      result: _compressionResult!,
                                      onShare: _shareResult,
                                      onOpen: _openResult,
                                      onCompressAnother: _clearSelection,
                                    ),
                                  ],
                                ],
                              ),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'O video original nunca e alterado.',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.status});

  final HomeFlowStatus status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Comprima videos sem complicacao.',
          style: theme.textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          status == HomeFlowStatus.initial
              ? 'Selecione um video para ver as informacoes e preparar a compressao.'
              : 'Toque em Comprimir agora para gerar uma copia MP4 menor automaticamente.',
          style: theme.textTheme.bodyLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 0,
      color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.48),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Icon(
              Icons.movie_creation_outlined,
              size: 52,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(height: 12),
            Text(
              'Nenhum video selecionado',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'O app vai ler os dados do arquivo antes de qualquer processamento.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ExtraOptionsCard extends StatelessWidget {
  const _ExtraOptionsCard({required this.settings, required this.outputName});

  final CompressionSettings settings;
  final String outputName;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 0,
      child: Theme(
        data: theme.copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 16),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          title: Text(
            'Opções extras',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          subtitle: const Text('Destino e formato da copia final'),
          children: [
            _OptionRow(label: 'Compressao', value: 'Automatica'),
            _OptionRow(label: 'Resolucao', value: settings.resolutionPolicy),
            _OptionRow(label: 'Orientacao', value: settings.rotationPolicy),
            _OptionRow(
              label: 'Audio',
              value: settings.keepAudio ? 'Manter audio' : 'Sem audio',
            ),
            _OptionRow(label: 'Arquivo', value: outputName),
            const _OptionRow(label: 'Formato', value: 'MP4'),
            const _OptionRow(
              label: 'Destino',
              value: 'Movies/Preparo de Videos quando permitido',
            ),
          ],
        ),
      ),
    );
  }
}

class _ProgressCard extends StatelessWidget {
  const _ProgressCard({
    required this.progress,
    required this.isCancelling,
    required this.onCancel,
    required this.elapsedSeconds,
  });

  final VideoProcessingProgress? progress;
  final bool isCancelling;
  final VoidCallback onCancel;
  final int elapsedSeconds;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percent = progress?.percent;
    // Quando o Media3 nao fornece percentual real, o indicador fica
    // indeterminado de verdade: nao inventamos um numero a partir da duracao.
    final message = progress?.message ?? 'Comprimindo video...';

    return _SectionCard(
      title: 'Progresso',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (percent == null)
            const LinearProgressIndicator()
          else
            LinearProgressIndicator(value: percent / 100),
          const SizedBox(height: 10),
          Text(
            percent == null ? message : '$message $percent%',
            style: theme.textTheme.bodyMedium,
          ),
          if (percent == null) ...[
            const SizedBox(height: 4),
            Text(
              'Tempo decorrido: ${_formatElapsed(elapsedSeconds)}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: isCancelling ? null : onCancel,
            icon: const Icon(Icons.stop_circle_outlined),
            label: Text(isCancelling ? 'Cancelando...' : 'Cancelar'),
          ),
        ],
      ),
    );
  }

  String _formatElapsed(int totalSeconds) {
    final minutes = totalSeconds ~/ 60;
    final seconds = totalSeconds % 60;
    if (minutes > 0) {
      return '${minutes}min ${seconds.toString().padLeft(2, '0')}s';
    }
    return '${seconds}s';
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({
    required this.result,
    required this.onShare,
    required this.onOpen,
    required this.onCompressAnother,
  });

  final CompressionResult result;
  final VoidCallback onShare;
  final VoidCallback onOpen;
  final VoidCallback onCompressAnother;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return _SectionCard(
      title: 'Resultado',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 14),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: theme.colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Column(
              children: [
                Text(
                  '${result.savingsPercent.toStringAsFixed(1)}%',
                  style: theme.textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'menor que o original',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _OptionRow(
            label: 'Original',
            value: formatBytes(result.originalSizeBytes),
          ),
          _OptionRow(
            label: 'Final',
            value: formatBytes(result.outputSizeBytes),
          ),
          _OptionRow(label: 'Arquivo', value: result.outputName),
          _OptionRow(label: 'Formato', value: result.format),
          _OptionRow(label: 'Local', value: result.outputLocationLabel),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              FilledButton.icon(
                onPressed: onShare,
                icon: const Icon(Icons.ios_share),
                label: const Text('Compartilhar'),
              ),
              OutlinedButton.icon(
                onPressed: onOpen,
                icon: const Icon(Icons.play_circle_outline),
                label: const Text('Abrir arquivo'),
              ),
              TextButton.icon(
                onPressed: onCompressAnother,
                icon: const Icon(Icons.add),
                label: const Text('Comprimir outro video'),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Resultado salvo como uma copia. O original foi preservado.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 0,
      color: theme.colorScheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.55),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

class _OptionRow extends StatelessWidget {
  const _OptionRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 98,
            child: Text(
              label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              value,
              style: theme.textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline, color: theme.colorScheme.onErrorContainer),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onErrorContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
