"""
Cobre a blindagem de erros do pipeline de compressao:

1. Quando o ffmpeg falha de verdade (ex.: pasta de saida inexistente), a
   mensagem devolvida por `compress_video` precisa expor a causa real (nunca
   vazia, nunca so o banner "ffmpeg version ..."), com e sem progress_callback.
2. Um blur temporal com regiao fora do quadro deve ser descartado e logado
   via `logging`, sem quebrar a exportacao dos demais vidros/segmentos.

Usa um .mp4 real gerado pelo proprio ffmpeg do sistema (testsrc + sine), nunca
valores/erros inventados.
"""

import os
import sys
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compressor import VideoCompressor  # noqa: E402
from editor_state import BlurFilter  # noqa: E402
from blur_state import NormalizedRect  # noqa: E402


class FfmpegErrorSurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = TemporaryDirectory()
        cls.tmp_path = Path(cls._tmp.name)
        cls.compressor = VideoCompressor()

        if not cls.compressor.is_ffmpeg_available():
            raise unittest.SkipTest("ffmpeg não está disponível neste ambiente.")

        cls.real_video = str(cls.tmp_path / "fixture_real.mp4")
        cls._generate_real_video(cls.compressor.ffmpeg_path, cls.real_video)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @staticmethod
    def _generate_real_video(ffmpeg_path: str, output_path: str, duration: float = 2.0):
        """Gera um .mp4 real (testsrc + sine) usando o ffmpeg do proprio projeto."""
        import subprocess

        cmd = [
            ffmpeg_path, "-y",
            "-f", "lavfi", "-i", f"testsrc=size=640x360:duration={duration}:rate=25",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"Não foi possível gerar o vídeo de teste: {result.stderr}")

    def _progress_calls(self):
        calls = []
        return calls, calls.append

    # ---- Bloco 1.2/1.3: stderr real precisa aparecer na mensagem de erro ----

    def test_real_ffmpeg_failure_surfaces_real_message_without_progress_callback(self):
        output_dir = self.tmp_path / "pasta_inexistente_sem_callback"
        output_file = str(output_dir / "saida.mp4")  # diretório não existe de propósito

        success, message = self.compressor.compress_video(
            self.real_video,
            output_file,
            profile="Balanceado",
            progress_callback=None,
        )

        self.assertFalse(success)
        self.assertTrue(message.strip())
        self.assertFalse(message.lower().startswith("erro ao comprimir: ffmpeg version"))
        self.assertNotIn("ffmpeg version", message.lower())
        self.assertTrue(
            any(token in message for token in ("No such file", "Error opening", "no such file")),
            f"mensagem não contém a causa real do erro: {message!r}",
        )

    def test_real_ffmpeg_failure_surfaces_real_message_with_progress_callback(self):
        output_dir = self.tmp_path / "pasta_inexistente_com_callback"
        output_file = str(output_dir / "saida.mp4")

        progress_values, progress_callback = self._progress_calls()

        success, message = self.compressor.compress_video(
            self.real_video,
            output_file,
            profile="Balanceado",
            progress_callback=progress_callback,
        )

        self.assertFalse(success)
        self.assertTrue(message.strip(), "mensagem de erro ficou vazia (stderr drenado duas vezes?)")
        self.assertFalse(message.lower().startswith("erro ao comprimir: ffmpeg version"))
        self.assertNotIn("ffmpeg version", message.lower())
        self.assertTrue(
            any(token in message for token in ("No such file", "Error opening", "no such file")),
            f"mensagem não contém a causa real do erro: {message!r}",
        )

    def test_successful_compression_still_works_with_progress_callback(self):
        """Garante que a correção do stderr não quebrou o caminho de sucesso."""
        output_file = str(self.tmp_path / "saida_sucesso.mp4")
        progress_values, progress_callback = self._progress_calls()

        success, message = self.compressor.compress_video(
            self.real_video,
            output_file,
            profile="Compressão Máxima",
            progress_callback=progress_callback,
        )

        self.assertTrue(success, message)
        self.assertTrue(os.path.exists(output_file))
        self.assertIn("sucesso", message.lower())

    # ---- Bloco 1.4: blur fora do quadro é descartado e logado ----

    def test_out_of_frame_blur_is_discarded_and_logged_without_breaking_export(self):
        output_file = str(self.tmp_path / "saida_blur_invalido.mp4")

        real_info = self.compressor.get_video_info(self.real_video)
        self.assertIsNotNone(real_info)

        # Simula get_video_info devolvendo dimensões de EXIBIÇÃO divergentes das
        # armazenadas (como aconteceria com metadata de rotação 90/270), para
        # comprovar que o descarte usa as dimensões reais passadas ao validador,
        # não um valor presumido pela UI.
        mismatched_info = dict(real_info)
        mismatched_info["width"], mismatched_info["height"] = real_info["height"], real_info["width"]

        original_get_video_info = self.compressor.get_video_info

        def fake_get_video_info(path):
            if path == self.real_video:
                return mismatched_info
            return original_get_video_info(path)

        self.compressor.get_video_info = fake_get_video_info
        try:
            invalid_blur = BlurFilter(
                id="blur-fora-do-quadro",
                type="blur",
                name="fora-do-quadro",
                start_time=0.0,
                end_time=real_info["duration"],
                region=NormalizedRect(1.5, 1.5, 0.2, 0.2),  # totalmente fora de [0,1]
                intensity=0.8,
            )

            with self.assertLogs("compressor", level="WARNING") as logs:
                success, message = self.compressor.compress_video(
                    self.real_video,
                    output_file,
                    profile="Balanceado",
                    temporal_blurs=[invalid_blur],
                )
        finally:
            self.compressor.get_video_info = original_get_video_info

        self.assertTrue(success, message)
        self.assertTrue(os.path.exists(output_file))
        self.assertTrue(
            any("fora do quadro" in record.message.lower() or "ignorado" in record.message.lower()
                for record in logs.records),
            f"nenhum log de descarte do blur inválido foi emitido: {[r.message for r in logs.records]}",
        )


    # ---- Bloco 3.c: cancel_compression drena e loga o stderr parcial ----

    def test_cancel_compression_drains_and_logs_partial_stderr(self):
        heavy_video = str(self.tmp_path / "fixture_heavy.mp4")
        self._generate_real_video(self.compressor.ffmpeg_path, heavy_video, duration=12.0)

        result = {}

        def run_compression():
            success, message = self.compressor.compress_video(
                heavy_video,
                str(self.tmp_path / "saida_cancelada.mp4"),
                profile="Alta Qualidade",  # preset "slow": dá tempo de cancelar antes de terminar
                progress_callback=lambda _pct: None,
            )
            result["success"] = success
            result["message"] = message

        worker = threading.Thread(target=run_compression, daemon=True)
        with self.assertLogs("compressor", level="WARNING") as logs:
            worker.start()
            # Espera o processo ffmpeg realmente começar antes de cancelar.
            for _ in range(50):
                if self.compressor.is_running and self.compressor.process is not None:
                    break
                time.sleep(0.05)
            self.compressor.cancel_compression()
            worker.join(timeout=15)

        self.assertFalse(worker.is_alive(), "compress_video não retornou após o cancelamento")
        self.assertFalse(result.get("success"))
        self.assertIn("cancelad", result.get("message", "").lower())
        self.assertTrue(
            any("cancel" in record.message.lower() for record in logs.records),
            f"cancelamento não foi logado: {[r.message for r in logs.records]}",
        )


if __name__ == "__main__":
    unittest.main()
