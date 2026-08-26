"""Mapeamento (perfil × capabilities) -> parâmetros de encode.

Testes de tabela puros: nada aqui roda ffmpeg. As capabilities são fabricadas
para poder afirmar o que aconteceria numa máquina NVIDIA, numa AMD e numa Intel
sem precisar de uma de cada — que é justamente o motivo de o policy ser um
módulo separado do compressor.

O que está sendo protegido, em ordem de importância:

1. `Alta Qualidade` nunca sai de software, por mais hardware que exista.
2. VideoToolbox nunca recebe `-crf` (não existe lá) e a escala de `-q:v` é
   invertida em relação ao CRF — inverter errado degrada em silêncio.
3. HEVC em mp4/mov sempre leva `-tag:v hvc1`, senão o arquivo não abre em
   device Apple.
4. Qualquer buraco na detecção cai em libx264, nunca em erro.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import encoder_policy
from encoder_caps import EncoderCapabilities
from compressor import VideoCompressor


def fake_caps(platform_key: str, usable=(), tier='software', modes=None) -> EncoderCapabilities:
    """Capabilities fabricadas, sem tocar em ffmpeg nem em hardware."""
    return EncoderCapabilities(
        ffmpeg_path='/fake/ffmpeg',
        ffmpeg_version='ffmpeg version 9.0',
        platform_key=platform_key,
        machine='x86_64',
        listed_encoders=tuple(usable),
        usable_encoders=tuple(usable),
        tier=tier,
        quality_modes=dict(modes or {}),
    )


VT = ('libx264', 'h264_videotoolbox', 'hevc_videotoolbox')
# Apple Silicon: VideoToolbox aceita qualidade constante (-q:v).
MAC = fake_caps('darwin', VT, 'videotoolbox')
# Mac Intel: -q:v é recusado pelo ffmpeg, só resta bitrate. Não é hipótese —
# foi o que este projeto encontrou na máquina de desenvolvimento.
MAC_INTEL = fake_caps('darwin', VT, 'videotoolbox', modes={
    'h264_videotoolbox': 'bitrate', 'hevc_videotoolbox': 'bitrate',
})
NVIDIA = fake_caps('win32', ('libx264', 'h264_nvenc', 'hevc_nvenc'), 'nvenc')
INTEL = fake_caps('win32', ('libx264', 'h264_qsv', 'hevc_qsv'), 'qsv')
AMD = fake_caps('win32', ('libx264', 'h264_amf', 'hevc_amf'), 'amf')
SEM_HW = fake_caps('win32', ('libx264',), 'software')

BALANCEADO = VideoCompressor.COMPRESSION_PROFILES['Balanceado']
ALTA = VideoCompressor.COMPRESSION_PROFILES['Alta Qualidade']


def args_de(perfil, caps, **kwargs):
    config = VideoCompressor.COMPRESSION_PROFILES[perfil]
    return list(encoder_policy.plan_encode(perfil, config, caps, **kwargs).video_args)


class PoliticaDeSoftwareTest(unittest.TestCase):
    """A regra que não pode ser quebrada por otimização nenhuma."""

    def test_alta_qualidade_ignora_todo_hardware_disponivel(self):
        for nome, caps in [('mac', MAC), ('nvidia', NVIDIA), ('intel', INTEL), ('amd', AMD)]:
            with self.subTest(maquina=nome):
                plan = encoder_policy.plan_encode('Alta Qualidade', ALTA, caps)
                self.assertEqual(plan.encoder, 'libx264')
                self.assertFalse(plan.is_hardware)
                self.assertIn('-crf', plan.video_args)

    def test_demais_perfis_aceitam_hardware(self):
        for perfil in ('Balanceado', 'Compressão Forte', 'Compressão Máxima'):
            with self.subTest(perfil=perfil):
                config = VideoCompressor.COMPRESSION_PROFILES[perfil]
                plan = encoder_policy.plan_encode(perfil, config, NVIDIA)
                self.assertTrue(plan.is_hardware)
                self.assertEqual(plan.encoder, 'h264_nvenc')


class FallbackTest(unittest.TestCase):
    """Todo caminho degradado termina em libx264, nunca em exceção."""

    def test_sem_capabilities_detectadas_usa_software(self):
        plan = encoder_policy.plan_encode('Balanceado', BALANCEADO, None)
        self.assertEqual(plan.encoder, 'libx264')
        self.assertFalse(plan.is_hardware)

    def test_sem_hardware_usavel_usa_software(self):
        plan = encoder_policy.plan_encode('Balanceado', BALANCEADO, SEM_HW)
        self.assertEqual(plan.encoder, 'libx264')

    def test_allow_hardware_false_forca_software(self):
        plan = encoder_policy.plan_encode('Balanceado', BALANCEADO, NVIDIA, allow_hardware=False)
        self.assertEqual(plan.encoder, 'libx264')
        self.assertFalse(plan.is_hardware)

    def test_encoder_listado_mas_reprovado_no_probe_nao_e_escolhido(self):
        """`usable_encoders` é o que manda — listar não basta."""
        caps = EncoderCapabilities(
            platform_key='win32',
            listed_encoders=('libx264', 'h264_nvenc'),
            usable_encoders=('libx264',),   # nvenc reprovou no probe real
            tier='software',
        )
        plan = encoder_policy.plan_encode('Balanceado', BALANCEADO, caps)
        self.assertEqual(plan.encoder, 'libx264')

    def test_plataforma_desconhecida_usa_software(self):
        caps = fake_caps('sunos5', ('libx264', 'h264_nvenc'), 'nvenc')
        self.assertEqual(args_de('Balanceado', caps)[:2], ['-c:v', 'libx264'])


class VideoToolboxTest(unittest.TestCase):
    """A família mais fácil de errar: escala invertida e sem CRF."""

    def test_nunca_recebe_crf(self):
        for perfil in ('Balanceado', 'Compressão Forte', 'Compressão Máxima'):
            with self.subTest(perfil=perfil):
                args = args_de(perfil, MAC)
                self.assertNotIn('-crf', args)
                self.assertIn('-q:v', args)

    def test_qualidade_cai_conforme_o_perfil_comprime_mais(self):
        """-q:v é 0-100 com MAIOR = MELHOR: a série tem que ser decrescente."""
        valores = []
        for perfil in ('Balanceado', 'Compressão Forte', 'Compressão Máxima'):
            args = args_de(perfil, MAC)
            valores.append(int(args[args.index('-q:v') + 1]))

        self.assertEqual(valores, sorted(valores, reverse=True),
                         f"-q:v deveria cair conforme a compressão aumenta, veio {valores}")
        for valor in valores:
            self.assertTrue(0 <= valor <= 100, f"-q:v fora da faixa 0-100: {valor}")

    def test_q_v_fica_na_faixa_util_para_os_perfis_reais(self):
        """Os perfis do app não podem cair em regiões absurdas da escala."""
        balanceado = args_de('Balanceado', MAC)
        self.assertGreaterEqual(int(balanceado[balanceado.index('-q:v') + 1]), 45)


class HardwareSoBitrateTest(unittest.TestCase):
    """Hardware que só faz bitrate é recusado — a decisão medida no bench."""

    def test_bitrate_puro_nao_e_usado_por_padrao(self):
        plan = encoder_policy.plan_encode('Balanceado', BALANCEADO, MAC_INTEL)
        self.assertEqual(plan.encoder, 'libx264')
        self.assertFalse(plan.is_hardware)
        self.assertIn('bitrate', plan.reason)

    def test_o_motivo_distingue_de_maquina_sem_hardware(self):
        """Diagnóstico: 'não tem GPU' e 'tem, mas recusamos' são coisas diferentes."""
        sem_hw = encoder_policy.plan_encode('Balanceado', BALANCEADO, SEM_HW).reason
        so_bitrate = encoder_policy.plan_encode('Balanceado', BALANCEADO, MAC_INTEL).reason
        self.assertNotEqual(sem_hw, so_bitrate)

    def test_pode_ser_habilitado_explicitamente(self):
        plan = encoder_policy.plan_encode('Balanceado', BALANCEADO, MAC_INTEL,
                                          allow_bitrate_hardware=True)
        self.assertTrue(plan.is_hardware)

    def test_qualidade_constante_continua_aceita(self):
        """A recusa é do modo bitrate, não do hardware em geral."""
        for caps in (MAC, NVIDIA, INTEL, AMD):
            with self.subTest(tier=caps.tier):
                self.assertTrue(
                    encoder_policy.plan_encode('Balanceado', BALANCEADO, caps).is_hardware
                )


class VideoToolboxBitrateTest(unittest.TestCase):
    """Mac Intel: sem `-q:v`, o alvo tem que sair de resolução × fps.

    O modo é recusado por padrão (ver `HardwareSoBitrateTest`), mas o código
    continua no lugar e testado: é o único caminho de aceleração possível
    nessas máquinas, caso um dia se opte por oferecê-lo como escolha do usuário.
    """

    P1080P30 = {'width': 1920, 'height': 1080, 'fps': 30.0}
    P4K30 = {'width': 3840, 'height': 2160, 'fps': 30.0}
    P1080P60 = {'width': 1920, 'height': 1080, 'fps': 60.0}

    def _bitrate(self, perfil, video_info):
        args = args_de(perfil, MAC_INTEL, video_info=video_info, allow_bitrate_hardware=True)
        return int(args[args.index('-b:v') + 1].rstrip('k'))

    def test_usa_bitrate_e_nao_qscale(self):
        args = args_de('Balanceado', MAC_INTEL, allow_bitrate_hardware=True, video_info=self.P1080P30)
        self.assertNotIn('-q:v', args)
        for opcao in ('-b:v', '-maxrate', '-bufsize'):
            self.assertIn(opcao, args)

    def test_maxrate_e_bufsize_acima_do_alvo(self):
        args = args_de('Balanceado', MAC_INTEL, allow_bitrate_hardware=True, video_info=self.P1080P30)
        alvo = int(args[args.index('-b:v') + 1].rstrip('k'))
        maxrate = int(args[args.index('-maxrate') + 1].rstrip('k'))
        bufsize = int(args[args.index('-bufsize') + 1].rstrip('k'))
        self.assertGreater(maxrate, alvo)
        self.assertGreater(bufsize, maxrate)

    def test_4k_recebe_mais_bitrate_que_1080p(self):
        self.assertGreater(self._bitrate('Balanceado', self.P4K30),
                           self._bitrate('Balanceado', self.P1080P30))

    def test_60fps_recebe_mais_bitrate_que_30fps(self):
        self.assertGreater(self._bitrate('Balanceado', self.P1080P60),
                           self._bitrate('Balanceado', self.P1080P30))

    def test_bitrate_cai_conforme_o_perfil_comprime_mais(self):
        valores = [self._bitrate(p, self.P1080P30)
                   for p in ('Balanceado', 'Compressão Forte', 'Compressão Máxima')]
        self.assertEqual(valores, sorted(valores, reverse=True), valores)

    def test_video_info_ausente_nao_quebra(self):
        """Sem dimensões, assume 1080p30 em vez de gerar bitrate absurdo."""
        for info in (None, {}, {'width': 0, 'height': 0}, {'width': 'x', 'height': None}):
            with self.subTest(info=info):
                args = args_de('Balanceado', MAC_INTEL, allow_bitrate_hardware=True, video_info=info)
                alvo = int(args[args.index('-b:v') + 1].rstrip('k'))
                self.assertTrue(1000 < alvo < 60000, f'bitrate implausível: {alvo}k')

    def test_resolucao_absurda_e_grampeada(self):
        gigante = {'width': 15360, 'height': 8640, 'fps': 120.0}
        alvo = self._bitrate('Balanceado', gigante)
        self.assertLessEqual(alvo, 60000)

    def test_apple_silicon_continua_usando_qscale(self):
        """A correção do Intel não pode ter tirado o modo bom do Apple Silicon."""
        args = args_de('Balanceado', MAC, video_info=self.P1080P30)
        self.assertIn('-q:v', args)
        self.assertNotIn('-b:v', args)


class HevcTagTest(unittest.TestCase):
    def test_hevc_em_mp4_recebe_hvc1(self):
        args = args_de('Balanceado', MAC, output_file='/tmp/saida.mp4', prefer_hevc=True)
        self.assertIn('hevc_videotoolbox', args)
        self.assertIn('-tag:v', args)
        self.assertEqual(args[args.index('-tag:v') + 1], 'hvc1')

    def test_hevc_em_mov_tambem_recebe_hvc1(self):
        args = args_de('Balanceado', MAC, output_file='/tmp/saida.MOV', prefer_hevc=True)
        self.assertIn('hvc1', args)

    def test_h264_nunca_recebe_hvc1(self):
        args = args_de('Balanceado', MAC, output_file='/tmp/saida.mp4')
        self.assertIn('h264_videotoolbox', args)
        self.assertNotIn('-tag:v', args)

    def test_hevc_fora_de_container_apple_nao_recebe_tag(self):
        args = args_de('Balanceado', MAC, output_file='/tmp/saida.mkv', prefer_hevc=True)
        self.assertNotIn('-tag:v', args)

    def test_hevc_desligado_por_padrao(self):
        args = args_de('Balanceado', MAC, output_file='/tmp/saida.mp4')
        self.assertNotIn('hevc_videotoolbox', args)


class ParametrosPorFamiliaTest(unittest.TestCase):
    """Cada família tem um contrato próprio; errá-lo custa qualidade em silêncio."""

    def test_nvenc_usa_cq_com_bitrate_zero(self):
        args = args_de('Balanceado', NVIDIA)
        self.assertIn('-cq', args)
        # Sem `-b:v 0` o -cq vira só um teto e a qualidade deixa de ser constante.
        self.assertEqual(args[args.index('-b:v') + 1], '0')
        self.assertEqual(args[args.index('-rc') + 1], 'vbr')
        self.assertEqual(args[args.index('-tune') + 1], 'hq')

    def test_nvenc_usa_preset_da_familia_p(self):
        preset = args_de('Balanceado', NVIDIA)[:]
        valor = preset[preset.index('-preset') + 1]
        self.assertRegex(valor, r'^p[1-7]$')

    def test_qsv_usa_global_quality_sem_bitrate(self):
        args = args_de('Balanceado', INTEL)
        self.assertIn('-global_quality', args)
        self.assertNotIn('-b:v', args)

    def test_amf_usa_cqp(self):
        args = args_de('Balanceado', AMD)
        self.assertEqual(args[args.index('-rc') + 1], 'cqp')
        self.assertIn('-qp_i', args)
        self.assertIn('-qp_p', args)

    def test_ordem_de_preferencia_no_windows(self):
        """Com as três famílias usáveis, NVENC ganha."""
        todas = fake_caps('win32', ('libx264', 'h264_nvenc', 'h264_qsv', 'h264_amf'), 'nvenc')
        self.assertEqual(encoder_policy.plan_encode('Balanceado', BALANCEADO, todas).encoder,
                         'h264_nvenc')

    def test_qsv_ganha_de_amf_quando_nao_ha_nvidia(self):
        sem_nvidia = fake_caps('win32', ('libx264', 'h264_qsv', 'h264_amf'), 'qsv')
        self.assertEqual(encoder_policy.plan_encode('Balanceado', BALANCEADO, sem_nvidia).encoder,
                         'h264_qsv')


class TodosOsPerfisTest(unittest.TestCase):
    def test_todo_perfil_gera_plano_valido_em_toda_maquina(self):
        """Varredura completa: nenhum par (perfil, máquina) pode faltar -c:v."""
        maquinas = {'mac': MAC, 'nvidia': NVIDIA, 'intel': INTEL, 'amd': AMD,
                    'sem_hw': SEM_HW, 'indetectado': None}
        for nome, caps in maquinas.items():
            for perfil in VideoCompressor.COMPRESSION_PROFILES:
                with self.subTest(maquina=nome, perfil=perfil):
                    args = args_de(perfil, caps)
                    self.assertEqual(args[0], '-c:v')
                    self.assertTrue(args[1])


if __name__ == '__main__':
    unittest.main()
