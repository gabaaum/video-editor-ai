#!/usr/bin/env python3
"""
generate_carousel.py — Gerador automático de carrosséis para Instagram/LinkedIn.

Uso:
    python generate_carousel.py --tema "Benefícios da IA na produtividade" --num_slides 5
"""

import argparse
import os
import sys
import textwrap

# Verifica e instala Pillow se necessário
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess
    print("Pillow não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw, ImageFont


# ──────────────────────────────────────────────────────────────────────────────
# 1. GERAÇÃO DE CONTEÚDO TEXTUAL
# ──────────────────────────────────────────────────────────────────────────────

def gerar_conteudo_slides(tema: str, num_slides: int) -> list[dict]:
    """
    Gera o conteúdo textual de cada slide com base no tema fornecido.
    Simula a lógica de um LLM estruturando o conteúdo em introdução,
    pontos-chave e call to action.
    """
    slides = []

    # Slide de abertura (capa)
    slides.append({
        "titulo": f"{tema}",
        "texto_principal": (
            f"Descubra como {tema.lower()} pode transformar sua rotina "
            "e impulsionar seus resultados. Continue lendo!"
        ),
    })

    # Slides intermediários com pontos-chave
    pontos = [
        ("O Problema", f"Muitas pessoas enfrentam desafios relacionados a {tema.lower()}. "
                        "Entender o cenário atual é o primeiro passo para mudá-lo."),
        ("A Oportunidade", f"Com as estratégias certas em {tema.lower()}, é possível "
                            "economizar tempo, reduzir erros e obter resultados superiores."),
        ("Como Aplicar", f"Comece com pequenos passos: identifique onde {tema.lower()} "
                          "pode ser integrado ao seu fluxo de trabalho diário."),
        ("Resultados Reais", f"Empresas que adotaram práticas ligadas a {tema.lower()} "
                              "relatam ganhos de produtividade de até 40% em poucos meses."),
        ("Ferramentas Essenciais", f"Existem diversas ferramentas que facilitam a aplicação "
                                    f"de {tema.lower()} — escolha a que melhor se adapta à sua realidade."),
        ("Dicas Práticas", f"Separe 15 minutos por dia para explorar recursos de "
                            f"{tema.lower()}. A consistência é o segredo do progresso."),
        ("Cases de Sucesso", f"Profissionais de diversas áreas já colhem os frutos de "
                              f"{tema.lower()}. Inspire-se e comece hoje mesmo."),
    ]

    # Distribui pontos intermediários conforme o número de slides solicitado
    slides_intermediarios = num_slides - 2  # exclui capa e CTA
    for i in range(slides_intermediarios):
        ponto = pontos[i % len(pontos)]
        slides.append({
            "titulo": ponto[0],
            "texto_principal": ponto[1],
        })

    # Último slide: Call to Action
    slides.append({
        "titulo": "Gostou do conteúdo?",
        "texto_principal": (
            f"Agora você já sabe mais sobre {tema.lower()}!\n\n"
            "👇 Comente abaixo o que você achou!\n"
            "💾 Salve este post para consultar depois.\n"
            "🔁 Compartilhe com quem precisa ver isso."
        ),
        "call_to_action": "Comente para saber mais!",
    })

    # Garante que a lista tem exatamente num_slides entradas
    return slides[:num_slides]


# ──────────────────────────────────────────────────────────────────────────────
# 2. GERAÇÃO DAS IMAGENS
# ──────────────────────────────────────────────────────────────────────────────

# Paleta de cores do tema
BACKGROUND_TOP    = (18, 18, 40)      # azul-escuro quase preto
BACKGROUND_BOTTOM = (40, 20, 70)      # roxo escuro
ACCENT_COLOR      = (120, 80, 255)    # roxo vibrante
TITLE_COLOR       = (255, 255, 255)   # branco puro
TEXT_COLOR        = (220, 215, 240)   # branco acinzentado suave
BADGE_BG          = (120, 80, 255)    # mesmo roxo do accent
BADGE_TEXT        = (255, 255, 255)

SLIDE_SIZE   = (1080, 1080)
PADDING      = 80
LINE_SPACING = 12  # pixels extras entre linhas


def _criar_gradiente(largura: int, altura: int, cor_topo, cor_base) -> Image.Image:
    """Cria uma imagem com gradiente vertical entre duas cores."""
    img = Image.new("RGB", (largura, altura))
    draw = ImageDraw.Draw(img)
    for y in range(altura):
        t = y / altura
        r = int(cor_topo[0] + (cor_base[0] - cor_topo[0]) * t)
        g = int(cor_topo[1] + (cor_base[1] - cor_topo[1]) * t)
        b = int(cor_topo[2] + (cor_base[2] - cor_topo[2]) * t)
        draw.line([(0, y), (largura, y)], fill=(r, g, b))
    return img


def _carregar_fonte(tamanho: int, negrito: bool = False) -> ImageFont.FreeTypeFont:
    """
    Tenta carregar DejaVuSans (disponível na maioria dos sistemas Linux/Mac).
    Cai para a fonte padrão do Pillow se não encontrar.
    """
    candidatos_negrito = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "DejaVuSans-Bold.ttf",
    ]
    candidatos_normal = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "DejaVuSans.ttf",
    ]
    candidatos = candidatos_negrito if negrito else candidatos_normal
    for caminho in candidatos:
        if os.path.exists(caminho):
            return ImageFont.truetype(caminho, tamanho)
    # Fallback: fonte bitmap padrão do Pillow (sem controle de tamanho)
    return ImageFont.load_default()


def _quebrar_texto(texto: str, fonte: ImageFont.FreeTypeFont,
                   largura_max: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """
    Quebra o texto em linhas que caibam dentro de largura_max pixels.
    Respeita quebras de linha manuais (\n) existentes no texto.
    """
    linhas_resultado = []
    for paragrafo in texto.split("\n"):
        palavras = paragrafo.split()
        linha_atual = ""
        for palavra in palavras:
            candidato = (linha_atual + " " + palavra).strip()
            bbox = draw.textbbox((0, 0), candidato, font=fonte)
            largura_texto = bbox[2] - bbox[0]
            if largura_texto <= largura_max:
                linha_atual = candidato
            else:
                if linha_atual:
                    linhas_resultado.append(linha_atual)
                linha_atual = palavra
        if linha_atual:
            linhas_resultado.append(linha_atual)
        linhas_resultado.append("")  # espaço entre parágrafos
    # Remove linha vazia final redundante
    while linhas_resultado and linhas_resultado[-1] == "":
        linhas_resultado.pop()
    return linhas_resultado


def _desenhar_linha_acento(draw: ImageDraw.ImageDraw, x: int, y: int, largura: int = 60):
    """Desenha uma linha colorida de destaque abaixo do título."""
    draw.rounded_rectangle(
        [(x, y), (x + largura, y + 6)],
        radius=3,
        fill=ACCENT_COLOR,
    )


def criar_imagem_slide(slide_data: dict, slide_numero: int,
                       total_slides: int, output_dir: str) -> str:
    """
    Cria e salva a imagem de um slide.

    Args:
        slide_data:    Dicionário com 'titulo' e 'texto_principal'.
        slide_numero:  Índice do slide (começa em 1).
        total_slides:  Total de slides no carrossel.
        output_dir:    Pasta onde o arquivo será salvo.

    Returns:
        Caminho completo do arquivo salvo.
    """
    W, H = SLIDE_SIZE

    # Fundo com gradiente
    img = _criar_gradiente(W, H, BACKGROUND_TOP, BACKGROUND_BOTTOM)
    draw = ImageDraw.Draw(img)

    # Decoração: círculo suave no canto superior direito
    draw.ellipse([(700, -150), (1250, 400)], fill=(60, 30, 100))
    draw.ellipse([(750, -100), (1200, 350)], fill=(45, 20, 80))

    # Decoração: linha horizontal accent no topo
    draw.rectangle([(PADDING, 40), (W - PADDING, 46)], fill=ACCENT_COLOR)

    # ── Badge com número do slide ─────────────────────────────────────────────
    fonte_badge = _carregar_fonte(28, negrito=True)
    badge_texto = f"{slide_numero}/{total_slides}"
    bbox_b = draw.textbbox((0, 0), badge_texto, font=fonte_badge)
    bw = bbox_b[2] - bbox_b[0] + 30
    bh = bbox_b[3] - bbox_b[1] + 16
    bx, by = W - PADDING - bw, 60
    draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=12, fill=BADGE_BG)
    draw.text((bx + 15, by + 8), badge_texto, font=fonte_badge, fill=BADGE_TEXT)

    # ── Título ────────────────────────────────────────────────────────────────
    fonte_titulo = _carregar_fonte(64, negrito=True)
    area_titulo = W - 2 * PADDING

    linhas_titulo = _quebrar_texto(slide_data["titulo"], fonte_titulo, area_titulo, draw)
    y_titulo = 160
    for linha in linhas_titulo:
        draw.text((PADDING, y_titulo), linha, font=fonte_titulo, fill=TITLE_COLOR)
        bbox = draw.textbbox((0, 0), linha, font=fonte_titulo)
        y_titulo += (bbox[3] - bbox[1]) + LINE_SPACING

    # Linha de acento abaixo do título
    _desenhar_linha_acento(draw, PADDING, y_titulo + 10)
    y_texto = y_titulo + 50

    # ── Texto principal ───────────────────────────────────────────────────────
    fonte_texto = _carregar_fonte(36)
    area_texto = W - 2 * PADDING
    linhas_texto = _quebrar_texto(slide_data["texto_principal"], fonte_texto, area_texto, draw)

    for linha in linhas_texto:
        if y_texto > H - PADDING - 60:
            break  # evita estouro vertical
        draw.text((PADDING, y_texto), linha, font=fonte_texto, fill=TEXT_COLOR)
        if linha:
            bbox = draw.textbbox((0, 0), linha, font=fonte_texto)
            y_texto += (bbox[3] - bbox[1]) + LINE_SPACING
        else:
            y_texto += 20  # espaço de parágrafo

    # ── Rodapé ────────────────────────────────────────────────────────────────
    draw.rectangle([(PADDING, H - 50), (W - PADDING, H - 44)], fill=ACCENT_COLOR)

    # Salva o arquivo
    nome_arquivo = f"slide_{slide_numero:02d}.png"
    caminho = os.path.join(output_dir, nome_arquivo)
    img.save(caminho, "PNG")
    return caminho


# ──────────────────────────────────────────────────────────────────────────────
# 3. FLUXO PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Gera imagens de carrossel para Instagram/LinkedIn."
    )
    parser.add_argument(
        "--tema",
        required=True,
        help='Tema do carrossel (ex: "Benefícios da IA na produtividade")',
    )
    parser.add_argument(
        "--num_slides",
        type=int,
        required=True,
        help="Número de slides desejado (mínimo 2, recomendado entre 5 e 10)",
    )
    args = parser.parse_args()

    if args.num_slides < 2:
        print("Erro: --num_slides deve ser pelo menos 2.")
        sys.exit(1)

    # Diretório de saída baseado no tema
    tema_slug = args.tema.lower().replace(" ", "_")[:40]
    output_dir = os.path.join("carrossel_output", tema_slug)
    os.makedirs(output_dir, exist_ok=True)

    print(f'\n🎨 Gerando carrossel: "{args.tema}"')
    print(f"   Slides: {args.num_slides}")
    print(f"   Saída:  {output_dir}/\n")

    # Gera conteúdo textual
    slides = gerar_conteudo_slides(args.tema, args.num_slides)

    # Cria imagens
    for i, slide_data in enumerate(slides, start=1):
        caminho = criar_imagem_slide(slide_data, i, len(slides), output_dir)
        print(f"  ✅ {os.path.basename(caminho)} — {slide_data['titulo']}")

    print(f"\n✨ Carrossel gerado com sucesso em: {os.path.abspath(output_dir)}/")


if __name__ == "__main__":
    main()
