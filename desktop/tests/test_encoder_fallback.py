"""Integração real: quando o encoder de hardware falha, a exportação sobrevive.

Não há mock de ffmpeg aqui. O que estes testes fazem é mentir sobre as
*capabilities* — declarar utilizável um encoder que este binário não tem — para
que o ffmpeg falhe **de verdade**, do jeito que falharia na máquina de um
usuário cujo driver quebrou depois do probe. Depois exigem que o vídeo saia
íntegro mesmo assim.

Por que mentir sobre as capabilities em vez de sabotar o ffmpeg: é a única forma
de reproduzir o cenário que motiva o retry — encoder aprovado no probe e
quebrado na hora H — sem depender do hardware da máquina que roda os testes.
Assim o teste vale igual num Mac, num PC com NVIDIA e na CI sem GPU nenhuma.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import encoder_caps
import encoder_policy
from compressor import VideoCompressor
from editor_state import EditorState
from encoder_caps import EncoderCapabilities

# Encoder que não existe em nenhum build deste projeto (macOS não tem NVENC;
# o build de Windows não tem VideoToolbox). Declará-lo "usável" garante que o
# ffmpeg vai recusar o comando, que é exatamente o que queremos provocar.
ENCODER_INEXISTENTE = 'h264_nvenc' if sys.platform == 'darwin' else 'h264_videotoolbox'
PLATAFORMA_DO_FAKE = 'win32' if sys.platform == 'darwin' else 'darwin'

CAPS_MENTIROSAS = EncoderCapabilities(
    ffmpeg_path='(fake)',
    platform_key=PLATAFORMA_DO_FAKE,
    machine='x86_64',
    listed_encoders=('libx264', ENCODER_INEXISTENTE),
    usable_encoders=('libx264', ENCODER_INEXISTENTE),
    tier='nvenc' if sys.platform == 'darwin' else 'videotoolbox',
)


def ffprobe_campos(compressor, caminho, entradas):
    """Lê campos do stream de vídeo com ffprobe. Retorna lista de strings."""
    result = subprocess.run(
        [compressor.ffprobe_path, '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', f'stream={entradas}', '-of', 'default=nw=1:nk=1', caminho],
        capture_output=True, text=True,
    )
    return result.stdout.strip().splitlines()


class FallbackDeHardwareTest(unittest.TestCase):
    """O caminho simples (`-vf`) e o segmentado (`-filter_complex`)."""

    @classmethod
    def setUpClass(cls):
        cls.compressor = VideoCompressor()
        cls._tmp = TemporaryDirectory()
        cls.tmp_path = Path(cls._tmp.name)
        cls.fonte = str(cls.tmp_path / 'fonte.mp4')

        # Vídeo real com áudio real: o pipeline reencoda os dois.
        subprocess.run(
            [cls.compressor.ffmpeg_path, '-hide_banner', '-loglevel', 'error',
             '-f', 'lavfi', '-i', 'testsrc2=size=640x480:rate=30:duration=3',
             '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3',
             '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-shortest', '-y', cls.fonte],
            check=True, capture_output=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        encoder_caps.set_capabilities_for_test(CAPS_MENTIROSAS)
        self.addCleanup(encoder_caps.set_capabilities_for_test, None)

    def _assert_video_integro(self, caminho, duracao_esperada=3.0):
        self.assertTrue(os.path.exists(caminho), 'o arquivo de saída não existe')
        self.assertGreater(os.path.getsize(caminho), 1000, 'saída pequena demais para ser vídeo')

        codec, largura, altura, frames = (ffprobe_campos(
            self.compressor, caminho, 'codec_name,width,height,nb_frames'
        ) + ['', '', '', ''])[:4]

        self.assertEqual(codec, 'h264', 'a saída do fallback deveria ser H.264')
        self.assertEqual((largura, altura), ('640', '480'))
        self.assertGreater(int(frames or 0), 0, 'vídeo sem frames decodificáveis')

        info = self.compressor.get_video_info(caminho)
        self.assertIsNotNone(info, 'ffprobe não conseguiu ler a saída')
        self.assertAlmostEqual(info['duration'], duracao_esperada, delta=0.5)

    def test_o_plano_realmente_escolhe_o_encoder_quebrado(self):
        """Sanidade: sem isto, os testes abaixo passariam por não testar nada."""
        plan = self.compressor._encode_plan(
            'Balanceado', VideoCompressor.COMPRESSION_PROFILES['Balanceado'], 'saida.mp4'
        )
        self.assertEqual(plan.encoder, ENCODER_INEXISTENTE)
        self.assertTrue(plan.is_hardware)

    def test_caminho_simples_cai_para_software_e_entrega_video(self):
        saida = str(self.tmp_path / 'simples.mp4')

        with self.assertLogs('compressor', level='WARNING') as registro:
            sucesso, mensagem = self.compressor.compress_video(
                self.fonte, saida, profile='Balanceado'
            )

        self.assertTrue(sucesso, f'a exportação deveria ter sobrevivido ao fallback: {mensagem}')
        self._assert_video_integro(saida)

        # O usuário não vê erro, mas o log tem que registrar o que houve —
        # senão ninguém descobre que a aceleração parou de funcionar.
        texto = '\n'.join(registro.output)
        self.assertIn(ENCODER_INEXISTENTE, texto)
        self.assertIn(encoder_policy.SOFTWARE_ENCODER, texto)

    def test_caminho_segmentado_cai_para_software_e_entrega_video(self):
        """O segundo lugar onde o encoder era hardcoded."""
        saida = str(self.tmp_path / 'segmentado.mp4')
        info = self.compressor.get_video_info(self.fonte)

        state = EditorState()
        state.reset(duration=info['duration'], source_path=self.fonte)
        primeiro = state.segments[0]
        primeiro.timeline_end = 1.0
        primeiro.source_end = 1.0
        state.add_media_segment(self.fonte, duration=info['duration'] - 2.0)
        segundo = state.segments[1]
        segundo.source_start = 2.0
        segundo.source_end = info['duration']
        segundo.timeline_start = 1.0
        segundo.timeline_end = 1.0 + (info['duration'] - 2.0)

        segmentos = state.segments_for_export()
        self.assertEqual(len(segmentos), 2, 'o teste precisa de 2 segmentos para forçar o concat')

        sucesso, mensagem = self.compressor.compress_video(
            self.fonte, saida, profile='Balanceado', segments=segmentos
        )

        self.assertTrue(sucesso, f'exportação segmentada falhou: {mensagem}')
        # 1s do primeiro segmento + 1s do segundo.
        self._assert_video_integro(saida, duracao_esperada=2.0)

    def test_alta_qualidade_nem_tenta_o_hardware(self):
        """Não deve haver retry: o perfil já sai em software na primeira tentativa."""
        saida = str(self.tmp_path / 'alta.mp4')

        sucesso, mensagem = self.compressor.compress_video(
            self.fonte, saida, profile='Alta Qualidade'
        )

        self.assertTrue(sucesso, mensagem)
        self._assert_video_integro(saida)

    def test_falha_que_nao_e_de_hardware_nao_vira_retry_infinito(self):
        """Saída em pasta inexistente falha nas duas tentativas e reporta erro."""
        saida = str(self.tmp_path / 'pasta_que_nao_existe' / 'x.mp4')

        sucesso, mensagem = self.compressor.compress_video(
            self.fonte, saida, profile='Balanceado'
        )

        self.assertFalse(sucesso)
        self.assertIn('Erro ao comprimir', mensagem)


class CapabilitiesReaisTest(unittest.TestCase):
    """O que o policy decide com as capabilities REAIS desta máquina."""

    @classmethod
    def setUpClass(cls):
        cls.compressor = VideoCompressor()
        cls.caps = encoder_caps.detect_capabilities(cls.compressor.ffmpeg_path)

    def setUp(self):
        encoder_caps.set_capabilities_for_test(self.caps)
        self.addCleanup(encoder_caps.set_capabilities_for_test, None)

    def test_encoder_escolhido_esta_entre_os_aprovados_no_probe(self):
        """Nunca escolher algo que o probe real não aprovou."""
        for perfil in VideoCompressor.COMPRESSION_PROFILES:
            with self.subTest(perfil=perfil):
                plan = encoder_policy.plan_encode(
                    perfil, VideoCompressor.COMPRESSION_PROFILES[perfil], self.caps
                )
                self.assertIn(plan.encoder, self.caps.usable_encoders)

    def test_hardware_so_bitrate_nao_e_usado(self):
        """Nesta máquina (Mac Intel) isso significa: exportação em software."""
        hw_bitrate = [e for e in self.caps.usable_encoders
                      if self.caps.quality_mode_of(e) == 'bitrate']
        if not hw_bitrate:
            self.skipTest('esta máquina não tem encoder limitado a bitrate')

        plan = encoder_policy.plan_encode(
            'Compressão Máxima',
            VideoCompressor.COMPRESSION_PROFILES['Compressão Máxima'], self.caps
        )
        self.assertFalse(plan.is_hardware, f'não deveria usar {plan.encoder}')
        self.assertEqual(plan.encoder, encoder_policy.SOFTWARE_ENCODER)


class HardwareRealTest(unittest.TestCase):
    """Se esta máquina tem hardware de verdade, o caminho acelerado tem que funcionar.

    Sem isto, todos os testes acima passariam mesmo que o caminho de hardware
    estivesse permanentemente quebrado — eles só exercitam o fallback.
    """

    @classmethod
    def setUpClass(cls):
        cls.compressor = VideoCompressor()
        cls.caps = encoder_caps.detect_capabilities(cls.compressor.ffmpeg_path)
        cls._tmp = TemporaryDirectory()
        cls.tmp_path = Path(cls._tmp.name)
        cls.fonte = str(cls.tmp_path / 'fonte.mp4')
        subprocess.run(
            [cls.compressor.ffmpeg_path, '-hide_banner', '-loglevel', 'error',
             '-f', 'lavfi', '-i', 'testsrc2=size=640x480:rate=30:duration=2',
             '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
             '-an', '-y', cls.fonte],
            check=True, capture_output=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        encoder_caps.set_capabilities_for_test(self.caps)
        self.addCleanup(encoder_caps.set_capabilities_for_test, None)

        # Ter hardware não basta: o policy recusa o que só oferece bitrate
        # (ver ALLOW_BITRATE_HARDWARE). O que importa aqui é se ele de fato
        # escolheria hardware nesta máquina.
        plan = encoder_policy.plan_encode(
            'Balanceado', VideoCompressor.COMPRESSION_PROFILES['Balanceado'], self.caps
        )
        if not plan.is_hardware:
            self.skipTest(f'o policy não usa hardware nesta máquina: {plan.reason}')

    def test_exportacao_acelerada_produz_video_valido(self):
        """O hardware precisa encodar de verdade — sem cair no fallback.

        Este teste já passou por engano uma vez: o encoder falhava, o retry
        salvava a exportação e o `assertTrue(sucesso)` ficava verde. Daí o
        `assertNoLogs`: se houve fallback, a aceleração não está funcionando e
        o teste tem que dizer isso.
        """
        saida = str(self.tmp_path / 'hw.mp4')
        info = self.compressor.get_video_info(self.fonte)

        plan = self.compressor._encode_plan(
            'Balanceado', VideoCompressor.COMPRESSION_PROFILES['Balanceado'], saida,
            video_info=info,
        )
        self.assertTrue(plan.is_hardware, 'o policy deveria ter escolhido hardware aqui')

        with self.assertNoLogs('compressor', level='WARNING'):
            sucesso, mensagem = self.compressor.compress_video(
                self.fonte, saida, profile='Balanceado'
            )

        self.assertTrue(sucesso, f'exportação por hardware falhou: {mensagem}')
        codec = ffprobe_campos(self.compressor, saida, 'codec_name')
        self.assertEqual(codec[:1], ['h264'])
        self.assertGreater(os.path.getsize(saida), 1000)

    def test_o_modo_de_qualidade_detectado_e_o_que_o_plano_usa(self):
        """O probe e o comando real precisam falar dos mesmos parâmetros."""
        info = self.compressor.get_video_info(self.fonte)
        plan = self.compressor._encode_plan(
            'Balanceado', VideoCompressor.COMPRESSION_PROFILES['Balanceado'],
            'saida.mp4', video_info=info,
        )
        modo = self.caps.quality_mode_of(plan.encoder)
        args = list(plan.video_args)

        if modo == 'bitrate':
            self.assertIn('-b:v', args)
            self.assertNotIn('-q:v', args)
        else:
            self.assertNotIn('-b:v', args[2:])  # nvenc usa '-b:v 0' legitimamente


if __name__ == '__main__':
    unittest.main()
