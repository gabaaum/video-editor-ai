#!/usr/bin/env python3
"""
video_server.py — Editor de vídeo inteligente.
Rodar: python3 video_server.py
Acesse: http://localhost:5001
"""

import os
import re
import uuid
import json
import subprocess
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort

app = Flask(__name__)

UPLOAD_DIR = Path('video_uploads')
OUTPUT_DIR = Path('video_outputs')
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# job_id → { status, progresso, etapa, path, segmentos, silencio, ... }
JOBS: dict = {}


# ─── Helpers de mídia ────────────────────────────────────────────────────────

def info_video(path: Path) -> tuple[float, float]:
    """Retorna (duração_s, fps)."""
    r = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json',
         '-show_streams', '-show_format', str(path)],
        capture_output=True, text=True
    )
    d = json.loads(r.stdout)
    duracao = float(d['format']['duration'])
    fps = 30.0
    for s in d.get('streams', []):
        if s.get('codec_type') == 'video':
            partes = s.get('r_frame_rate', '30/1').split('/')
            fps = float(partes[0]) / float(partes[1])
            break
    return duracao, fps


def detectar_silencio(path: Path, threshold: int = -35, dur_min: float = 0.5) -> list:
    r = subprocess.run(
        ['ffmpeg', '-i', str(path),
         '-af', f'silencedetect=noise={threshold}dB:d={dur_min}',
         '-f', 'null', '-', '-y'],
        capture_output=True, text=True
    )
    starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r.stderr)]
    ends   = [float(x) for x in re.findall(r'silence_end: ([\d.]+)',   r.stderr)]
    result = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        result.append({'start': s, 'end': e, 'cortar': True})
    return result


def transcrever(path: Path, job_id: str) -> list:
    """Usa faster-whisper (ou openai-whisper como fallback)."""
    audio = UPLOAD_DIR / f'{job_id}.wav'
    subprocess.run(
        ['ffmpeg', '-i', str(path), '-q:a', '0', '-map', 'a',
         '-ac', '1', '-ar', '16000', str(audio), '-y'],
        capture_output=True
    )
    try:
        from faster_whisper import WhisperModel
        modelo = WhisperModel('base', device='cpu', compute_type='int8')
        segs, _ = modelo.transcribe(str(audio), word_timestamps=True)
        segmentos = []
        for i, seg in enumerate(segs):
            palavras = [
                {'texto': w.word.strip(), 'inicio': w.start, 'fim': w.end}
                for w in (seg.words or [])
            ]
            segmentos.append({
                'id': i, 'inicio': seg.start, 'fim': seg.end,
                'texto': seg.text.strip(), 'palavras': palavras
            })
    except ImportError:
        import whisper
        m = whisper.load_model('base')
        res = m.transcribe(str(audio), word_timestamps=True, verbose=False)
        segmentos = []
        for seg in res['segments']:
            palavras = [
                {'texto': w['word'].strip(), 'inicio': w['start'], 'fim': w['end']}
                for w in seg.get('words', [])
            ]
            segmentos.append({
                'id': seg['id'], 'inicio': seg['start'], 'fim': seg['end'],
                'texto': seg['text'].strip(), 'palavras': palavras
            })
    finally:
        audio.unlink(missing_ok=True)
    return segmentos


def processar_job(job_id: str, path: Path):
    job = JOBS[job_id]
    try:
        job.update(status='processando', progresso=5, etapa='Lendo vídeo…')
        duracao, fps = info_video(path)
        job.update(duracao=duracao, fps=round(fps, 3), progresso=15)

        job.update(etapa='Transcrevendo com Whisper (pode demorar)…', progresso=20)
        segmentos = transcrever(path, job_id)
        job.update(segmentos=segmentos, progresso=75)

        job.update(etapa='Detectando silêncios…', progresso=80)
        silencio = detectar_silencio(path)
        job.update(silencio=silencio, progresso=100, etapa='Pronto!', status='ok')

    except Exception as e:
        job.update(status='erro', erro=str(e))


# ─── Geração de legendas ASS ─────────────────────────────────────────────────

def ts_ass(s: float) -> str:
    """Formata segundos para H:MM:SS.cc (formato ASS)."""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f'{h}:{m:02d}:{sec:05.2f}'


def ajustar_tempo(t: float, mantidos: list) -> float | None:
    """Mapeia tempo original → tempo após os cortes. None se caiu num corte."""
    acum = 0.0
    for ini, fim in mantidos:
        if t < ini - 0.02:
            return None
        if t <= fim + 0.02:
            return acum + max(0.0, t - ini)
        acum += fim - ini
    return None


def gerar_ass(segmentos: list, mantidos: list, chunk_size: int = 4) -> str:
    header = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,90,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,2,2,80,80,160,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    # ASS usa ABGR: laranja (#FF9600) → &H000096FF&
    def fmt(p: dict) -> str:
        t = (p.get('texto') or '').upper()
        if p.get('enfase'):
            return r'{\c&H000096FF&\fs100}' + t + r'{\c&H00FFFFFF&\fs90}'
        return t

    linhas = []

    if chunk_size >= 999:
        # Modo frase: cada segmento = uma linha
        for seg in segmentos:
            ini = ajustar_tempo(seg['inicio'], mantidos)
            fim = ajustar_tempo(seg['fim'], mantidos)
            if ini is None or fim is None:
                continue
            pals = seg.get('palavras') or [{'texto': seg['texto'], 'enfase': False}]
            linhas.append(
                f'Dialogue: 0,{ts_ass(ini)},{ts_ass(fim)},Default,,0,0,0,,{" ".join(fmt(p) for p in pals)}'
            )
    else:
        palavras = [p for seg in segmentos for p in (seg.get('palavras') or [])]
        if not palavras:
            palavras = [
                {'texto': seg['texto'], 'inicio': seg['inicio'],
                 'fim': seg['fim'], 'enfase': False}
                for seg in segmentos
            ]
        for i in range(0, len(palavras), chunk_size):
            bloco = palavras[i:i + chunk_size]
            ini = ajustar_tempo(bloco[0]['inicio'], mantidos)
            fim = ajustar_tempo(bloco[-1]['fim'], mantidos)
            if ini is None or fim is None:
                continue
            linhas.append(
                f'Dialogue: 0,{ts_ass(ini)},{ts_ass(fim)},Default,,0,0,0,,{" ".join(fmt(p) for p in bloco)}'
            )

    return header + '\n'.join(linhas)


# ─── Renderização ────────────────────────────────────────────────────────────

def executar_render(job_id: str, silencio: list, segmentos: list, chunk_size: int):
    job = JOBS[job_id]
    try:
        job['render_status'] = 'renderizando'
        path_in  = Path(job['path'])
        duracao  = job['duracao']

        # Calcula segmentos a manter
        cortes = sorted([s for s in silencio if s.get('cortar')], key=lambda x: x['start'])
        mantidos: list[tuple[float, float]] = []
        pos = 0.0
        for c in cortes:
            fim_corte = c.get('end') or c['start']
            if c['start'] > pos + 0.02:
                mantidos.append((pos, c['start']))
            pos = fim_corte
        if pos < duracao - 0.02:
            mantidos.append((pos, duracao))
        if not mantidos:
            mantidos = [(0.0, duracao)]

        ass_path  = OUTPUT_DIR / f'{job_id}.ass'
        path_temp = OUTPUT_DIR / f'{job_id}_cut.mp4'
        path_out  = OUTPUT_DIR / f'{job_id}_final.mp4'

        # Passo 1: cortar silêncios (se necessário)
        if len(mantidos) > 1:
            partes_v, partes_a = [], []
            for i, (ini, fim) in enumerate(mantidos):
                partes_v.append(f'[0:v]trim={ini:.4f}:{fim:.4f},setpts=PTS-STARTPTS[v{i}]')
                partes_a.append(f'[0:a]atrim={ini:.4f}:{fim:.4f},asetpts=PTS-STARTPTS[a{i}]')
            n = len(mantidos)
            juncao = ''.join(f'[v{i}][a{i}]' for i in range(n))
            fc = ';'.join(partes_v + partes_a + [f'{juncao}concat=n={n}:v=1:a=1[vo][ao]'])
            r = subprocess.run(
                ['ffmpeg', '-i', str(path_in), '-filter_complex', fc,
                 '-map', '[vo]', '-map', '[ao]',
                 '-c:v', 'libx264', '-c:a', 'aac', str(path_temp), '-y'],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-600:])
            base_para_legendas = path_temp
        else:
            base_para_legendas = path_in

        # Passo 2: gerar e queimar legendas
        ass_path.write_text(gerar_ass(segmentos, mantidos, chunk_size), encoding='utf-8')
        r2 = subprocess.run(
            ['ffmpeg', '-i', str(base_para_legendas),
             '-vf', f"ass='{ass_path}'",
             '-c:v', 'libx264', '-c:a', 'copy', str(path_out), '-y'],
            capture_output=True, text=True
        )
        if path_temp.exists():
            path_temp.unlink()
        if r2.returncode != 0:
            raise RuntimeError(r2.stderr[-600:])

        job.update(path_out=str(path_out), render_status='pronto')

    except Exception as e:
        job.update(render_status='erro', render_erro=str(e))


# ─── Rotas ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('editor.html')


@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('video')
    if not f:
        return jsonify({'erro': 'Nenhum arquivo enviado.'}), 400
    jid = uuid.uuid4().hex[:8]
    ext = Path(f.filename).suffix.lower() or '.mp4'
    path = UPLOAD_DIR / f'{jid}{ext}'
    f.save(path)
    JOBS[jid] = {
        'status': 'aguardando', 'progresso': 0,
        'etapa': 'Arquivo recebido.', 'path': str(path), 'nome': f.filename,
        'render_status': 'idle'
    }
    threading.Thread(target=processar_job, args=(jid, path), daemon=True).start()
    return jsonify({'job_id': jid})


@app.route('/status/<jid>')
def status(jid):
    job = JOBS.get(jid)
    if not job:
        return jsonify({'erro': 'Não encontrado.'}), 404
    # Não serializa paths internos desnecessários
    dados = {k: v for k, v in job.items() if k != 'path'}
    return jsonify(dados)


@app.route('/video/<jid>')
def servir_video(jid):
    job = JOBS.get(jid)
    if not job:
        abort(404)
    return send_file(job['path'])


@app.route('/renderizar/<jid>', methods=['POST'])
def renderizar(jid):
    job = JOBS.get(jid)
    if not job or job['status'] != 'ok':
        return jsonify({'erro': 'Job não pronto.'}), 400
    cfg = request.get_json() or {}
    silencio   = cfg.get('silencio',   job.get('silencio', []))
    segmentos  = cfg.get('segmentos',  job['segmentos'])   # transcrição editada
    chunk_size = int(cfg.get('chunk_size', 4))              # estilo de legenda
    job['silencio']  = silencio
    job['segmentos'] = segmentos
    threading.Thread(
        target=executar_render, args=(jid, silencio, segmentos, chunk_size), daemon=True
    ).start()
    return jsonify({'ok': True})


@app.route('/render_status/<jid>')
def render_status(jid):
    job = JOBS.get(jid)
    if not job:
        return jsonify({'erro': 'Não encontrado.'}), 404
    return jsonify({
        'status': job.get('render_status', 'idle'),
        'erro': job.get('render_erro')
    })


@app.route('/download/<jid>')
def download(jid):
    job = JOBS.get(jid)
    if not job or 'path_out' not in job:
        abort(404)
    return send_file(
        job['path_out'], as_attachment=True,
        download_name=f'editado_{jid}.mp4'
    )


if __name__ == '__main__':
    app.run(debug=True, port=5001)
