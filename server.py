#!/usr/bin/env python3
"""
server.py — Servidor web para o Gerador de Carrosséis.
Rodar: python3 server.py
Acesse: http://localhost:5000
"""

import base64
import tempfile
from flask import Flask, render_template, request, jsonify
from generate_carousel import gerar_conteudo_slides, criar_imagem_slide

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/gerar', methods=['POST'])
def gerar():
    corpo = request.get_json(silent=True) or {}
    tema = (corpo.get('tema') or '').strip()

    try:
        num_slides = max(2, min(12, int(corpo.get('num_slides', 5))))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Número de slides inválido.'}), 400

    if not tema:
        return jsonify({'erro': 'Informe o tema do carrossel.'}), 400

    slides_data = gerar_conteudo_slides(tema, num_slides)
    resultado = []

    with tempfile.TemporaryDirectory() as tmp:
        for i, slide in enumerate(slides_data, start=1):
            caminho = criar_imagem_slide(slide, i, len(slides_data), tmp)
            with open(caminho, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            resultado.append({
                'indice': i,
                'titulo': slide['titulo'],
                'imagem': f'data:image/png;base64,{b64}',
                'arquivo': f'slide_{i:02d}.png',
            })

    return jsonify({'slides': resultado, 'tema': tema})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
