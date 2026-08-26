#!/usr/bin/env python3
"""
Diff de dois JSONs de benchmark: imprime a tabela de delta e marca regressões.

Uso:
    python desktop/tests/bench/compare_bench.py baseline.json candidato.json

Sai com código 1 se alguma regressão passar do limiar, o que permite usar o
comando direto num check de CI.

Uma otimização de compressão quase sempre troca uma coisa por outra, então a
tabela mostra tempo, tamanho e qualidade lado a lado: ficar 30% mais rápido
perdendo 4 pontos de VMAF não é ganho, é escolha — e precisa aparecer.
"""

import argparse
import json
import sys
from pathlib import Path

# Limiares padrão. Acima do ruído típico de repetição na mesma máquina
# (~2-3% no wall time), mas apertados o bastante para pegar degradação real.
DEFAULT_TIME_PCT = 5.0        # ficar mais lento que isso (%) é regressão
DEFAULT_SIZE_PCT = 2.0        # arquivo maior que isso (%) é regressão
DEFAULT_VMAF_DROP = 0.5       # queda de VMAF médio em pontos
DEFAULT_LOW_DROP = 1.0        # queda de VMAF 1% low em pontos


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Compara dois resultados de benchmark e aponta regressões.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('baseline', type=Path, help='JSON de referência (o baseline).')
    parser.add_argument('candidate', type=Path, help='JSON novo, a ser avaliado.')
    parser.add_argument('--time-pct', type=float, default=DEFAULT_TIME_PCT)
    parser.add_argument('--size-pct', type=float, default=DEFAULT_SIZE_PCT)
    parser.add_argument('--vmaf-drop', type=float, default=DEFAULT_VMAF_DROP)
    parser.add_argument('--low-drop', type=float, default=DEFAULT_LOW_DROP)
    parser.add_argument('--json', action='store_true',
                        help='Emite o diff como JSON em vez de tabela.')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        baseline = _load(args.baseline)
        candidate = _load(args.candidate)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERRO ao ler os JSONs: {exc}", file=sys.stderr)
        return 2

    warnings = compare_environments(baseline, candidate)
    rows = build_rows(baseline, candidate, args)

    if args.json:
        json.dump(
            {'warnings': warnings, 'rows': rows,
             'thresholds': {'time_pct': args.time_pct, 'size_pct': args.size_pct,
                            'vmaf_drop': args.vmaf_drop, 'low_drop': args.low_drop}},
            sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write('\n')
    else:
        _print_report(baseline, candidate, warnings, rows, args)

    return 1 if any(row['regressions'] for row in rows) else 0


def _load(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def compare_environments(baseline: dict, candidate: dict) -> list:
    """Avisa sobre diferenças que tornam os dois runs não-comparáveis.

    Comparar tempos entre máquinas, arquiteturas ou builds de ffmpeg
    diferentes não mede a mudança de código: mede a diferença de ambiente.
    """
    warnings = []

    def check(label, base_value, cand_value):
        if base_value != cand_value:
            warnings.append(f"{label}: baseline={base_value!r} vs candidato={cand_value!r}")

    base_env = baseline.get('environment', {})
    cand_env = candidate.get('environment', {})
    base_platform = base_env.get('platform', {})
    cand_platform = cand_env.get('platform', {})

    check('sistema', base_platform.get('system'), cand_platform.get('system'))
    check('arquitetura', base_platform.get('machine'), cand_platform.get('machine'))
    check('núcleos lógicos', base_env.get('cpu_logical_cores'), cand_env.get('cpu_logical_cores'))
    check('versão do ffmpeg',
          (base_env.get('ffmpeg') or {}).get('version'),
          (cand_env.get('ffmpeg') or {}).get('version'))
    check('ffmpeg embutido',
          (base_env.get('ffmpeg') or {}).get('is_bundled'),
          (cand_env.get('ffmpeg') or {}).get('is_bundled'))
    # Software e hardware produzem tamanhos e VMAF diferentes por natureza.
    # Comparar os dois é legítimo (é o experimento), mas quem lê a tabela
    # precisa saber que está vendo isso, e não uma otimização de código.
    check('modo de encoder',
          (base_env.get('encoder') or {}).get('mode'),
          (cand_env.get('encoder') or {}).get('mode'))
    check('modo quick', (baseline.get('run') or {}).get('quick'),
          (candidate.get('run') or {}).get('quick'))
    check('vmaf n_subsample', (baseline.get('run') or {}).get('vmaf_n_subsample'),
          (candidate.get('run') or {}).get('vmaf_n_subsample'))

    # Fontes diferentes = vídeos diferentes: nenhum número é comparável.
    base_prints = {source['spec']['name']: source.get('fingerprint')
                   for source in baseline.get('sources', [])}
    cand_prints = {source['spec']['name']: source.get('fingerprint')
                   for source in candidate.get('sources', [])}
    for name, fingerprint in base_prints.items():
        if name in cand_prints and cand_prints[name] != fingerprint:
            warnings.append(
                f"fonte {name!r} foi gerada com receita diferente "
                f"({fingerprint} vs {cand_prints[name]}) — números não comparáveis")

    return warnings


def build_rows(baseline: dict, candidate: dict, args) -> list:
    """Casa as medições por (fonte, perfil) e calcula os deltas."""
    base_index = {(item['source'], item['profile']): item for item in baseline.get('results', [])}
    cand_index = {(item['source'], item['profile']): item for item in candidate.get('results', [])}

    rows = []
    for key in sorted(set(base_index) | set(cand_index)):
        base_item = base_index.get(key)
        cand_item = cand_index.get(key)
        source, profile = key

        if base_item is None or cand_item is None:
            rows.append({
                'source': source, 'profile': profile,
                'status': 'ausente no candidato' if cand_item is None else 'novo no candidato',
                'metrics': {}, 'regressions': [],
            })
            continue

        if not (base_item.get('ok') and cand_item.get('ok')):
            rows.append({
                'source': source, 'profile': profile,
                'status': 'falhou em um dos runs',
                'metrics': {},
                'regressions': ['compressão falhou'] if not cand_item.get('ok') else [],
            })
            continue

        metrics = {
            'wall_time_s': _delta(base_item.get('wall_time_s'), cand_item.get('wall_time_s')),
            'output_bytes': _delta(base_item.get('output_bytes'), cand_item.get('output_bytes')),
            'encode_fps_avg': _delta(base_item.get('encode_fps_avg'),
                                     cand_item.get('encode_fps_avg')),
            'peak_rss_bytes': _delta((base_item.get('rss') or {}).get('peak_rss_bytes'),
                                     (cand_item.get('rss') or {}).get('peak_rss_bytes')),
            'vmaf_mean': _delta(_vmaf(base_item, 'mean'), _vmaf(cand_item, 'mean')),
            'vmaf_low_1pct': _delta(_vmaf(base_item, 'low_1pct'), _vmaf(cand_item, 'low_1pct')),
            'psnr_y_mean': _delta(_vmaf(base_item, 'psnr_y_mean'), _vmaf(cand_item, 'psnr_y_mean')),
        }

        regressions = []
        time_delta = metrics['wall_time_s']
        if time_delta['pct'] is not None and time_delta['pct'] > args.time_pct:
            regressions.append(f"{time_delta['pct']:+.1f}% mais lento")

        size_delta = metrics['output_bytes']
        if size_delta['pct'] is not None and size_delta['pct'] > args.size_pct:
            regressions.append(f"arquivo {size_delta['pct']:+.1f}% maior")

        vmaf_delta = metrics['vmaf_mean']
        if vmaf_delta['abs'] is not None and vmaf_delta['abs'] < -args.vmaf_drop:
            regressions.append(f"VMAF {vmaf_delta['abs']:+.2f}")

        low_delta = metrics['vmaf_low_1pct']
        if low_delta['abs'] is not None and low_delta['abs'] < -args.low_drop:
            regressions.append(f"VMAF 1% low {low_delta['abs']:+.2f}")

        rows.append({
            'source': source, 'profile': profile,
            'status': 'ok', 'metrics': metrics, 'regressions': regressions,
        })

    return rows


def _vmaf(item: dict, key: str):
    vmaf = item.get('vmaf') or {}
    return vmaf.get(key) if vmaf.get('ok') else None


def _delta(base_value, cand_value) -> dict:
    """Delta absoluto e percentual, tolerando valores ausentes."""
    if not isinstance(base_value, (int, float)) or not isinstance(cand_value, (int, float)):
        return {'base': base_value, 'cand': cand_value, 'abs': None, 'pct': None}
    absolute = cand_value - base_value
    percent = (absolute / base_value * 100) if base_value else None
    return {
        'base': base_value,
        'cand': cand_value,
        'abs': round(absolute, 4),
        'pct': round(percent, 3) if percent is not None else None,
    }


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------

HEADERS = ['fonte', 'perfil', 'tempo (s)', 'tamanho (MB)', 'VMAF', '1% low', 'RSS (MB)', '']


def _print_report(baseline: dict, candidate: dict, warnings: list, rows: list, args):
    print('=' * 100)
    print('Comparação de benchmark')
    print('=' * 100)
    print(f"baseline  : {_describe(baseline)}")
    print(f"candidato : {_describe(candidate)}")
    print()

    if warnings:
        print('AVISOS DE AMBIENTE (os deltas abaixo podem não significar nada):')
        for warning in warnings:
            print(f"  ! {warning}")
        print()

    table = [HEADERS]
    for row in rows:
        if row['status'] != 'ok':
            table.append([row['source'], row['profile'], row['status'], '', '', '', '', '!'])
            continue
        metrics = row['metrics']
        table.append([
            row['source'],
            row['profile'],
            _fmt_pct(metrics['wall_time_s'], 's', lower_is_better=True),
            _fmt_pct(metrics['output_bytes'], 'MB', lower_is_better=True, scale=1 / (1024 * 1024)),
            _fmt_abs(metrics['vmaf_mean']),
            _fmt_abs(metrics['vmaf_low_1pct']),
            _fmt_pct(metrics['peak_rss_bytes'], 'MB', lower_is_better=True,
                     scale=1 / (1024 * 1024)),
            'REG' if row['regressions'] else 'ok',
        ])

    _print_table(table)

    regressed = [row for row in rows if row['regressions']]
    print()
    if regressed:
        print(f"REGRESSÕES ({len(regressed)} de {len(rows)}):")
        for row in regressed:
            print(f"  - {row['source']} / {row['profile']}: {'; '.join(row['regressions'])}")
        print()
        print(f"Limiares: tempo > +{args.time_pct}% | tamanho > +{args.size_pct}% | "
              f"VMAF < -{args.vmaf_drop} | 1% low < -{args.low_drop}")
    else:
        print(f"Nenhuma regressão acima dos limiares (tempo +{args.time_pct}%, "
              f"tamanho +{args.size_pct}%, VMAF -{args.vmaf_drop}, 1% low -{args.low_drop}).")


def _describe(payload: dict) -> str:
    run = payload.get('run') or {}
    env = payload.get('environment') or {}
    platform_info = env.get('platform') or {}
    ffmpeg = env.get('ffmpeg') or {}
    label = f"{run.get('label')} " if run.get('label') else ''
    return (f"{label}{run.get('timestamp_utc')} | {platform_info.get('system')}/"
            f"{platform_info.get('machine')} | ffmpeg {ffmpeg.get('version')} | "
            f"{'quick' if run.get('quick') else 'completo'}")


def _fmt_pct(delta: dict, unit: str, lower_is_better: bool, scale: float = 1.0) -> str:
    if delta['base'] is None or delta['cand'] is None:
        return '-'
    base = delta['base'] * scale
    cand = delta['cand'] * scale
    if delta['pct'] is None:
        return f"{base:.1f}->{cand:.1f}{unit}"
    marker = _marker(delta['pct'], lower_is_better)
    return f"{base:.1f}->{cand:.1f} ({delta['pct']:+.1f}%){marker}"


def _fmt_abs(delta: dict) -> str:
    if delta['base'] is None or delta['cand'] is None:
        return '-'
    marker = _marker(delta['abs'], lower_is_better=False)
    return f"{delta['base']:.2f}->{delta['cand']:.2f} ({delta['abs']:+.2f}){marker}"


def _marker(value: float, lower_is_better: bool) -> str:
    """Seta de direção: para baixo é bom em tempo/tamanho, ruim em qualidade."""
    if abs(value) < 1e-9:
        return ' ='
    improved = (value < 0) if lower_is_better else (value > 0)
    return ' +' if improved else ' -'


def _print_table(table: list):
    widths = [max(len(str(row[col])) for row in table) for col in range(len(table[0]))]
    for index, row in enumerate(table):
        line = '  '.join(str(cell).ljust(widths[col]) for col, cell in enumerate(row))
        print(line.rstrip())
        if index == 0:
            print('-' * len(line.rstrip()))


if __name__ == '__main__':
    sys.exit(main())
