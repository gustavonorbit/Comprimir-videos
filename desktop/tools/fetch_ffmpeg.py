#!/usr/bin/env python3
"""Baixa os binários estáticos de FFmpeg/FFprobe usados pelo app e os instala em
``desktop/bin/``.

Por que este script existe
--------------------------
O binário macOS que vinha versionado no repositório era o do Homebrew Intel
(``/usr/local/Cellar/ffmpeg/8.1_1``), **linkado dinamicamente**. Isso dava dois
problemas sérios:

1. em Apple Silicon ele roda sob Rosetta 2, jogando fora a performance da máquina;
2. em qualquer Mac que não tenha exatamente aquelas fórmulas do Homebrew
   instaladas, ele nem sobe — morre com erro de dyld antes de comprimir nada.

A correção é usar builds **estáticos** (sem dependência fora de ``/usr/lib`` e
``/System``) e **universais** (``arm64`` + ``x86_64`` no mesmo arquivo, montados
com ``lipo``), que é o que este script produz.

Fontes escolhidas
-----------------
**macOS — ffmpeg.martin-riedl.de.** É a única fonte pública que publica builds
estáticos *das duas* arquiteturas do macOS com a mesma configuração de compilação,
o que é o requisito para juntar as duas metades num universal2 coerente. Publica
``.sha256`` ao lado de cada arquivo e mantém URLs versionadas por build (não só um
"latest" rolante), então dá para fixar exatamente o que foi baixado. Traz
VideoToolbox, libx264, libvmaf, libsvtav1 e libfreetype.

*(evermeet.cx, a fonte mais conhecida, publica só x86_64 — não serve para
universal. Homebrew é dinâmico por definição, que é justamente o bug.)*

**Windows — BtbN/FFmpeg-Builds.** Build estático de referência do ecossistema,
publicado no GitHub Releases com tags datadas (``autobuild-YYYY-MM-DD-HH-MM``)
cujas URLs de asset não mudam, então também dá para fixar.

Uso
---
    python desktop/tools/fetch_ffmpeg.py              # plataforma atual
    python desktop/tools/fetch_ffmpeg.py --check      # só valida o que já está lá
    python desktop/tools/fetch_ffmpeg.py --platform windows
    python desktop/tools/fetch_ffmpeg.py --update     # re-fixa o manifesto no build mais novo

O que for baixado é conferido contra o SHA-256 fixado em ``ffmpeg_manifest.json``
antes de ser instalado. Divergência aborta a instalação — um binário que não bate
com o hash fixado é exatamente o cenário que a verificação existe para pegar.

Se o download falhar (rede, firewall, fonte fora do ar), o script imprime a
instrução manual exata — URL, hash e onde colocar o arquivo — e ainda assim valida
o que estiver em ``desktop/bin/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
DESKTOP_DIR = TOOLS_DIR.parent
DEFAULT_BIN_DIR = DESKTOP_DIR / "bin"
MANIFEST_PATH = TOOLS_DIR / "ffmpeg_manifest.json"

TOOLS = ("ffmpeg", "ffprobe")

# Versão mínima aceita. O código usa filtros e opções que assumem FFmpeg moderno;
# abaixo disso o app pode falhar de formas silenciosas em vez de erro claro.
MIN_VERSION = (8, 0)

# Encoders/filtros dos quais o código realmente depende hoje.
REQUIRED_ENCODERS = ("libx264", "aac")
# VideoToolbox é requisito explícito do build macOS (aceleração por hardware).
REQUIRED_ENCODERS_MACOS = ("h264_videotoolbox", "hevc_videotoolbox")
# libvmaf é usado pelo benchmark (desktop/tests/bench) para medir qualidade.
REQUIRED_FILTERS = ("libvmaf",)

USER_AGENT = "Comprimir-videos-fetch-ffmpeg/1.0"
DOWNLOAD_TIMEOUT_S = 300

# Onde procurar o build mais novo quando se roda --update.
UPSTREAM = {
    "macos": {
        "kind": "martin-riedl",
        "arches": {"arm64": "macos/arm64", "x86_64": "macos/amd64"},
        "redirect": "https://ffmpeg.martin-riedl.de/redirect/latest/{path}/release/{tool}.zip",
    },
    "windows": {
        "kind": "btbn",
        "api": "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases?per_page=10",
        # Trilho de release estável (n8.1) em vez do master, que é branch de desenvolvimento.
        "asset_re": r"^ffmpeg-n8\.\d+(\.\d+)?(-\d+-g[0-9a-f]+)?-win64-gpl-8\.\d+\.zip$",
    },
}


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

def platform_key(system: str | None = None) -> str:
    system = (system or platform.system()).lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return system


def tool_filename(tool: str, plat: str) -> str:
    return f"{tool}.exe" if plat == "windows" else tool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def human_mb(num_bytes: int) -> str:
    return f"{num_bytes / 1048576:.1f} MB"


def _ssl_context() -> ssl.SSLContext:
    """Contexto TLS com verificação ligada.

    As instalações do Python vindas de python.org no macOS não usam o keychain do
    sistema e frequentemente ficam sem CA raiz nenhuma (é o que o
    "Install Certificates.command" conserta). Quando é esse o caso, cai no bundle
    do ``certifi``, que vem junto com pip. Verificação nunca é desligada: este
    script baixa executáveis que vão rodar na máquina do usuário.
    """
    context = ssl.create_default_context()
    if context.cert_store_stats().get("x509_ca", 0) == 0:
        try:
            import certifi
        except ImportError:
            raise SystemExit(
                "Nenhuma autoridade certificadora disponível para validar HTTPS.\n"
                "Conserte com uma das opções:\n"
                "  - rode o \"Install Certificates.command\" da sua instalação do Python, ou\n"
                "  - instale o certifi:  python3 -m pip install certifi"
            ) from None
        context = ssl.create_default_context(cafile=certifi.where())
    return context


def _open(url: str, timeout: int = DOWNLOAD_TIMEOUT_S):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())


def download(url: str, dest: Path, expected_sha256: str | None = None) -> str:
    """Baixa ``url`` para ``dest``. Devolve o SHA-256 do que foi baixado.

    Se ``expected_sha256`` for passado e não bater, apaga o arquivo e levanta erro:
    binário que não confere com o hash fixado não chega perto de desktop/bin/.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"    baixando {url}")
    with _open(url) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out)

    actual = sha256_file(dest)
    print(f"      {human_mb(dest.stat().st_size)}  sha256 {actual[:16]}...")

    if expected_sha256 and actual != expected_sha256:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 não confere para {url}\n"
            f"  esperado: {expected_sha256}\n"
            f"  obtido:   {actual}\n"
            "O arquivo foi descartado. Se a fonte publicou um build novo, rode "
            "com --update para re-fixar o manifesto (e confira a mudança antes de commitar)."
        )
    return actual


def extract_tool(zip_path: Path, tool: str, plat: str, dest: Path) -> None:
    """Extrai ``tool`` de dentro do zip para ``dest``.

    Os dois upstreams empacotam diferente: martin-riedl põe o executável na raiz
    do zip, BtbN põe em ``ffmpeg-<versao>/bin/``. Em vez de codificar os dois
    layouts, procura pelo nome de arquivo.
    """
    wanted = tool_filename(tool, plat)
    with zipfile.ZipFile(zip_path) as archive:
        matches = [n for n in archive.namelist() if Path(n).name == wanted]
        if not matches:
            raise RuntimeError(f"{zip_path.name} não contém {wanted}")
        # O caminho mais curto é o executável em si, não algo aninhado em doc/exemplo.
        member = min(matches, key=len)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
    make_executable(dest)


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def lipo_create(parts: list[Path], dest: Path) -> None:
    subprocess.run(
        ["lipo", "-create", "-output", str(dest), *[str(p) for p in parts]],
        check=True,
        capture_output=True,
    )
    make_executable(dest)


# --------------------------------------------------------------------------- #
# Manifesto
# --------------------------------------------------------------------------- #

def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise SystemExit(
            f"Manifesto não encontrado: {MANIFEST_PATH}\n"
            "Rode com --update para gerá-lo a partir dos builds mais novos."
        )
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def save_manifest(manifest: dict) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def resolve_url(url: str) -> str:
    """Segue redirects sem baixar o corpo, para descobrir a URL fixa do build."""
    with _open(url) as response:
        return response.geturl()


def fetch_published_sha256(url: str) -> str | None:
    """martin-riedl publica ``<arquivo>.sha256`` no formato do ``shasum``."""
    try:
        with _open(f"{url}.sha256", timeout=60) as response:
            return response.read().decode("utf-8").split()[0].strip()
    except (urllib.error.URLError, urllib.error.HTTPError, IndexError):
        return None


# --------------------------------------------------------------------------- #
# --update: descobre o build mais novo e re-fixa o manifesto
# --------------------------------------------------------------------------- #

def discover_macos(tmp: Path) -> dict:
    config = UPSTREAM["macos"]
    components = []
    version = None
    for arch, path in config["arches"].items():
        for tool in TOOLS:
            url = resolve_url(config["redirect"].format(path=path, tool=tool))
            local = tmp / f"{arch}-{tool}.zip"
            published = fetch_published_sha256(url)
            actual = download(url, local, expected_sha256=published)
            if published:
                print("      sha256 confere com o .sha256 publicado pela fonte")
            components.append(
                {"arch": arch, "tool": tool, "url": url, "sha256": actual}
            )
            version = version or version_from_url(url)
    return {
        "source": "ffmpeg.martin-riedl.de",
        "ffmpeg_version": version,
        "universal": True,
        "components": components,
    }


def version_from_url(url: str) -> str | None:
    # .../download/macos/arm64/1785863997_9.0/ffmpeg.zip -> 9.0
    match = re.search(r"/\d+_([0-9][^/]*)/", url)
    return match.group(1) if match else None


def discover_windows(tmp: Path) -> dict:
    config = UPSTREAM["windows"]
    with _open(config["api"], timeout=60) as response:
        releases = json.load(response)

    pattern = re.compile(config["asset_re"])
    for release in releases:
        # Tags datadas têm URL de asset estável; a tag "latest" é rolante e o
        # hash fixado deixaria de bater no dia seguinte.
        if release["tag_name"] == "latest":
            continue
        for asset in release["assets"]:
            if pattern.match(asset["name"]):
                url = asset["browser_download_url"]
                local = tmp / asset["name"]
                actual = download(url, local)
                return {
                    "source": "github.com/BtbN/FFmpeg-Builds",
                    "release_tag": release["tag_name"],
                    "ffmpeg_version": version_from_asset(asset["name"]),
                    "universal": False,
                    "components": [
                        {"arch": "x86_64", "tool": tool, "url": url, "sha256": actual}
                        for tool in TOOLS
                    ],
                }
    raise RuntimeError("Nenhum asset win64-gpl do trilho n8.x encontrado no BtbN/FFmpeg-Builds")


def version_from_asset(name: str) -> str | None:
    match = re.search(r"ffmpeg-n([0-9][0-9.]*)", name)
    return match.group(1) if match else None


def cmd_update(platforms: list[str]) -> int:
    manifest = {}
    if MANIFEST_PATH.exists():
        manifest = load_manifest()
    manifest.setdefault("_comment", (
        "Gerado por fetch_ffmpeg.py --update. Os SHA-256 são o contrato: o script "
        "recusa instalar qualquer download que não bata com o hash aqui fixado."
    ))
    manifest.setdefault("targets", {})

    with tempfile.TemporaryDirectory(prefix="ffmpeg-update-") as tmpdir:
        tmp = Path(tmpdir)
        for plat in platforms:
            print(f"==> Descobrindo build mais novo para {plat}")
            if plat == "macos":
                manifest["targets"][plat] = discover_macos(tmp)
            elif plat == "windows":
                manifest["targets"][plat] = discover_windows(tmp)
            else:
                print(f"    plataforma sem fonte configurada: {plat}", file=sys.stderr)
                return 2
            print(f"    fixado: ffmpeg {manifest['targets'][plat]['ffmpeg_version']}")

    save_manifest(manifest)
    print(f"\nManifesto atualizado: {MANIFEST_PATH}")
    print("Confira o diff antes de commitar — ele é o que autoriza os binários.")
    return 0


# --------------------------------------------------------------------------- #
# Instalação
# --------------------------------------------------------------------------- #

def manual_instructions(target: dict, plat: str, bin_dir: Path) -> str:
    lines = [
        "Não foi possível baixar automaticamente. Para fazer à mão:",
        "",
    ]
    for component in target["components"]:
        lines.append(f"  1. Baixe {component['url']}")
        lines.append(f"     SHA-256 esperado: {component['sha256']}")
        if plat == "macos":
            lines.append(
                f"     Confira com:  shasum -a 256 <arquivo.zip>"
            )
        lines.append("")
    if plat == "macos" and target.get("universal"):
        lines += [
            "  2. Descompacte cada zip e junte as arquiteturas:",
            "",
            "       lipo -create -output ffmpeg  <arm64>/ffmpeg  <x86_64>/ffmpeg",
            "       lipo -create -output ffprobe <arm64>/ffprobe <x86_64>/ffprobe",
            "",
        ]
    else:
        lines += ["  2. Descompacte os executáveis do zip.", ""]
    lines += [
        f"  3. Coloque os arquivos em {bin_dir} e marque como executáveis:",
        "",
        f"       chmod +x {bin_dir / 'ffmpeg'} {bin_dir / 'ffprobe'}",
        "",
        "  4. Rode novamente com --check para validar.",
    ]
    return "\n".join(lines)


def install(plat: str, bin_dir: Path, manifest: dict, force: bool) -> bool:
    """Baixa, monta e instala os binários. Devolve True se instalou."""
    target = manifest["targets"].get(plat)
    if target is None:
        raise SystemExit(f"Manifesto não tem entrada para a plataforma '{plat}'.")

    print(f"==> Instalando FFmpeg {target['ffmpeg_version']} ({target['source']}) em {bin_dir}")

    existing = [bin_dir / tool_filename(t, plat) for t in TOOLS]
    if all(p.exists() for p in existing) and not force:
        # Presente não é o mesmo que bom: era exatamente este o caso do binário
        # dinâmico do Homebrew que vivia versionado aqui. Só pula o download se o
        # que está instalado passar na validação.
        if plat == platform_key() and validate(bin_dir, plat):
            print("    binários já presentes, mas reprovaram na validação; rebaixando")
        else:
            print("    binários já presentes e válidos (use --force para rebaixar)")
            return False

    with tempfile.TemporaryDirectory(prefix="ffmpeg-fetch-") as tmpdir:
        tmp = Path(tmpdir)
        staged: dict[str, list[Path]] = {tool: [] for tool in TOOLS}

        for component in target["components"]:
            # Nomear o cache pela URL, e não por (arch, tool): no Windows os dois
            # executáveis vêm do mesmo zip de 160 MB, que seria baixado duas vezes.
            archive = tmp / (hashlib.sha256(component["url"].encode()).hexdigest()[:16] + ".zip")
            if not archive.exists():
                download(component["url"], archive, expected_sha256=component["sha256"])
            extracted = tmp / f"{component['arch']}-{tool_filename(component['tool'], plat)}"
            extract_tool(archive, component["tool"], plat, extracted)
            staged[component["tool"]].append(extracted)

        bin_dir.mkdir(parents=True, exist_ok=True)
        for tool in TOOLS:
            parts = staged[tool]
            if not parts:
                raise SystemExit(
                    f"Manifesto não tem nenhum componente para '{tool}' em {plat}. "
                    "Rode com --update para regerá-lo."
                )
            final = tmp / f"final-{tool_filename(tool, plat)}"
            if plat == "macos" and target.get("universal") and len(parts) > 1:
                print(f"    juntando {len(parts)} arquiteturas em {tool} universal2 (lipo)")
                lipo_create(parts, final)
            else:
                shutil.copy2(parts[0], final)
                make_executable(final)

            destination = bin_dir / tool_filename(tool, plat)
            # Substituição atômica: um binário meio escrito em desktop/bin é
            # pior que binário nenhum, porque falha em runtime e não no build.
            temp_dest = destination.with_name(destination.name + ".new")
            shutil.copy2(final, temp_dest)
            make_executable(temp_dest)
            os.replace(temp_dest, destination)
            print(f"    instalado {destination} ({human_mb(destination.stat().st_size)})")

    return True


# --------------------------------------------------------------------------- #
# Validação
# --------------------------------------------------------------------------- #

def run_tool(path: Path, args: list[str]) -> str:
    result = subprocess.run(
        [str(path), *args], capture_output=True, text=True, timeout=120
    )
    return result.stdout + result.stderr


def parse_version(text: str) -> tuple[int, ...] | None:
    # Cada binário se identifica com o próprio nome ("ffmpeg version 9.0",
    # "ffprobe version 9.0"), então casar só "ffmpeg" reprovaria o ffprobe.
    match = re.search(r"\bff(?:mpeg|probe) version n?(\d+)\.(\d+)", text)
    if not match:
        return None
    return tuple(int(g) for g in match.groups())


def dynamic_deps(path: Path) -> list[str]:
    """Dependências dinâmicas fora do sistema base do macOS.

    ``/usr/lib`` e ``/System`` sempre existem em qualquer Mac, então dependência
    delas não quebra nada. Qualquer outra coisa (típico: ``/usr/local/opt/...``
    do Homebrew) significa que o binário não é realmente portátil.
    """
    try:
        output = subprocess.run(
            ["otool", "-L", str(path)], capture_output=True, text=True, timeout=60
        ).stdout
    except FileNotFoundError:
        raise SystemExit(
            "'otool' não encontrado — as Command Line Tools do Xcode são necessárias "
            "para verificar se o binário é estático.\n"
            "Instale com:  xcode-select --install"
        ) from None
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


def architectures(path: Path) -> list[str]:
    try:
        output = subprocess.run(
            ["lipo", "-archs", str(path)], capture_output=True, text=True, timeout=60
        ).stdout
    except FileNotFoundError:
        raise SystemExit(
            "'lipo' não encontrado — as Command Line Tools do Xcode são necessárias "
            "para montar e verificar o binário universal.\n"
            "Instale com:  xcode-select --install"
        ) from None
    return output.split()


def validate(bin_dir: Path, plat: str) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = tudo certo)."""
    problems: list[str] = []

    for tool in TOOLS:
        path = bin_dir / tool_filename(tool, plat)
        if not path.exists():
            problems.append(f"{path} não existe")
            continue
        if not os.access(path, os.X_OK):
            problems.append(f"{path} não é executável")
            continue

        if plat == "macos":
            external = dynamic_deps(path)
            if external:
                problems.append(
                    f"{tool} depende de bibliotecas fora de /usr/lib e /System "
                    f"(não é estático): {', '.join(external)}"
                )
            archs = architectures(path)
            if platform.machine() not in archs:
                problems.append(
                    f"{tool} não tem a arquitetura desta máquina "
                    f"({platform.machine()}); tem apenas: {', '.join(archs) or '?'}"
                )

        # Só executa o binário se ele tiver a arquitetura certa — senão o erro
        # seria "não pode executar" e esconderia o problema real, já reportado acima.
        if plat != platform_key() or (plat == "macos" and platform.machine() not in architectures(path)):
            continue

        version_text = run_tool(path, ["-hide_banner", "-version"])
        version = parse_version(version_text)
        if version is None:
            problems.append(f"{tool} não reportou versão reconhecível")
        elif version < MIN_VERSION:
            problems.append(
                f"{tool} versão {'.'.join(map(str, version))} é menor que a mínima "
                f"{'.'.join(map(str, MIN_VERSION))}"
            )

        if tool == "ffmpeg":
            encoders = run_tool(path, ["-hide_banner", "-encoders"])
            required = list(REQUIRED_ENCODERS)
            if plat == "macos":
                required += list(REQUIRED_ENCODERS_MACOS)
            for encoder in required:
                if not re.search(rf"^\s*\S+\s+{re.escape(encoder)}\s", encoders, re.M):
                    problems.append(f"encoder ausente: {encoder}")

            filters = run_tool(path, ["-hide_banner", "-filters"])
            for filt in REQUIRED_FILTERS:
                if not re.search(rf"^\s*\S+\s+{re.escape(filt)}\s", filters, re.M):
                    problems.append(f"filtro ausente: {filt}")

    return problems


def describe(bin_dir: Path, plat: str) -> None:
    for tool in TOOLS:
        path = bin_dir / tool_filename(tool, plat)
        if not path.exists():
            continue
        bits = [human_mb(path.stat().st_size)]
        if plat == "macos":
            bits.append("+".join(architectures(path)) or "?")
            bits.append("estático" if not dynamic_deps(path) else "DINÂMICO")
        version = parse_version(run_tool(path, ["-hide_banner", "-version"])) if plat == platform_key() else None
        if version:
            bits.append("v" + ".".join(map(str, version)))
        print(f"    {tool:<8} {'  '.join(bits)}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Baixa e valida os binários estáticos de FFmpeg/FFprobe do app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--platform", choices=sorted(UPSTREAM), default=None,
        help="plataforma alvo (padrão: a atual)",
    )
    parser.add_argument(
        "--dest", type=Path, default=DEFAULT_BIN_DIR,
        help=f"onde instalar (padrão: {DEFAULT_BIN_DIR})",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="não baixa nada; só valida os binários já instalados",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="rebaixa e substitui mesmo se os binários já existirem",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="descobre o build mais novo e re-fixa o manifesto (não instala)",
    )
    args = parser.parse_args(argv)

    plat = args.platform or platform_key()

    if args.update:
        return cmd_update([plat] if args.platform else sorted(UPSTREAM))

    bin_dir = args.dest.resolve()

    if not args.check:
        manifest = load_manifest()
        try:
            install(plat, bin_dir, manifest, force=args.force)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            print(f"\nFalha ao baixar: {exc}\n", file=sys.stderr)
            print(manual_instructions(manifest["targets"][plat], plat, bin_dir), file=sys.stderr)
            print("", file=sys.stderr)
            # Segue para a validação: se já houver binário utilizável em
            # desktop/bin, o build pode continuar mesmo sem rede.

    print(f"==> Validando {bin_dir}")
    describe(bin_dir, plat)
    problems = validate(bin_dir, plat)
    if problems:
        # stdout e stderr têm buffers separados; sem o flush, a lista de problemas
        # aparece antes do relatório a que ela se refere.
        sys.stdout.flush()
        print("\nProblemas encontrados:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("    ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
