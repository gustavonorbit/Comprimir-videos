<div align="center">

# Project Codename

**🇧🇷 Português (Brasil)** · [🇺🇸 English](README_EN.md)

### Prepare vídeos de forma rápida para qualquer destino.

Converta, comprima, otimize e compartilhe — tudo com poucos cliques e processamento 100% local.

<br />

![Beta](https://img.shields.io/badge/status-Beta-007AFF?style=for-the-badge)
![Open Source](https://img.shields.io/badge/Open%20Source-sim-34C759?style=for-the-badge)
![Licença](https://img.shields.io/badge/licença-GPL--3.0-blue?style=for-the-badge)

![Windows](https://img.shields.io/badge/Windows-suportado-2F80ED?style=for-the-badge&logo=windows)
![macOS](https://img.shields.io/badge/macOS-suportado-111827?style=for-the-badge&logo=apple)
![Android](https://img.shields.io/badge/Android-em%20desenvolvimento-34A853?style=for-the-badge&logo=android)
![iOS](https://img.shields.io/badge/iOS-planejado-8E8E93?style=for-the-badge&logo=apple)

![FFmpeg](https://img.shields.io/badge/FFmpeg-powered-007808?style=for-the-badge&logo=ffmpeg)
![Python](https://img.shields.io/badge/Python-Desktop-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-Mobile-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![Media3](https://img.shields.io/badge/Media3-Android-EA4335?style=for-the-badge&logo=android&logoColor=white)

<br />

[**⬇️ Baixar o app (macOS)**](distribuicao/) · [Sobre](#sobre-o-projeto) · [Funcionalidades](#funcionalidades) · [Roadmap](#roadmap) · [Instalação](#instalação) · [Contribuir](#contribuições)

</div>

---

## Sumário

- [Sobre o Projeto](#sobre-o-projeto)
- [Filosofia do Projeto](#filosofia-do-projeto)
- [Escolha do Nome](#escolha-do-nome)
- [Status](#status)
- [Funcionalidades](#funcionalidades)
- [Roadmap](#roadmap)
- [Nossa Visão](#nossa-visão)
- [Screenshots](#screenshots)
- [Demonstração em GIF](#demonstração-em-gif)
- [Tecnologias](#tecnologias)
- [Instalação](#instalação)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Documentação](#documentação)
- [Contribuições](#contribuições)
- [Open Source](#open-source)
- [Changelog](#changelog)
- [Licença](#licença)
- [Agradecimentos](#agradecimentos)

## Sobre o Projeto

**Project Codename** nasceu como uma ferramenta simples para reduzir o tamanho de vídeos, mas a visão do projeto é maior do que isso.

O objetivo não é ser apenas um compressor de vídeos. A ideia é construir uma ferramenta para **preparar vídeos de forma rápida para qualquer destino**:

- converter;
- comprimir;
- otimizar;
- preparar;
- compartilhar.

Tudo com poucos cliques, processamento local e uma interface que não atrapalha o usuário.

> [!IMPORTANT]
> Este projeto está em desenvolvimento ativo e ainda está em fase **Beta**. Funcionalidades, interface e estrutura podem evoluir bastante até uma versão estável.

## Filosofia do Projeto

O software nasceu para resolver problemas reais encontrados no dia a dia.

Queremos uma ferramenta simples. Não queremos competir com grandes editores de vídeo. Queremos que qualquer pessoa consiga preparar um vídeo em poucos segundos, sem precisar entender codecs, presets, formatos, bitrate ou configurações avançadas.

A prioridade é criar uma experiência rápida, clara e confiável:

- sem upload obrigatório;
- sem complexidade desnecessária;
- sem transformar uma tarefa simples em um fluxo pesado;
- com controle suficiente para quem precisa ajustar o resultado.

## Escolha do Nome

O projeto nasceu como uma ideia pessoal e ainda não possui um nome definitivo.

Por enquanto usamos **Project Codename** como nome temporário. Sugestões são muito bem-vindas, e a comunidade poderá participar da escolha do nome final.

Se você tiver uma ideia de nome que transmita simplicidade, velocidade e preparação inteligente de vídeos, abra uma discussão ou issue quando o repositório público estiver disponível.

## Status

| Plataforma | Status | Observações |
| --- | --- | --- |
| Desktop | ✔ Beta funcional | Aplicativo em Python com interface CustomTkinter |
| Windows | ✔ Suportado | Empacotamento `.exe` planejado com PyInstaller |
| macOS | ✔ Suportado | Execução local e empacotamento `.app` planejados |
| Linux | 🚧 Futuro | Possível suporte após estabilização |
| Android | 🚧 Em desenvolvimento | Aplicativo mobile em Flutter |
| iOS | ❌ Planejado | Ainda sem implementação pública |

## Funcionalidades

| Funcionalidade | Desktop | Android | iOS |
| --- | :---: | :---: | :---: |
| Converter qualquer vídeo para MP4 | ✔ | 🚧 | ❌ |
| Compressão de vídeo | ✔ | 🚧 | ❌ |
| Perfis de qualidade | ✔ | 🚧 | ❌ |
| Alteração de resolução | ✔ | 🚧 | ❌ |
| Rotação | ✔ | 🚧 | ❌ |
| Remover áudio | ✔ | 🚧 | ❌ |
| Extração de áudio | ✔ | 🚧 | ❌ |
| Blur em áreas do vídeo | ✔ | 🚧 | ❌ |
| Corte rápido / divisão de clipes | ✔ | 🚧 | ❌ |
| Múltiplos vídeos na timeline | ✔ | 🚧 | ❌ |
| Compartilhamento rápido | ❌ | 🚧 | ❌ |
| Receber vídeos pelo menu Compartilhar | ❌ | 🚧 | ❌ |
| Processamento local | ✔ | 🚧 | ❌ |
| Sem upload para nuvem | ✔ | 🚧 | ❌ |

Legenda: ✔ disponível · 🚧 em desenvolvimento · ❌ não disponível

## Roadmap

### Beta

- ✔ Desktop funcional
- ✔ Compressão para MP4
- ✔ Perfis de qualidade
- ✔ Alteração de resolução
- ✔ Rotação
- ✔ Remoção e extração de áudio
- ✔ Timeline com segmentos reais
- ✔ Blur temporal
- 🚧 Android
- 🚧 Melhorias de UI/UX
- 🚧 Empacotamento mais simples para usuários finais

### Próximas versões

- Compressão em lote
- Melhor estimativa de tamanho final
- Presets inteligentes por destino
- Compartilhamento direto
- Receber vídeos pelo menu Compartilhar do sistema
- Melhor compatibilidade com codecs de entrada
- Melhor experiência mobile
- Versão iOS
- Documentação técnica para contribuidores

## Nossa Visão

Este projeto não pretende crescer sozinho.

Queremos aprender junto da comunidade, receber sugestões, discutir ideias e construir uma ferramenta realmente útil. O objetivo é criar um software que resolva uma dor comum de forma simples, transparente e agradável.

Se você já precisou reduzir um vídeo para enviar por mensagem, preparar um arquivo para redes sociais, corrigir rotação, remover áudio ou transformar um vídeo enorme em algo compartilhável, este projeto é para você.

## Screenshots

> [!NOTE]
> Esta seção está preparada para receber imagens oficiais da interface.

| Desktop | Mobile |
| --- | --- |
| `screenshots/desktop-home.png` | `screenshots/mobile-home.png` |
| `screenshots/desktop-editor.png` | `screenshots/mobile-processing.png` |

## Demonstração em GIF

> GIF de demonstração em breve.

```text
assets/demo/demo.gif
```

## Tecnologias

### Desktop

- Python
- Tkinter / CustomTkinter
- FFmpeg
- FFprobe
- PyInstaller para empacotamento

### Mobile

- Flutter
- Android
- Media3
- iOS planejado

## Instalação

> [!TIP]
> Só quer usar o app, sem mexer em código? Baixe o `.dmg` ou `.zip` prontos em [`distribuicao/`](distribuicao/) — tem passo a passo simples por lá. O restante desta seção é para quem quer rodar/buildar a partir do código-fonte.

### Desktop

#### Requisitos

- Python 3.11 ou superior recomendado
- FFmpeg e FFprobe instalados no sistema
- Dependências Python em `desktop/requirements.txt`

#### macOS

```bash
brew install ffmpeg
cd desktop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

#### Windows

```powershell
cd desktop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

FFmpeg pode ser instalado pelo Chocolatey:

```powershell
choco install ffmpeg
```

Ou manualmente pelo site oficial:

```text
https://ffmpeg.org/download.html
```

#### Linux

> [!NOTE]
> Suporte Linux ainda não é prioridade da fase Beta, mas a base Python/FFmpeg deve funcionar em muitas distribuições.

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg
cd desktop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

### Gerar o `.app` standalone (macOS)

Para quem não quer instalar Python/FFmpeg, existe um build empacotado com [PyInstaller](https://pyinstaller.org/) que gera um `.app` standalone, com FFmpeg e FFprobe já embutidos:

```bash
cd desktop
source .venv/bin/activate
pyinstaller build.spec --noconfirm
```

O `.app` final fica em `desktop/dist/`.

> [!NOTE]
> O FFmpeg/FFprobe embutidos são os binários do Homebrew, que originalmente dependem dinamicamente de bibliotecas do próprio Homebrew (`libx264`, `libx265`, `openssl`, etc.). O PyInstaller já resolve isso automaticamente ao gerar o bundle: todas as dependências são copiadas para dentro do `.app` e os caminhos são reescritos para `@rpath` (confirmado via `otool -L` — nenhuma referência a `/usr/local` ou `/opt/homebrew` sobra no bundle final). Isso foi validado rodando o `.app` e testando compressão/preview reais.

## Estrutura do Projeto

```text
.
├── desktop/                  # Aplicativo Desktop (Python)
│   ├── main.py                   # Ponto de entrada do app
│   ├── ui.py                     # Interface Desktop
│   ├── compressor.py             # Integração com FFmpeg/FFprobe
│   ├── editor_state.py           # Estado do editor temporal
│   ├── editor_timeline.py        # Timeline do editor
│   ├── video_preview.py          # Prévia de vídeo
│   ├── video_filters.py          # Construção de filtros de vídeo
│   ├── blur_state.py             # Estado compartilhado de blur
│   ├── utils.py                  # Utilitários gerais
│   ├── requirements.txt          # Dependências Python
│   ├── build.spec                # Configuração do PyInstaller (gera o .app)
│   ├── bin/                      # FFmpeg/FFprobe embutidos no build (GPL)
│   └── assets/                   # Ícone e assets do app empacotado
├── mobile_app/                # Aplicativo Mobile (Flutter)
├── docs/                      # Documentação técnica, roadmap e relatórios
│   ├── ROADMAP_MOBILE.md
│   ├── TESTES.md
│   ├── EMPACOTAMENTO.md
│   └── ...
├── assets/                    # Imagens e material de apoio
├── distribuicao/              # App pronto pra baixar (.dmg/.zip) + README simples e CHANGELOG
├── README.md                  # Documentação principal em PT-BR
└── README_EN.md                # Documentação em inglês
```

## Documentação

- [Roadmap](docs/ROADMAP_MOBILE.md)
- [Issues](../../issues)
- [Releases](../../releases)
- [Wiki](../../wiki)
- [Testes](docs/TESTES.md)
- [Empacotamento](docs/EMPACOTAMENTO.md)

> [!TIP]
> Alguns links dependem da publicação do repositório no GitHub.

## Contribuições

Contribuições são bem-vindas.

Você pode ajudar com:

- código;
- documentação;
- tradução;
- design;
- UX;
- testes;
- ideias;
- bugs;
- sugestões.

Antes de propor grandes mudanças, abra uma issue ou discussão para alinharmos a direção. Queremos manter o projeto simples, organizado e útil.

## Open Source

Acreditamos que compartilhar conhecimento fortalece toda a comunidade.

Em tempos de IA, queremos colaborar mais do que competir. Este projeto busca ser um espaço para aprender, construir e melhorar uma ferramenta real com transparência.

Toda contribuição será analisada com cuidado. O foco é manter qualidade, consistência e organização, mesmo com o projeto aberto para colaboração.

## Changelog

O changelog oficial será publicado em breve.

```text
CHANGELOG.md
```

## Licença

Este projeto é distribuído sob a **[GNU General Public License v3.0](LICENSE)**.

> [!NOTE]
> O build empacotado para macOS embute os binários do **FFmpeg**/**FFprobe**, que também são distribuídos sob GPL (build com `--enable-gpl`, incluindo `libx264`). Ao redistribuir o `.app`, o código-fonte deste projeto e os termos da GPL se aplicam ao pacote como um todo — consulte [ffmpeg.org/legal.html](https://ffmpeg.org/legal.html) para detalhes sobre a licença do FFmpeg em si.

## Agradecimentos

Obrigado a todas as pessoas, projetos e comunidades que tornam este trabalho possível:

- Comunidade Open Source
- FFmpeg
- Flutter
- Python
- CustomTkinter
- Contribuidores atuais e futuros

---

Feito por pessoas que gostam de transformar ferramentas pequenas em soluções realmente úteis.
