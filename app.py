import os
import base64
from typing import List
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from dotenv import load_dotenv
from duckduckgo_search import DDGS

load_dotenv()
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

# --- PROMPT OPTIMISÉ (Standardisation des réponses) ---
SYSTEM_PROMPT = """
Tu agis comme un Expert Certifié en Maintenance Bâtiment. 
Pour chaque analyse, tu DOIS respecter strictement ce format HTML :
<div class='res-card'>
    <h2 class='status-icon'>🔍 Diagnostic</h2>
    <p><strong>Observation visuelle :</strong> [Décris précisément ce que tu vois sur les photos]</p>
    <p><strong>Panne identifiée :</strong> [Nom technique de la panne]</p>
</div>

<div class='res-card danger'>
    <h2>🛡️ Sécurité & Risque : [X/10]</h2>
    <p>[Si risque > 6, affiche : ⚠️ INTERVENTION PRO RECOMMANDÉE]</p>
    <ul>[Liste des EPI et précautions]</ul>
</div>

<div class='res-card success'>
    <h2>🛠️ Solution DIY Pas-à-Pas</h2>
    <ol>[Étapes numérotées claires et courtes]</ol>
</div>
"""

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    try:
        images_b64 = []
        for img in images:
            content = await img.read()
            images_b64.append(base64.b64encode(content).decode('utf-8'))
        
        # Envoi avec Prompt stabilisé
        vision_content = [{"type": "text", "text": SYSTEM_PROMPT + f"\nContexte utilisateur : {context}"}]
        for img in images_b64:
            vision_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
        
        response = client.chat.completions.create(
            model=MODEL_VISION, 
            messages=[{"role": "user", "content": vision_content}], 
            temperature=0.1 # Réduit pour éviter les variations
        ).choices[0].message.content

        return response
    except Exception as e:
        return f"<div class='res-card danger'>Erreur technique : {str(e)}</div>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>FixIt AI PRO</title>
    <style>
        :root { --p: #f97316; --s: #2563eb; --d: #dc2626; --bg: #f1f5f9; --card-bg: #ffffff; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); margin: 0; padding: 15px; color: #1e293b; }
        .app { max-width: 500px; margin: auto; }
        
        /* Layout Standardisé */
        header { text-align: center; margin-bottom: 20px; }
        header h1 { color: var(--p); margin: 0; font-size: 1.8rem; letter-spacing: -1px; }
        
        .main-controls { background: var(--card-bg); padding: 20px; border-radius: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .btn { border: none; padding: 14px; border-radius: 12px; font-weight: 700; cursor: pointer; color: white; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.9rem; transition: 0.2s; }
        .btn-cam { background: #334155; grid-column: span 2; }
        .btn-reset { background: #94a3b8; }
        .btn-mic { background: #7c3aed; }
        .btn-run { background: var(--p); width: 100%; font-size: 1.1rem; margin-top: 15px; box-shadow: 0 10px 15px -3px rgba(249, 115, 22, 0.3); }
        
        /* Formatage du texte de sortie */
        .res-card { background: white; padding: 18px; border-radius: 16px; margin-top: 15px; border: 1px solid #e2e8f0; line-height: 1.6; }
        .res-card h2 { margin-top: 0; font-size: 1.1rem; color: #334155; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px; }
        .res-card.danger { border-top: 5px solid var(--d); }
        .res-card.success { border-top: 5px solid #22c55e; }
        
        #pv-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 15px 0; }
        .pv-img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 10px; border: 2px solid #e2e8f0; }
        
        textarea { width: 100%; padding: 15px; border: 2px solid #e2e8f0; border-radius: 12px; box-sizing: border-box; font-family: inherit; font-size: 1rem; background: #f8fafc; resize: none; }
        #loading { display: none; text-align: center; padding: 20px; font-weight: bold; color: var(--p); }
    </style>
</head>
<body>
    <div class="app">
        <header>
            <h1>🛠️ FixIt AI PRO</h1>
            <p style="font-size:0.8rem; opacity:0.7;">Expertise Llama 4 Scout 17B</p>
        </header>

        <div class="main-controls">
            <div class="btn-grid">
                <button class="btn btn-cam" onclick="document.getElementById('fin').click()">📸 PRENDRE DES PHOTOS</button>
                <button class="btn btn-mic" id="mBtn" onclick="tMic()">🎤 DICTER</button>
                <button class="btn btn-reset" onclick="newDiag()">🔄 NOUVEAU</button>
            </div>

            <input type="file" id="fin" accept="image/*" capture="environment" multiple hidden onchange="hFiles(this)">
            <div id="pv-grid"></div>
            
            <textarea id="ctx" placeholder="Décrivez brièvement le problème..."></textarea>
            
            <button id="go" class="btn btn-run" onclick="run()">LANCER L'ANALYSE</button>
        </div>

        <div id="loading">🚀 Analyse multidimensionnelle...</div>
        <div id="out"></div>
    </div>

    <script>
        let files = [];
        
        // Charger le dernier état
        if(localStorage.getItem('last')) document.getElementById('out').innerHTML = localStorage.getItem('last');

        function hFiles(i) {
            const g = document.getElementById('pv-grid');
            for(let f of i.files) {
                files.push(f);
                const r = new FileReader();
                r.onload = (e) => {
                    const img = document.createElement('img');
                    img.src = e.target.result; img.className = 'pv-img';
                    g.appendChild(img);
                };
                r.readAsDataURL(f);
            }
        }

        function newDiag() {
            if(confirm("Effacer ce diagnostic et recommencer ?")) {
                files = [];
                document.getElementById('pv-grid').innerHTML = "";
                document.getElementById('ctx').value = "";
                document.getElementById('out').innerHTML = "";
                localStorage.removeItem('last');
            }
        }

        async function compress(file) {
            return new Promise(res => {
                const r = new FileReader(); r.readAsDataURL(file);
                r.onload = ev => {
                    const i = new Image(); i.src = ev.target.result;
                    i.onload = () => {
                        const c = document.createElement('canvas');
                        const m = 1024; let w = i.width, h = i.height;
                        if(w > h) { if(w > m) { h *= m/w; w = m; } }
                        else { if(h > m) { w *= m/h; h = m; } }
                        c.width = w; c.height = h;
                        c.getContext('2d').drawImage(i, 0, 0, w, h);
                        c.toBlob(b => res(b), 'image/jpeg', 0.7);
                    }
                }
            });
        }

        // --- VOCAL ---
        const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
        let rec = Rec ? new Rec() : null;
        if(rec) {
            rec.lang = 'fr-FR';
            rec.onresult = e => { document.getElementById('ctx').value += " " + e.results[0][0].transcript; tMic(); };
        }
        function tMic() {
            const b = document.getElementById('mBtn');
            if(b.style.background === 'red') { rec.stop(); b.style.background = '#7c3aed'; b.innerHTML = "🎤 DICTER"; }
            else { rec.start(); b.style.background = 'red'; b.innerHTML = "🛑 STOP"; }
        }

        async function run() {
            if(!files.length) return alert("Photo requise");
            document.getElementById('loading').style.display = 'block';
            const fd = new FormData();
            for(let f of files) { const c = await compress(f); fd.append('images', c); }
            fd.append('context', document.getElementById('ctx').value);
            
            try {
                const r = await fetch('/analyze', { method: 'POST', body: fd });
                const resHtml = await r.text();
                document.getElementById('out').innerHTML = resHtml;
                localStorage.setItem('last', resHtml);
            } catch(e) { 
                alert("Erreur de connexion");
            } finally { 
                document.getElementById('loading').style.display = 'none'; 
            }
        }
    </script>
</body>
</html>
    """
