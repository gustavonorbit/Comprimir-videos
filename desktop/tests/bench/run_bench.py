#!/usr/bin/env python3
"""
Harness de benchmark do pipeline de compressão do app desktop.

Roda o pipeline REAL (``VideoCompressor.compress_video``, o mesmo código que
o botão de exportar usa) sobre vídeos REAIS gerados com ffmpeg, e grava um
JSON com tempo, tamanho, throughput, memória e qualidade (VMAF/PSNR).

Isto é uma linha de base: serve para provar ganho de uma otimização futura e,
principalmente, para flagrar a regressão de qualidade que costuma vir junto.

Uso:
    python desktop/tests/bench/run_bench.py --quick
    python desktop/tests/bench/run_bench.py
    python desktop/tests/bench/run_bench.py --sources screen_1080p30 --profiles Balanceado

Ver README.md nesta pasta.
"""

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
DESKTOP_DIR = BENCH_DIR.parents[1]
sys.path.insert(0, str(BENCH_DIR))
sys.path.insert(0, str(DESKTOP_DIR))

from bench_lib import (  # noqa: E402
    PeakRssSampler,
    collect_environment,
    measure_vmaf,
    probe_media,
)
from bench_sources import ensure_sources, get_sources  # noqa: E402
from compressor import VideoCompressor  # noqa: E402
import encoder_caps  # noqa: E402

SCHEMA_VERSION = 1
DEFAULT_MEDIA_DIR = BENCH_DIR / 'media'
DEFAULT_RESULTS_DIR = BENCH_DIR / 'results'

# No modo --quick o VMAF pontua 1 frame a cada N. A média mal se move (medido:
# diferença < 0.05 ponto com n_subsample=3), mas o 1% low fica mais grosseiro —
# por isso o modo completo sempre usa 1.
QUICK_VMAF_SUBSAMPLE = 3


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Benchmark do pipeline de compressão (desktop).',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--quick', action='store_true',
                        help='Fontes curtas e VMAF subamostrado; alvo < 10 min.')
    parser.add_argument('--sources', nargs='+', default=None,
                        help='Subconjunto de fontes pelo nome (padrão: todas).')
    parser.add_argument('--profiles', nargs='+', default=None,
                        help='Subconjunto de perfis (padrão: os 4 de COMPRESSION_PROFILES).')
    parser.add_argument('--media-dir', type=Path, default=DEFAULT_MEDIA_DIR,
                        help='Onde ficam os vídeos de origem (reaproveitados entre runs).')
    parser.add_argument('--results-dir', type=Path, default=DEFAULT_RESULTS_DIR,
                        help='Onde gravar o JSON de resultado.')
    parser.add_argument('--out', type=Path, default=None,
                        help='Caminho exato do JSON (sobrepõe --results-dir).')
    parser.add_argument('--label', default=None,
                        help='Rótulo livre gravado no JSON (ex: "baseline", "pr-42").')
    parser.add_argument('--regen-sources', action='store_true',
                        help='Regera os vídeos de origem mesmo se já existirem.')
    parser.add_argument('--keep-outputs', action='store_true',
                        help='Não apaga os vídeos comprimidos após medir.')
    parser.add_argument('--no-vmaf', action='store_true',
                        help='Pula a medição de qualidade (só tempo/tamanho/memória).')
    parser.add_argument('--hardware', action='store_true',
                        help='detecta e usa encoders de hardware (o padrão é medir só software, '
                             'que é o caminho garantido em qualquer máquina)')
    parser.add_argument('--vmaf-subsample', type=int, default=None,
                        help='n_subsample do libvmaf (1 = todos os frames).')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    started_at = datetime.now(timezone.utc)
    run_started = time.perf_counter()

    compressor = VideoCompressor()
    if not compressor.is_ffmpeg_available():
        print(f"ERRO: ffmpeg não utilizável em {compressor.ffmpeg_path}", file=sys.stderr)
        return 2
    if not compressor.is_ffprobe_available():
        print(f"ERRO: ffprobe não utilizável em {compressor.ffprobe_path}", file=sys.stderr)
        return 2

    environment = collect_environment(compressor.ffmpeg_path, compressor.ffprobe_path)

    # O encoder escolhido muda tempo, tamanho E qualidade, então entra no
    # ambiente: dois runs com encoders diferentes não são comparáveis, e o
    # compare_bench precisa poder avisar.
    if args.hardware:
        caps = encoder_caps.detect_capabilities(compressor.ffmpeg_path)
        encoder_caps.set_capabilities_for_test(caps)
        environment['encoder'] = {
            'mode': 'hardware',
            'tier': caps.tier,
            'usable': list(caps.usable_encoders),
            'quality_modes': dict(caps.quality_modes),
        }
    else:
        # Sem capabilities detectadas o policy devolve software — o mesmo que
        # acontece no app enquanto o probe de background não terminou.
        encoder_caps.set_capabilities_for_test(None)
        environment['encoder'] = {'mode': 'software'}
    measure_quality = not args.no_vmaf
    if measure_quality and not environment['ffmpeg'].get('has_libvmaf'):
        print("AVISO: este ffmpeg não tem libvmaf; seguindo sem medir qualidade.",
              file=sys.stderr)
        measure_quality = False

    vmaf_subsample = args.vmaf_subsample or (QUICK_VMAF_SUBSAMPLE if args.quick else 1)

    specs = get_sources(quick=args.quick)
    if args.sources:
        wanted = set(args.sources)
        unknown = wanted - {spec.name for spec in specs}
        if unknown:
            print(f"ERRO: fonte desconhecida: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        specs = [spec for spec in specs if spec.name in wanted]

    profiles = args.profiles or list(VideoCompressor.COMPRESSION_PROFILES)
    unknown_profiles = set(profiles) - set(VideoCompressor.COMPRESSION_PROFILES)
    if unknown_profiles:
        print(f"ERRO: perfil desconhecido: {', '.join(sorted(unknown_profiles))}", file=sys.stderr)
        return 2

    _print_header(environment, specs, profiles, args.quick, vmaf_subsample)

    print("Fontes:")
    sources = ensure_sources(
        compressor.ffmpeg_path,
        compressor.ffprobe_path,
        specs,
        args.media_dir,
        force=args.regen_sources,
        log=print,
    )

    output_dir = args.media_dir / 'out'
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(sources) * len(profiles)
    index = 0
    print(f"\nMedições ({total} combinações):")
    for source in sources:
        for profile in profiles:
            index += 1
            print(f"  [{index}/{total}] {source['spec']['name']} / {profile} ...",
                  end='', flush=True)
            measurement = run_one(
                compressor=compressor,
                source=source,
                profile=profile,
                output_dir=output_dir,
                measure_quality=measure_quality,
                vmaf_subsample=vmaf_subsample,
                keep_output=args.keep_outputs,
            )
            results.append(measurement)
            print(f" {_summarize(measurement)}")

    payload = {
        'schema_version': SCHEMA_VERSION,
        'run': {
            'label': args.label,
            'timestamp_utc': started_at.isoformat(),
            'quick': args.quick,
            'profiles': profiles,
            'vmaf_measured': measure_quality,
            'vmaf_n_subsample': vmaf_subsample,
            'total_elapsed_s': round(time.perf_counter() - run_started, 3),
            'command': ' '.join(sys.argv),
        },
        'environment': environment,
        'sources': sources,
        'results': results,
    }

    out_path = args.out or _default_out_path(args.results_dir, started_at)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write('\n')

    failures = [item for item in results if not item['ok']]
    print(f"\nJSON: {out_path}")
    print(f"Tempo total: {payload['run']['total_elapsed_s']:.1f}s "
          f"({payload['run']['total_elapsed_s'] / 60:.1f} min)")
    if failures:
        print(f"ATENÇÃO: {len(failures)} de {total} compressões falharam.", file=sys.stderr)
        for item in failures:
            print(f"  - {item['source']} / {item['profile']}: {item['message']}", file=sys.stderr)
        return 1
    return 0


def run_one(
    compressor: VideoCompressor,
    source: dict,
    profile: str,
    output_dir: Path,
    measure_quality: bool,
    vmaf_subsample: int,
    keep_output: bool,
) -> dict:
    """Uma compressão medida: tempo, tamanho, throughput, memória e qualidade."""
    source_name = source['spec']['name']
    input_path = source['path']
    input_bytes = source['media']['size_bytes']
    safe_profile = profile.replace(' ', '_').lower()
    output_path = output_dir / f"{source_name}__{safe_profile}.mp4"
    config = VideoCompressor.COMPRESSION_PROFILES[profile]

    # Zera o processo anterior: o sampler identifica o ffmpeg desta rodada
    # esperando um pid NOVO aparecer em compressor.process, e um objeto
    # remanescente da rodada anterior o faria medir um processo já morto.
    compressor.process = None

    def current_pid():
        process = compressor.process
        return getattr(process, 'pid', None) if process is not None else None

    started = time.perf_counter()
    with PeakRssSampler(current_pid) as sampler:
        ok, message = compressor.compress_video(
            input_path,
            str(output_path),
            profile=profile,
            resolution=0,       # mantém a resolução original
            remove_audio=False,
            rotation=0,         # sem rotação manual: a de metadados é a do arquivo
        )
    wall_time_s = time.perf_counter() - started

    plan = compressor.last_encode_plan
    measurement = {
        'source': source_name,
        'profile': profile,
        'crf': config['crf'],
        'preset': config['preset'],
        # O que REALMENTE rodou, já contando um eventual fallback de hardware
        # para software: sem isto, um run "de hardware" onde tudo caiu para
        # libx264 seria indistinguível de um ganho de verdade.
        'encoder': getattr(plan, 'encoder', None),
        'encoder_is_hardware': getattr(plan, 'is_hardware', None),
        'encoder_args': list(getattr(plan, 'video_args', ())),
        'ok': bool(ok),
        'message': message,
        'wall_time_s': round(wall_time_s, 3),
        'input_bytes': input_bytes,
        'output_bytes': None,
        'size_ratio': None,
        'compression_ratio_pct': None,
        'encode_fps_avg': None,
        'output_media': None,
        'rss': sampler.result(),
        'vmaf': None,
    }

    if not ok or not output_path.exists():
        measurement['ok'] = False
        return measurement

    output_media = probe_media(compressor.ffprobe_path, str(output_path))
    output_bytes = output_media['size_bytes']
    measurement['output_media'] = output_media
    measurement['output_bytes'] = output_bytes
    measurement['size_ratio'] = round(output_bytes / input_bytes, 5) if input_bytes else None
    # Mesma convenção de utils.estimate_output_size: quanto do original sumiu.
    measurement['compression_ratio_pct'] = (
        round((input_bytes - output_bytes) / input_bytes * 100, 3) if input_bytes else None
    )
    # Throughput de encode derivado do que saiu de fato: frames do arquivo de
    # saída sobre o wall time do pipeline inteiro (inclui abrir/mux, não só o
    # laço do x264 — é o número que o usuário sente).
    if output_media['frames'] and wall_time_s > 0:
        measurement['encode_fps_avg'] = round(output_media['frames'] / wall_time_s, 2)

    if measure_quality:
        log_path = output_dir / f"{source_name}__{safe_profile}_vmaf.json"
        measurement['vmaf'] = measure_vmaf(
            compressor.ffmpeg_path,
            reference=input_path,
            distorted=str(output_path),
            log_path=str(log_path),
            n_subsample=vmaf_subsample,
            timeout=7200,
        )
        log_path.unlink(missing_ok=True)

    if not keep_output:
        output_path.unlink(missing_ok=True)

    return measurement


def _summarize(measurement: dict) -> str:
    if not measurement['ok']:
        return f"FALHOU ({measurement['message']})"
    parts = [
        f"{measurement['wall_time_s']:.1f}s",
        f"{measurement['output_bytes'] / 1024 / 1024:.1f}MB",
        f"{measurement['compression_ratio_pct']:.1f}% menor",
    ]
    if measurement['encode_fps_avg']:
        parts.append(f"{measurement['encode_fps_avg']:.0f}fps")
    vmaf = measurement.get('vmaf')
    if vmaf and vmaf.get('ok'):
        parts.append(f"VMAF {vmaf['mean']:.2f} (1% low {vmaf['low_1pct']:.2f})")
    elif vmaf:
        parts.append('VMAF ERRO')
    return ' | '.join(parts)


def _default_out_path(results_dir: Path, started_at: datetime) -> Path:
    timestamp = started_at.strftime('%Y%m%dT%H%M%SZ')
    tag = f"{platform.system()}-{platform.machine()}"
    return results_dir / f"{timestamp}_{tag}.json"


def _print_header(environment: dict, specs: list, profiles: list, quick: bool, subsample: int):
    ffmpeg = environment['ffmpeg']
    origem = 'embutido (desktop/bin)' if ffmpeg['is_bundled'] else 'do sistema'
    print("=" * 78)
    print(f"Benchmark do pipeline de compressão {'(quick)' if quick else '(completo)'}")
    print("=" * 78)
    print(f"Plataforma : {environment['platform']['system']} "
          f"{environment['platform']['release']} / {environment['platform']['machine']} "
          f"/ {environment['cpu_logical_cores']} núcleos lógicos")
    print(f"ffmpeg     : {ffmpeg['version']} [{origem}] {ffmpeg['path']}")
    print(f"libvmaf    : {'sim' if ffmpeg.get('has_libvmaf') else 'NÃO'} "
          f"(n_subsample={subsample})")
    print(f"Fontes     : {', '.join(spec.name for spec in specs)}")
    print(f"Perfis     : {', '.join(profiles)}")
    print()


if __name__ == '__main__':
    sys.exit(main())
