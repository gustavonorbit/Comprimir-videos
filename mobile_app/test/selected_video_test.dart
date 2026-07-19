import 'package:flutter_test/flutter_test.dart';
import 'package:video_preparo_mobile/models/selected_video.dart';

void main() {
  test('cria modelo SelectedVideo com dados basicos', () {
    const video = SelectedVideo(
      uri: 'content://video/1',
      displayName: 'evidencia.mp4',
      mimeType: 'video/mp4',
      sizeBytes: 2048,
      duration: Duration(seconds: 10),
      width: 1920,
      height: 1080,
      rotation: 0,
    );

    expect(video.uri, 'content://video/1');
    expect(video.extension, 'MP4');
    expect(video.friendlyResolution, '1920x1080');
  });

  test('nao inventa extensao ou resolucao ausente', () {
    const video = SelectedVideo(
      uri: 'content://video/2',
      displayName: 'arquivo_sem_extensao',
    );

    expect(video.extension, 'Nao informado');
    expect(video.friendlyResolution, 'Nao informada');
  });
}
