import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_preparo_mobile/core/errors/app_error.dart';
import 'package:video_preparo_mobile/models/compression_result.dart';
import 'package:video_preparo_mobile/models/compression_settings.dart';
import 'package:video_preparo_mobile/models/selected_video.dart';
import 'package:video_preparo_mobile/models/video_processing_progress.dart';
import 'package:video_preparo_mobile/screens/home_screen.dart';
import 'package:video_preparo_mobile/services/media_picker_service.dart';
import 'package:video_preparo_mobile/services/shared_video_service.dart';
import 'package:video_preparo_mobile/services/video_info_service.dart';
import 'package:video_preparo_mobile/services/video_processing_service.dart';

void main() {
  testWidgets('mostra estado inicial sem opcoes extras', (tester) async {
    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(null),
        infoService: _FakeInfoService(),
        processingService: _FakeProcessingService(),
        sharedVideoService: _FakeSharedVideoService(),
      ),
    );

    expect(find.text('Nenhum video selecionado'), findsOneWidget);
    expect(find.text('Selecionar video'), findsOneWidget);
    expect(find.text('Opções extras'), findsNothing);
  });

  testWidgets(
    'mostra resumo, extras recolhidos e botao principal apos selecionar video',
    (tester) async {
      const picked = SelectedVideo(
        uri: 'content://video/1',
        displayName: 'bug.mp4',
        sizeBytes: 1024,
      );
      const withInfo = SelectedVideo(
        uri: 'content://video/1',
        displayName: 'bug.mp4',
        mimeType: 'video/mp4',
        sizeBytes: 1024,
        duration: Duration(seconds: 12),
        width: 1280,
        height: 720,
        rotation: 0,
      );

      await tester.pumpWidget(
        _TestApp(
          picker: _FakePicker(picked),
          infoService: _FakeInfoService(videoWithInfo: withInfo),
          processingService: _FakeProcessingService(),
          sharedVideoService: _FakeSharedVideoService(),
        ),
      );

      await tester.tap(find.text('Selecionar video'));
      await tester.pumpAndSettle();

      expect(find.text('bug.mp4'), findsOneWidget);
      expect(find.text('video/mp4'), findsOneWidget);
      expect(find.text('1280x720'), findsOneWidget);
      expect(find.text('Opções extras'), findsOneWidget);
      expect(find.text('Balanceado'), findsNothing);
      expect(find.text('Automatica'), findsNothing);
      expect(find.text('Comprimir agora'), findsOneWidget);
      expect(find.text('Remover'), findsOneWidget);

      await tester.tap(find.text('Opções extras'));
      await tester.pumpAndSettle();

      expect(find.text('Automatica'), findsOneWidget);
      expect(find.text('Original'), findsNWidgets(2));
      expect(find.text('MP4'), findsOneWidget);
    },
  );

  testWidgets('cancelamento do seletor nao mostra erro', (tester) async {
    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(null),
        infoService: _FakeInfoService(),
        processingService: _FakeProcessingService(),
        sharedVideoService: _FakeSharedVideoService(),
      ),
    );

    await tester.tap(find.text('Selecionar video'));
    await tester.pumpAndSettle();

    expect(find.text('Nenhum video selecionado'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsNothing);
  });

  testWidgets('remove selecao atual', (tester) async {
    const picked = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'demo.mp4',
    );
    const withInfo = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'demo.mp4',
      width: 640,
      height: 360,
    );

    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(picked),
        infoService: _FakeInfoService(videoWithInfo: withInfo),
        processingService: _FakeProcessingService(),
        sharedVideoService: _FakeSharedVideoService(),
      ),
    );

    await tester.tap(find.text('Selecionar video'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Remover'));
    await tester.tap(find.text('Remover'));
    await tester.pumpAndSettle();

    expect(find.text('Nenhum video selecionado'), findsOneWidget);
    expect(find.text('demo.mp4'), findsNothing);
  });

  testWidgets('mostra resultado apos comprimir', (tester) async {
    const picked = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'video.mp4',
      sizeBytes: 2000,
    );
    const result = CompressionResult(
      outputName: 'video_comprimido.mp4',
      outputUri: 'content://output/1',
      outputLocationLabel: 'Movies/Preparo de Videos',
      originalSizeBytes: 2000,
      outputSizeBytes: 1000,
      format: 'MP4',
    );

    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(picked),
        infoService: _FakeInfoService(videoWithInfo: picked),
        processingService: _FakeProcessingService(result: result),
        sharedVideoService: _FakeSharedVideoService(),
      ),
    );

    await tester.tap(find.text('Selecionar video'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Comprimir agora'));
    await tester.tap(find.text('Comprimir agora'));
    await tester.pumpAndSettle();

    expect(find.text('Resultado'), findsOneWidget);
    expect(find.text('video_comprimido.mp4'), findsAtLeastNWidgets(1));
    expect(find.text('50.0%'), findsOneWidget);
    expect(find.text('Compartilhar'), findsOneWidget);
  });

  testWidgets(
    'carrega video recebido por compartilhamento sem iniciar compressao automaticamente',
    (tester) async {
      const shared = SelectedVideo(
        uri: 'content://shared/1',
        displayName: 'compartilhado.mp4',
      );
      const withInfo = SelectedVideo(
        uri: 'content://shared/1',
        displayName: 'compartilhado.mp4',
        mimeType: 'video/mp4',
        sizeBytes: 3000,
        width: 1920,
        height: 1080,
      );

      await tester.pumpWidget(
        _TestApp(
          picker: _FakePicker(null),
          infoService: _FakeInfoService(videoWithInfo: withInfo),
          processingService: _FakeProcessingService(),
          sharedVideoService: _FakeSharedVideoService(initialVideo: shared),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('compartilhado.mp4'), findsOneWidget);
      expect(find.text('Opções extras'), findsOneWidget);
      expect(find.text('Comprimir agora'), findsOneWidget);
      expect(find.text('Progresso'), findsNothing);
      expect(find.text('Resultado'), findsNothing);
    },
  );

  testWidgets('video compartilhado enquanto app esta aberto atualiza a tela', (
    tester,
  ) async {
    const shared = SelectedVideo(
      uri: 'content://shared/2',
      displayName: 'novo.mp4',
    );
    const withInfo = SelectedVideo(
      uri: 'content://shared/2',
      displayName: 'novo.mp4',
      width: 640,
      height: 360,
    );
    final sharedVideoService = _FakeSharedVideoService();

    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(null),
        infoService: _FakeInfoService(videoWithInfo: withInfo),
        processingService: _FakeProcessingService(),
        sharedVideoService: sharedVideoService,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Nenhum video selecionado'), findsOneWidget);

    sharedVideoService.emit(shared);
    await tester.pumpAndSettle();

    expect(find.text('novo.mp4'), findsOneWidget);
  });

  testWidgets('ignora video compartilhado durante compressao em andamento', (
    tester,
  ) async {
    const picked = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'original.mp4',
      sizeBytes: 1000,
    );
    const outro = SelectedVideo(
      uri: 'content://shared/3',
      displayName: 'outro.mp4',
    );
    final gate = Completer<void>();
    final processingService = _FakeProcessingService(gate: gate);
    final sharedVideoService = _FakeSharedVideoService();

    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(picked),
        infoService: _FakeInfoService(videoWithInfo: picked),
        processingService: processingService,
        sharedVideoService: sharedVideoService,
      ),
    );

    await tester.tap(find.text('Selecionar video'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Comprimir agora'));
    await tester.tap(find.text('Comprimir agora'));
    await tester.pump();

    sharedVideoService.emit(outro);
    await tester.pump();

    expect(find.text('original.mp4'), findsOneWidget);
    expect(find.text('outro.mp4'), findsNothing);

    gate.complete();
    await tester.pump();
    await tester.pump();
  });

  testWidgets('mostra progresso determinado com percentual real', (
    tester,
  ) async {
    const picked = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'video.mp4',
      sizeBytes: 2000,
    );
    final gate = Completer<void>();
    final processingService = _FakeProcessingService(
      gate: gate,
      progressEvents: const [
        VideoProcessingProgress(
          stage: VideoProcessingStage.processing,
          percent: 42,
          message: 'Comprimindo video...',
        ),
      ],
    );

    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(picked),
        infoService: _FakeInfoService(videoWithInfo: picked),
        processingService: processingService,
        sharedVideoService: _FakeSharedVideoService(),
      ),
    );

    await tester.tap(find.text('Selecionar video'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Comprimir agora'));
    await tester.tap(find.text('Comprimir agora'));
    await tester.pump();

    final progressBar = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator),
    );
    expect(progressBar.value, closeTo(0.42, 0.0001));
    expect(find.textContaining('42%'), findsOneWidget);
    expect(find.textContaining('Tempo decorrido'), findsNothing);

    gate.complete();
    await tester.pump();
    await tester.pump();
  });

  testWidgets(
    'mostra progresso indeterminado com tempo decorrido quando percentual indisponivel',
    (tester) async {
      const picked = SelectedVideo(
        uri: 'content://video/1',
        displayName: 'video.mp4',
        sizeBytes: 2000,
      );
      final gate = Completer<void>();
      final processingService = _FakeProcessingService(
        gate: gate,
        progressEvents: const [
          VideoProcessingProgress(
            stage: VideoProcessingStage.processing,
            message: 'Comprimindo video...',
          ),
        ],
      );

      await tester.pumpWidget(
        _TestApp(
          picker: _FakePicker(picked),
          infoService: _FakeInfoService(videoWithInfo: picked),
          processingService: processingService,
          sharedVideoService: _FakeSharedVideoService(),
        ),
      );

      await tester.tap(find.text('Selecionar video'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Comprimir agora'));
      await tester.tap(find.text('Comprimir agora'));
      await tester.pump();

      final progressBar = tester.widget<LinearProgressIndicator>(
        find.byType(LinearProgressIndicator),
      );
      expect(progressBar.value, isNull);
      expect(find.textContaining('Tempo decorrido'), findsOneWidget);

      gate.complete();
      await tester.pump();
      await tester.pump();
    },
  );

  testWidgets('mostra aviso quando compartilhar falha', (tester) async {
    const picked = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'video.mp4',
      sizeBytes: 2000,
    );
    const result = CompressionResult(
      outputName: 'video_comprimido.mp4',
      outputUri: 'content://output/1',
      outputLocationLabel: 'Movies/Preparo de Videos',
      originalSizeBytes: 2000,
      outputSizeBytes: 1000,
      format: 'MP4',
    );

    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(picked),
        infoService: _FakeInfoService(videoWithInfo: picked),
        processingService: _FakeProcessingService(
          result: result,
          shareError: const AppError(
            'Nenhum aplicativo compatível foi encontrado.',
          ),
        ),
        sharedVideoService: _FakeSharedVideoService(),
      ),
    );

    await tester.tap(find.text('Selecionar video'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Comprimir agora'));
    await tester.tap(find.text('Comprimir agora'));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Compartilhar'));
    await tester.tap(find.text('Compartilhar'));
    await tester.pump();

    expect(
      find.text('Nenhum aplicativo compatível foi encontrado.'),
      findsOneWidget,
    );
  });

  testWidgets('mostra aviso quando abrir o arquivo falha', (tester) async {
    const picked = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'video.mp4',
      sizeBytes: 2000,
    );
    const result = CompressionResult(
      outputName: 'video_comprimido.mp4',
      outputUri: 'content://output/1',
      outputLocationLabel: 'Movies/Preparo de Videos',
      originalSizeBytes: 2000,
      outputSizeBytes: 1000,
      format: 'MP4',
    );

    await tester.pumpWidget(
      _TestApp(
        picker: _FakePicker(picked),
        infoService: _FakeInfoService(videoWithInfo: picked),
        processingService: _FakeProcessingService(
          result: result,
          openError: const AppError('Não foi possível abrir o vídeo.'),
        ),
        sharedVideoService: _FakeSharedVideoService(),
      ),
    );

    await tester.tap(find.text('Selecionar video'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Comprimir agora'));
    await tester.tap(find.text('Comprimir agora'));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Abrir arquivo'));
    await tester.tap(find.text('Abrir arquivo'));
    await tester.pump();

    expect(find.text('Não foi possível abrir o vídeo.'), findsOneWidget);
  });
}

class _TestApp extends StatelessWidget {
  const _TestApp({
    required this.picker,
    required this.infoService,
    required this.processingService,
    required this.sharedVideoService,
  });

  final MediaPickerService picker;
  final VideoInfoService infoService;
  final VideoProcessingService processingService;
  final SharedVideoService sharedVideoService;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: HomeScreen(
        mediaPickerService: picker,
        videoInfoService: infoService,
        videoProcessingService: processingService,
        sharedVideoService: sharedVideoService,
      ),
    );
  }
}

class _FakePicker implements MediaPickerService {
  const _FakePicker(this.video);

  final SelectedVideo? video;

  @override
  Future<SelectedVideo?> pickVideo() async => video;
}

class _FakeInfoService implements VideoInfoService {
  const _FakeInfoService({this.videoWithInfo});

  final SelectedVideo? videoWithInfo;

  @override
  Future<SelectedVideo> loadInfo(SelectedVideo video) async =>
      videoWithInfo ?? video;
}

class _FakeSharedVideoService implements SharedVideoService {
  _FakeSharedVideoService({this.initialVideo});

  final SelectedVideo? initialVideo;
  final _controller = StreamController<SelectedVideo>.broadcast();

  @override
  Future<SelectedVideo?> consumeInitialSharedVideo() async => initialVideo;

  @override
  Stream<SelectedVideo> get sharedVideoStream => _controller.stream;

  void emit(SelectedVideo video) => _controller.add(video);
}

class _FakeProcessingService implements VideoProcessingService {
  _FakeProcessingService({
    CompressionResult? result,
    List<VideoProcessingProgress>? progressEvents,
    this.gate,
    this.shareError,
    this.openError,
  }) : result =
           result ??
           const CompressionResult(
             outputName: 'video_comprimido.mp4',
             outputUri: 'content://output/1',
             outputLocationLabel: 'Movies/Preparo de Videos',
             originalSizeBytes: 1000,
             outputSizeBytes: 800,
             format: 'MP4',
           ),
       _progressEvents =
           progressEvents ??
           const [
             VideoProcessingProgress(
               stage: VideoProcessingStage.processing,
               percent: 100,
               message: 'Comprimindo video...',
             ),
           ];

  final CompressionResult result;
  final List<VideoProcessingProgress> _progressEvents;

  /// Quando presente, `compressVideo` so resolve apos este Completer ser
  /// concluido pelo teste, permitindo inspecionar o estado "em andamento".
  final Completer<void>? gate;
  final AppError? shareError;
  final AppError? openError;

  final _progressController =
      StreamController<VideoProcessingProgress>.broadcast();

  @override
  Stream<VideoProcessingProgress> get progressStream =>
      _progressController.stream;

  @override
  Future<void> cancelProcessing() async {}

  @override
  Future<CompressionResult> compressVideo({
    required SelectedVideo video,
    required CompressionSettings settings,
  }) async {
    for (final event in _progressEvents) {
      _progressController.add(event);
    }
    if (gate != null) {
      await gate!.future;
    }
    return result;
  }

  @override
  Future<void> openResult(CompressionResult result) async {
    if (openError != null) {
      throw openError!;
    }
  }

  @override
  Future<void> shareResult(CompressionResult result) async {
    if (shareError != null) {
      throw shareError!;
    }
  }
}
