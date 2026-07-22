#!/usr/bin/env python3
"""
EXEMPLO: Como usar o Compressor de Vídeos programaticamente
Este script mostra como integrar a biblioteca em seus próprios projetos.
"""

import sys
import os
from pathlib import Path

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compressor import VideoCompressor
from utils import format_file_size, format_duration


def exemplo_basico():
    """Exemplo mais simples possível."""
    print("=" * 60)
    print("EXEMPLO 1: Uso Básico")
    print("=" * 60)
    
    compressor = VideoCompressor()
    
    # Verificar se FFmpeg está disponível
    if not compressor.is_ffmpeg_available():
        print("❌ FFmpeg não está instalado!")
        return
    
    print("✅ FFmpeg disponível")
    print()


def exemplo_leitura_info():
    """Exemplo: Ler informações de um vídeo."""
    print("=" * 60)
    print("EXEMPLO 2: Ler Informações do Vídeo")
    print("=" * 60)
    
    compressor = VideoCompressor()
    
    # Usar vídeo de teste
    test_video = "/tmp/test_video.mp4"
    
    if not os.path.exists(test_video):
        print(f"❌ Vídeo de teste não encontrado: {test_video}")
        return
    
    # Obter informações
    info = compressor.get_video_info(test_video)
    
    if info:
        print(f"📁 Arquivo: {Path(test_video).name}")
        print(f"📊 Resolução: {info['width']}x{info['height']}")
        print(f"⏱️  Duração: {format_duration(info['duration'])}")
        print(f"💾 Tamanho: {format_file_size(info['file_size'])}")
    else:
        print("❌ Não foi possível ler informações")
    
    print()


def exemplo_compressao_simples():
    """Exemplo: Comprimir vídeo com config padrão."""
    print("=" * 60)
    print("EXEMPLO 3: Compressão Simples")
    print("=" * 60)
    
    compressor = VideoCompressor()
    
    input_file = "/tmp/test_video.mp4"
    output_file = "/tmp/exemplo_comprimido.mp4"
    
    if not os.path.exists(input_file):
        print(f"❌ Arquivo não encontrado: {input_file}")
        return
    
    print(f"📁 Input: {input_file}")
    print(f"📁 Output: {output_file}")
    print()
    
    success, message = compressor.compress_video(
        input_file=input_file,
        output_file=output_file,
        profile="Balanceado"
    )
    
    print(f"{'✅' if success else '❌'} {message}")
    
    if success:
        inp_size = os.path.getsize(input_file)
        out_size = os.path.getsize(output_file)
        reduction = ((inp_size - out_size) / inp_size) * 100
        
        print(f"\n📊 Resultado:")
        print(f"   Original: {format_file_size(inp_size)}")
        print(f"   Final: {format_file_size(out_size)}")
        print(f"   Redução: {reduction:.1f}%")
    
    print()


def exemplo_compressao_com_progresso():
    """Exemplo: Comprimir com callback de progresso."""
    print("=" * 60)
    print("EXEMPLO 4: Compressão com Progresso")
    print("=" * 60)
    
    compressor = VideoCompressor()
    
    input_file = "/tmp/test_video.mp4"
    output_file = "/tmp/exemplo_com_progresso.mp4"
    
    if not os.path.exists(input_file):
        print(f"❌ Arquivo não encontrado: {input_file}")
        return
    
    def progresso(percent):
        # Criar barra visual
        bar_length = 40
        filled = int(bar_length * percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r▶️  [{bar}] {percent}%", end="", flush=True)
    
    print(f"🔄 Comprimindo {Path(input_file).name}...")
    
    success, message = compressor.compress_video(
        input_file=input_file,
        output_file=output_file,
        profile="Compressão Forte",
        resolution=0,
        remove_audio=False,
        progress_callback=progresso
    )
    
    print()
    print(f"{'✅' if success else '❌'} {message}")
    print()


def exemplo_multiplos_perfis():
    """Exemplo: Testar todos os perfis."""
    print("=" * 60)
    print("EXEMPLO 5: Comparar Todos os Perfis")
    print("=" * 60)
    
    compressor = VideoCompressor()
    
    input_file = "/tmp/test_video.mp4"
    
    if not os.path.exists(input_file):
        print(f"❌ Arquivo não encontrado: {input_file}")
        return
    
    input_size = os.path.getsize(input_file)
    
    print(f"📁 Arquivo: {Path(input_file).name} ({format_file_size(input_size)})")
    print()
    print(f"{'Perfil':<25} {'Tamanho Final':<20} {'Redução':<10} {'Config'}")
    print("-" * 80)
    
    for perfil_name, config in compressor.COMPRESSION_PROFILES.items():
        output_file = f"/tmp/teste_{perfil_name.replace(' ', '_')}.mp4"
        
        # Não executar compressão real (apenas mostrar estimation)
        # Para teste real, descomente as linhas abaixo:
        
        # success, msg = compressor.compress_video(
        #     input_file, output_file, profile=perfil_name
        # )
        # if success:
        #     output_size = os.path.getsize(output_file)
        
        # Estimativa heurística
        reduction_factor = {
            "Alta Qualidade": 0.65,
            "Balanceado": 0.40,
            "Compressão Forte": 0.25,
            "Compressão Máxima": 0.15
        }
        
        factor = reduction_factor.get(perfil_name, 0.40)
        estimated_size = int(input_size * factor)
        reduction = ((input_size - estimated_size) / input_size) * 100
        
        config_str = f"CRF={config['crf']}, Preset={config['preset']}"
        
        print(f"{perfil_name:<25} {format_file_size(estimated_size):<20} {reduction:>6.1f}% {config_str}")
    
    print()


def exemplo_custom_compressao():
    """Exemplo: Compressão customizada."""
    print("=" * 60)
    print("EXEMPLO 6: Customização Avançada")
    print("=" * 60)
    
    compressor = VideoCompressor()
    
    input_file = "/tmp/test_video.mp4"
    output_file = "/tmp/exemplo_custom.mp4"
    
    if not os.path.exists(input_file):
        print(f"❌ Arquivo não encontrado: {input_file}")
        return
    
    print("Configurações personalizadas:")
    print("  - Profile: Balanceado")
    print("  - Redução de resolução: SIM (720p)")
    print("  - Áudio: SIM (mantem)")
    print()
    print("🔄 Processando...")
    
    success, message = compressor.compress_video(
        input_file=input_file,
        output_file=output_file,
        profile="Balanceado",
        resolution=720,  # Reduzir para 720p
        remove_audio=False
    )
    
    print(f"{'✅' if success else '❌'} {message}")
    
    if success:
        inp_info = compressor.get_video_info(input_file)
        out_info = compressor.get_video_info(output_file)
        
        if inp_info and out_info:
            print(f"\n📊 Antes:")
            print(f"   Resolução: {inp_info['width']}x{inp_info['height']}")
            print(f"   Tamanho: {format_file_size(inp_info['file_size'])}")
            print(f"\n📊 Depois:")
            print(f"   Resolução: {out_info['width']}x{out_info['height']}")
            print(f"   Tamanho: {format_file_size(out_info['file_size'])}")
    
    print()


def exemplo_sem_audio():
    """Exemplo: Remover áudio para máxima compressão."""
    print("=" * 60)
    print("EXEMPLO 7: Compressão sem Áudio")
    print("=" * 60)
    
    compressor = VideoCompressor()
    
    input_file = "/tmp/test_video.mp4"
    output_file = "/tmp/exemplo_sem_audio.mp4"
    
    if not os.path.exists(input_file):
        print(f"❌ Arquivo não encontrado: {input_file}")
        return
    
    print("Removendo áudio para máxima compressão...")
    print()
    
    success, message = compressor.compress_video(
        input_file=input_file,
        output_file=output_file,
        profile="Compressão Forte",
        remove_audio=True  # REMOVE ÁUDIO
    )
    
    print(f"{'✅' if success else '❌'} {message}")
    
    if success:
        inp_size = os.path.getsize(input_file)
        out_size = os.path.getsize(output_file)
        reduction = ((inp_size - out_size) / inp_size) * 100
        
        print(f"\n📊 Resultado (sem áudio):")
        print(f"   Original: {format_file_size(inp_size)}")
        print(f"   Final: {format_file_size(out_size)}")
        print(f"   Redução: {reduction:.1f}%")
    
    print()


def main():
    """Executa todos os exemplos."""
    print("""
╔════════════════════════════════════════════════════════════╗
║     EXEMPLOS DE USO: Compressor de Vídeos               ║
║     Integração Programática e Automação                   ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Executar exemplos
    exemplo_basico()
    exemplo_leitura_info()
    exemplo_compressao_simples()
    exemplo_compressao_com_progresso()
    exemplo_multiplos_perfis()
    exemplo_custom_compressao()
    exemplo_sem_audio()
    
    print("=" * 60)
    print("✅ Exemplos Concluídos")
    print("=" * 60)
    print("""
Para usar em seu projeto:

1. Importe a biblioteca:
   from compressor import VideoCompressor

2. Crie uma instância:
   compressor = VideoCompressor()

3. Use o método compress_video():
   success, msg = compressor.compress_video(
       input_file="entrada.mp4",
       output_file="saida.mp4",
       profile="Balanceado",
       resolution=720,  # 0 = original
       remove_audio=False,
       progress_callback=minha_funcao_progresso
   )

Para mais informações, veja:
- README.md (visão geral)
- TECNICA_DETALHADA.md (configuração de compressão)
- EXECUCAO_RAPIDA.md (troubleshooting)
    """)


if __name__ == "__main__":
    main()
