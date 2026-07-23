"""
Verifica que o resultado da compressao soma o tamanho de TODOS os videos
da timeline (nao apenas um), reproduzindo o bug relatado: card final
mostrando o tamanho de um unico video em vez da soma de 4.

Roda sem GUI: instancia VideoCompressorGUI.__new__ (sem __init__) e chama
diretamente os metodos reais _unique_export_source_paths/_sum_file_sizes,
usando arquivos reais gravados em disco (tamanhos medidos, nao inventados).
"""

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ui  # noqa: E402
from editor_state import EditorState  # noqa: E402


def make_bare_gui() -> ui.VideoCompressorGUI:
    """Instancia a classe real sem rodar __init__ (que monta a GUI)."""
    return ui.VideoCompressorGUI.__new__(ui.VideoCompressorGUI)


def write_real_file(path: Path, num_bytes: int) -> int:
    """Grava um arquivo real com `num_bytes` bytes e retorna o tamanho medido em disco."""
    with open(path, "wb") as fh:
        fh.write(os.urandom(num_bytes))
    return os.path.getsize(path)


class ExportSizeSumTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_single_video_uses_its_own_size(self):
        """1 video na timeline: soma deve ser igual ao tamanho desse unico arquivo."""
        video_path = self.tmp_path / "clipe_unico.mp4"
        real_size = write_real_file(video_path, 111_222)

        state = EditorState()
        state.reset(duration=5.0, source_path=str(video_path))

        gui = make_bare_gui()
        gui.input_file = str(video_path)
        gui.processing_segments = state.segments_for_export()

        source_paths = gui._unique_export_source_paths()
        total = gui._sum_file_sizes(source_paths)

        self.assertEqual(source_paths, [str(video_path)])
        self.assertEqual(total, real_size)

    def test_multiple_added_videos_sum_all_sizes(self):
        """4 videos adicionados via 'Adicionar': soma deve ser a soma real dos 4 arquivos,
        reproduzindo o cenario relatado (timeline de 4 videos)."""
        sizes = [307_384_000, 298_112_000, 320_450_000, 303_654_000]
        video_paths = []
        for index, size in enumerate(sizes):
            path = self.tmp_path / f"video_{index}.mp4"
            write_real_file(path, size)
            video_paths.append(path)

        state = EditorState()
        state.reset(duration=10.0, source_path=str(video_paths[0]))
        for path in video_paths[1:]:
            state.add_media_segment(str(path), duration=10.0)

        gui = make_bare_gui()
        gui.input_file = str(video_paths[0])
        gui.processing_segments = state.segments_for_export()

        source_paths = gui._unique_export_source_paths()
        total = gui._sum_file_sizes(source_paths)

        expected_total = sum(os.path.getsize(p) for p in video_paths)

        self.assertEqual(len(source_paths), 4)
        self.assertEqual(total, expected_total)
        # Trava explicitamente o bug relatado: soma nao pode ser o tamanho de 1 video so.
        self.assertNotIn(total, [os.path.getsize(p) for p in video_paths])

    def test_disabled_segment_is_excluded_from_sum(self):
        """Video desabilitado/removido antes de comprimir nao deve entrar na soma."""
        sizes = [200_000_000, 150_000_000, 175_000_000]
        video_paths = []
        for index, size in enumerate(sizes):
            path = self.tmp_path / f"video_{index}.mp4"
            write_real_file(path, size)
            video_paths.append(path)

        state = EditorState()
        state.reset(duration=8.0, source_path=str(video_paths[0]))
        for path in video_paths[1:]:
            state.add_media_segment(str(path), duration=8.0)

        # Desabilita o segundo video (simula desmarcar/remover antes de exportar).
        state.segments[1].enabled = False

        gui = make_bare_gui()
        gui.input_file = str(video_paths[0])
        gui.processing_segments = state.segments_for_export()

        source_paths = gui._unique_export_source_paths()
        total = gui._sum_file_sizes(source_paths)

        expected_total = os.path.getsize(video_paths[0]) + os.path.getsize(video_paths[2])

        self.assertEqual(len(source_paths), 2)
        self.assertEqual(total, expected_total)


if __name__ == "__main__":
    unittest.main()
