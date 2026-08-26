"""
Regressão do binário de FFmpeg embutido em ``desktop/bin/``.

Motivo: o binário macOS que vinha versionado era o do Homebrew Intel, linkado
DINAMICAMENTE contra dylibs em ``/usr/local/opt/``. Isso quebrava de duas formas
que nenhum teste pegava:

- em Apple Silicon rodava sob Rosetta 2, perdendo performance silenciosamente;
- em qualquer Mac sem exatamente aquelas fórmulas do Homebrew, o binário nem
  subia — morria com erro de dyld, e o usuário via "falha ao comprimir".

Os dois são invisíveis na máquina de quem buildou. Por isso estes testes checam
propriedades do *arquivo*, não só se ele roda aqui.

Os binários não são versionados no git (são grandes demais para o GitHub); quem
clonou o repositório popula ``desktop/bin/`` com::

    python desktop/tools/fetch_ffmpeg.py

Estes testes FALHAM (não pulam) se o binário estiver ausente: um build sem
binário embutido é um bug de release, não uma configuração alternativa.
"""

import os
import platform
import re
import subprocess
import sys
import unittest
from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESKTOP_DIR))

from compressor import VideoCompressor  # noqa: E402

BIN_DIR = DESKTOP_DIR / "bin"
IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"

# Versão mínima. Abaixo disso o comportamento de auto-rotação e de alguns filtros
# usados pelo pipeline muda, e a falha aparece como vídeo torto em vez de erro.
MIN_VERSION = (8, 0)

# Encoders dos quais o pipeline depende hoje (ver compressor.py: '-c:v libx264'
# e '-c:a aac'). Se o código passar a depender de outro, acrescente aqui — é este
# teste que garante que o binário embutido acompanha.
REQUIRED_ENCODERS = ("libx264", "aac")

# VideoToolbox é requisito do build macOS: é a porta para aceleração por hardware,
# e um build sem ele fecha essa porta sem avisar.
REQUIRED_ENCODERS_MACOS = ("h264_videotoolbox", "hevc_videotoolbox")

# libvmaf é o que o benchmark (desktop/tests/bench) usa para medir qualidade.
# Sem ele, uma otimização pode trocar qualidade por velocidade sem ninguém ver.
REQUIRED_FILTERS = ("libvmaf",)

FETCH_HINT = "Rode:  python desktop/tools/fetch_ffmpeg.py"


def binary_name(tool: str) -> str:
    return f"{tool}.exe" if IS_WINDOWS else tool


def run_tool(path: Path, args) -> str:
    result = subprocess.run(
        [str(path), *args], capture_output=True, text=True, timeout=120
    )
    return result.stdout + result.stderr


class BundledBinaryPresenceTest(unittest.TestCase):
    """O binário existe, é arquivo e é executável."""

    def test_binarios_existem_e_sao_executaveis(self):
        for tool in ("ffmpeg", "ffprobe"):
            path = BIN_DIR / binary_name(tool)
            with self.subTest(tool=tool):
                self.assertTrue(
                    path.exists(),
                    f"Binário embutido ausente: {path}\n{FETCH_HINT}",
                )
                self.assertTrue(path.is_file(), f"{path} não é um arquivo comum")
                self.assertTrue(
                    os.access(path, os.X_OK),
                    f"{path} existe mas não tem permissão de execução.\n"
                    f"Conserte com:  chmod +x {path}",
                )

    def test_compressor_resolve_para_o_binario_embutido(self):
        """O compressor precisa achar o binário embutido, não o do sistema.

        ``VideoCompressor._find_ffmpeg`` cai para o ffmpeg do sistema quando o
        embutido não está lá. Isso é bom em runtime, mas faria os outros testes
        aqui validarem o binário errado — e mascararia justamente a regressão
        que este arquivo existe para pegar.
        """
        compressor = VideoCompressor()
        for attr, tool in (("ffmpeg_path", "ffmpeg"), ("ffprobe_path", "ffprobe")):
            resolved = Path(getattr(compressor, attr)).resolve()
            expected = (BIN_DIR / binary_name(tool)).resolve()
            with self.subTest(tool=tool):
                self.assertEqual(
                    resolved, expected,
                    f"O compressor resolveu {tool} para {resolved}, e não para o "
                    f"binário embutido {expected}.\n{FETCH_HINT}",
                )


@unittest.skipUnless(IS_MACOS, "checagens de Mach-O só se aplicam ao macOS")
class MacOSBinaryShapeTest(unittest.TestCase):
    """Formato do Mach-O: estático e com a arquitetura da máquina."""

    def setUp(self):
        for tool in ("ffmpeg", "ffprobe"):
            if not (BIN_DIR / tool).exists():
                self.fail(f"Binário embutido ausente: {BIN_DIR / tool}\n{FETCH_HINT}")

    def _external_deps(self, path: Path):
        """Dependências dinâmicas fora do sistema base.

        ``/usr/lib`` e ``/System`` existem em qualquer Mac, então depender delas
        é seguro. Qualquer outro caminho — ``/usr/local/opt/`` do Homebrew Intel,
        ``/opt/homebrew/`` do Apple Silicon — significa que o binário só roda na
        máquina de quem o compilou.
        """
        output = subprocess.run(
            ["otool", "-L", str(path)], capture_output=True, text=True, timeout=60
        ).stdout
        external = []
        for line in output.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            lib = line.split(" (")[0].strip()
            if lib.startswith("/usr/lib/") or lib.startswith("/System/"):
                continue
            external.append(lib)
        return external

    def _archs(self, path: Path):
        output = subprocess.run(
            ["lipo", "-archs", str(path)], capture_output=True, text=True, timeout=60
        ).stdout
        return output.split()

    def test_nao_depende_de_biblioteca_fora_do_sistema(self):
        for tool in ("ffmpeg", "ffprobe"):
            path = BIN_DIR / tool
            with self.subTest(tool=tool):
                external = self._external_deps(path)
                self.assertEqual(
                    external, [],
                    f"{tool} não é estático: depende de {external}.\n"
                    "Esse binário quebra com erro de dyld em qualquer Mac que não "
                    f"tenha essas bibliotecas.\n{FETCH_HINT}",
                )

    def test_contem_a_arquitetura_da_maquina_atual(self):
        machine = platform.machine()
        for tool in ("ffmpeg", "ffprobe"):
            path = BIN_DIR / tool
            with self.subTest(tool=tool):
                archs = self._archs(path)
                self.assertIn(
                    machine, archs,
                    f"{tool} não contém a arquitetura desta máquina ({machine}); "
                    f"contém apenas {archs}.\n"
                    "Num Mac Apple Silicon isso significa rodar sob Rosetta 2 (ou "
                    f"nem rodar).\n{FETCH_HINT}",
                )


class BundledBinaryCapabilitiesTest(unittest.TestCase):
    """Versão, encoders e filtros que o código depende."""

    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = BIN_DIR / binary_name("ffmpeg")
        if not cls.ffmpeg.exists():
            raise AssertionError(
                f"Binário embutido ausente: {cls.ffmpeg}\n{FETCH_HINT}"
            )
        cls.version_text = run_tool(cls.ffmpeg, ["-hide_banner", "-version"])
        cls.encoders_text = run_tool(cls.ffmpeg, ["-hide_banner", "-encoders"])
        cls.filters_text = run_tool(cls.ffmpeg, ["-hide_banner", "-filters"])

    def _assert_listed(self, listing: str, name: str, kind: str):
        # As listagens do ffmpeg têm a forma " V....D libx264   descrição".
        # Casar a linha inteira evita falso positivo quando o nome aparece só
        # dentro do texto da descrição de outro item.
        found = re.search(rf"^\s*\S+\s+{re.escape(name)}\s", listing, re.M)
        self.assertIsNotNone(
            found,
            f"{kind} ausente no binário embutido: {name}\n"
            f"O build do FFmpeg em desktop/bin não tem {name} habilitado.\n{FETCH_HINT}",
        )

    def test_versao_minima(self):
        match = re.search(r"ffmpeg version n?(\d+)\.(\d+)", self.version_text)
        self.assertIsNotNone(
            match,
            f"Não foi possível ler a versão de {self.ffmpeg}.\n"
            f"Saída:\n{self.version_text[:400]}",
        )
        version = tuple(int(g) for g in match.groups())
        self.assertGreaterEqual(
            version, MIN_VERSION,
            f"FFmpeg embutido é {'.'.join(map(str, version))}, abaixo do mínimo "
            f"{'.'.join(map(str, MIN_VERSION))}.\n{FETCH_HINT}",
        )

    def test_encoders_necessarios(self):
        for encoder in REQUIRED_ENCODERS:
            with self.subTest(encoder=encoder):
                self._assert_listed(self.encoders_text, encoder, "Encoder")

    @unittest.skipUnless(IS_MACOS, "VideoToolbox só existe no macOS")
    def test_encoders_videotoolbox_no_macos(self):
        for encoder in REQUIRED_ENCODERS_MACOS:
            with self.subTest(encoder=encoder):
                self._assert_listed(self.encoders_text, encoder, "Encoder")

    def test_filtros_necessarios(self):
        for filt in REQUIRED_FILTERS:
            with self.subTest(filtro=filt):
                self._assert_listed(self.filters_text, filt, "Filtro")


class ProbeBinaryInfoTest(unittest.TestCase):
    """``VideoCompressor.probe_binary_info`` descreve o binário corretamente."""

    @classmethod
    def setUpClass(cls):
        cls.info = VideoCompressor().probe_binary_info()

    def test_reporta_versao_e_caminho(self):
        self.assertTrue(self.info["disponivel"], f"probe falhou: {self.info}")
        self.assertIsNotNone(self.info["version"], "version não foi detectada")
        self.assertTrue(self.info["is_bundled"], "não resolveu para o binário embutido")

    def test_reporta_encoders_que_o_codigo_usa(self):
        for encoder in REQUIRED_ENCODERS:
            with self.subTest(encoder=encoder):
                self.assertIn(encoder, self.info["encoders_disponiveis"])

    @unittest.skipUnless(IS_MACOS, "arquitetura Mach-O só se aplica ao macOS")
    def test_reporta_arquitetura_e_estatico(self):
        self.assertIn(platform.machine(), self.info["arch"])
        self.assertTrue(
            self.info["is_static"],
            "probe_binary_info reportou o binário como dinâmico",
        )


if __name__ == "__main__":
    unittest.main()
