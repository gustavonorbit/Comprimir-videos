"""
Bloco 2 (hipótese de rotação, a única não confirmada por leitura de código):
verifica, com um vídeo REAL contendo rotação de metadados por display matrix
(como um celular grava), se o crop de blur calculado a partir das dimensões de
EXIBIÇÃO (retornadas por `VideoCompressor.get_video_info`) escapa do quadro
que o ffmpeg realmente decodifica ao rodar o pipeline completo (cortes +
concat + blur) de `compress_video`.

Achado (reproduzido e documentado abaixo, não é suposição):
O ffmpeg (testado com a build "desktop/bin/ffmpeg", versão 8.1) aplica
auto-rotação por padrão a qualquer stream de entrada com rotação de display
matrix — tanto quando ele é referenciado por `-vf` quanto por
`-filter_complex` usando `[0:v]` diretamente. Ou seja, todo filtro (crop,
overlay, concat) já recebe o frame na orientação de EXIBIÇÃO, com
largura/altura já trocadas quando a rotação é 90°/270°. Isso é exatamente o
que `get_video_info` retorna como `width`/`height` (ver `_display_rotation`
em compressor.py). Não foi reproduzido nenhum escape de quadro nem erro do
tipo "Invalid too big or non positive size for width or height": este teste
existe como regressão, para o caso de uma futura versão do ffmpeg (ou de um
`-noautorotate` acidental) mudar esse comportamento padrão.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compressor import VideoCompressor  # noqa: E402
from editor_state import BlurFilter, EditorState  # noqa: E402
from blur_state import NormalizedRect  # noqa: E402


class RealDisplayMatrixRotationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = TemporaryDirectory()
        cls.tmp_path = Path(cls._tmp.name)
        cls.compressor = VideoCompressor()

        if not cls.compressor.is_ffmpeg_available():
            raise unittest.SkipTest("ffmpeg não está disponível neste ambiente.")

        cls.rotated_video = str(cls.tmp_path / "rotacionado_real.mp4")
        cls._generate_rotated_video(cls.compressor.ffmpeg_path, cls.rotated_video)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @staticmethod
    def _generate_rotated_video(ffmpeg_path: str, output_path: str, duration: float = 3.0):
        """Gera um .mp4 real com rotação de display matrix genuína (pixels
        armazenados em paisagem, container marcado para exibir em retrato),
        replicando o que um vídeo de celular tem: primeiro codifica um vídeo
        plano, depois remuxa com `-display_rotation 90 -c copy` (sem
        recodificar) para anexar a matriz de rotação real ao container."""
        plain_path = str(Path(output_path).with_name("plain_source.mp4"))

        encode_cmd = [
            ffmpeg_path, "-y",
            "-f", "lavfi", "-i", f"testsrc=size=1280x720:duration={duration}:rate=25",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            plain_path,
        ]
        result = subprocess.run(encode_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not os.path.exists(plain_path):
            raise RuntimeError(f"Não foi possível gerar o vídeo base: {result.stderr}")

        remux_cmd = [
            ffmpeg_path, "-y",
            "-display_rotation", "90",
            "-i", plain_path,
            "-c", "copy",
            output_path,
        ]
        result = subprocess.run(remux_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"Não foi possível remuxar com rotação real: {result.stderr}")

    def test_get_video_info_reports_swapped_display_dimensions(self):
        """Pré-condição do teste: o vídeo precisa ter rotação REAL divergente
        entre dimensões armazenadas e de exibição (senão o teste não prova
        nada sobre a hipótese de rotação)."""
        info = self.compressor.get_video_info(self.rotated_video)
        self.assertIsNotNone(info)
        self.assertEqual(info["display_rotation"], 90)
        self.assertEqual((info["stored_width"], info["stored_height"]), (1280, 720))
        self.assertEqual((info["width"], info["height"]), (720, 1280))

    def test_real_pipeline_with_cuts_and_edge_blur_does_not_escape_frame(self):
        """Roda o pipeline real (segmentado + blur perto da borda) num vídeo
        com rotação genuína e confirma que o ffmpeg não rejeita o crop
        (o que aconteceria com 'Invalid too big or non positive size for
        width or height' se as dimensões usadas para o crop não
        correspondessem ao frame realmente decodificado)."""
        output_file = str(self.tmp_path / "saida_rotacionada.mp4")
        info = self.compressor.get_video_info(self.rotated_video)

        state = EditorState()
        state.reset(duration=info["duration"], source_path=self.rotated_video)
        # Corta a timeline em dois segmentos para forçar o caminho
        # segmentado/concat (`_build_segmented_command`), não só o `-vf` simples.
        first = state.segments[0]
        first.timeline_end = 1.2
        first.source_end = 1.2
        state.add_media_segment(self.rotated_video, duration=info["duration"] - 1.5)
        second = state.segments[1]
        second.source_start = 1.5
        second.source_end = info["duration"]
        second.timeline_start = 1.2
        second.timeline_end = 1.2 + (info["duration"] - 1.5)

        # Blur encostado no canto inferior direito do quadro EXIBIDO (720x1280):
        # é a região mais provável de escapar do quadro armazenado (1280x720)
        # caso as dimensões usadas pelo crop estivessem trocadas/erradas.
        edge_blur = BlurFilter(
            id="blur-borda",
            type="blur",
            name="privacy",
            start_time=0.0,
            end_time=info["duration"],
            region=NormalizedRect(0.82, 0.82, 0.18, 0.18),
            intensity=0.9,
        )
        state.filters.append(edge_blur)

        segments = state.segments_for_export()
        temporal_blurs = state.blur_filters_for_export()
        self.assertEqual(len(segments), 2)
        self.assertEqual(len(temporal_blurs), 1)

        success, message = self.compressor.compress_video(
            self.rotated_video,
            output_file,
            profile="Balanceado",
            temporal_blurs=temporal_blurs,
            segments=segments,
        )

        self.assertTrue(success, f"pipeline com vídeo rotacionado falhou: {message}")
        self.assertNotIn("Invalid too big", message)
        self.assertTrue(os.path.exists(output_file))

        # Confere que a saída ficou na orientação de EXIBIÇÃO (retrato),
        # coerente com o que get_video_info reportou para a entrada.
        probe = subprocess.run(
            [self.compressor.ffprobe_path, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", output_file],
            capture_output=True, text=True, timeout=10,
        )
        width_str, height_str = probe.stdout.strip().split(",")
        output_width, output_height = int(width_str), int(height_str)
        self.assertLess(output_width, output_height, "saída deveria continuar em retrato (720x1280-ish)")


if __name__ == "__main__":
    unittest.main()
