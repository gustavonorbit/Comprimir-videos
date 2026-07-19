import 'package:file_picker/file_picker.dart';
import 'package:mime/mime.dart';

import '../core/errors/app_error.dart';
import '../models/selected_video.dart';

abstract class MediaPickerService {
  Future<SelectedVideo?> pickVideo();
}

class FilePickerMediaPickerService implements MediaPickerService {
  @override
  Future<SelectedVideo?> pickVideo() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.video,
        allowMultiple: false,
        withData: false,
        withReadStream: false,
        lockParentWindow: true,
      );

      if (result == null || result.files.isEmpty) {
        return null;
      }

      final file = result.files.single;
      final reference = file.identifier ?? file.path;
      if (reference == null || reference.isEmpty) {
        throw const AppError(
          'Nao foi possivel acessar o video selecionado.',
          debugMessage: 'FilePicker returned no identifier or path.',
        );
      }

      return SelectedVideo(
        uri: reference,
        displayName: file.name,
        mimeType: lookupMimeType(file.name),
        sizeBytes: file.size > 0 ? file.size : null,
        localPath: file.path,
      );
    } on AppError {
      rethrow;
    } catch (error) {
      throw AppError(_mapPickerError(error), debugMessage: error.toString());
    }
  }

  String _mapPickerError(Object error) {
    final text = error.toString().toLowerCase();
    if (text.contains('permission') || text.contains('denied')) {
      return 'Permissao negada. Autorize o acesso ao video e tente novamente.';
    }
    if (text.contains('read') || text.contains('access')) {
      return 'Nao foi possivel acessar o arquivo selecionado.';
    }
    return 'Nao foi possivel abrir o seletor de videos.';
  }
}
