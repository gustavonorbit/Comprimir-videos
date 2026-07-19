import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'services/compression_benchmark_service.dart';
import 'services/media_picker_service.dart';
import 'services/shared_video_service.dart';
import 'services/video_processing_service.dart';
import 'services/video_info_service.dart';

class VideoPreparoApp extends StatelessWidget {
  const VideoPreparoApp({super.key});

  @override
  Widget build(BuildContext context) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF0D7A5F),
      brightness: Brightness.light,
    );

    return MaterialApp(
      title: 'Preparo de Videos',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.system,
      theme: ThemeData(
        colorScheme: colorScheme,
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF7F8FA),
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF16A085),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: HomeScreen(
        mediaPickerService: FilePickerMediaPickerService(),
        videoInfoService: PlatformVideoInfoService(),
        videoProcessingService: PlatformVideoProcessingService(),
        sharedVideoService: PlatformSharedVideoService(),
        // Ferramenta interna de benchmark CQ: so existe em build debug. Em release,
        // kDebugMode e eliminado em tempo de compilacao e este servico nunca e instanciado,
        // entao o botao correspondente na tela nunca aparece.
        benchmarkService: kDebugMode
            ? PlatformCompressionBenchmarkService()
            : null,
      ),
    );
  }
}
