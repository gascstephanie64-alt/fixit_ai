import os
import base64
import logging
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

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# IDENTIFIANT UNIQUE ET STABLE
MODEL_PROD = "meta-llama/llama-4-scout-17b-16e-instruct"

def get_market_data(query: str):
    links = []
    try:
        with DDGS() as ddgs:
            # Recherche ciblée sur les gros acteurs du DIY et tutoriels
            results = list(ddgs.text(f"tutoriel reparation {query} leroy merlin youtube", max_results=3))
            for r in results:
                links.append(f"<li><a href='{r['href']}' target='_blank'>{r['title']}</a></li>")
    except: pass
    return "".join(links)

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    try:
        # Encodage en base64
        imgs_b64 = [base64.b64encode(await i.read()).decode('utf-8') for i in images]
        
        # PROMPT TECHNIQUE SANS BLABLA
        prompt = f"""
        [ROLE: EXPERT MAINTENANCE INDUSTRIELLE]
        [STRICT: FORMAT HTML UNIQUEMENT]
        Analyse les photos suivantes. Contexte utilisateur : {context}
        
        STRUCTURE DU RAPPORT :
        <div class='section'><h3>🔍 DIAGNOSTIC TECHNIQUE</h3><p>[Nom de la pièce et cause précise de la panne]</p></div>
        <div class='section' style='background:#fff1f2; padding:10px; border-radius:8px;'><h3>⚠️ RISQUE & SECURITÉ : [X]/10</h3><p>[Dangers immédiats et EPI requis]</p></div>
        <div class='section'><h3>🛠️ MATÉRIEL NÉCESSAIRE</h3><ul>[Liste précise d'outils et de pièces]</ul></div>
        <div class='section'><h3>⚙️ PROCÉDURE DE RÉPARATION</h3><ol>[Étapes techniques pas-à-pas]</ol></div>
        """
        
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}] + 
                [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in imgs_b64]}]
        
        # EXÉCUTION LLAMA 4 SCOUT (STABILISÉ)
        res = client.chat.completions.create(
            model=MODEL_PROD,
            messages=msgs,
            temperature=0, # AUCUNE CRÉATIVITÉ
            top_p=1,
            seed=42 # GRAINE FIXE POUR RÉSULTAT IDENTIQUE
        )
        
        report = res.choices[0].message.content
        links = get_market_data(context)
        footer = f"<div class='section'><h3>🔗 RESSOURCES & TUTO</h3><ul>{links}</ul></div>" if links else ""

        return f"<div id='final-report'>{report}{footer}</div>"

    except Exception as e:
        return f"<div style='color:red; font-weight:bold;'>ERREUR CRITIQUE API : {str(e)}</div>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>FixIt Pro 4.0</title>
    <style>
        :root { --main: #1e293b; --accent: #2563eb; --bg: #f8fafc; }
        body { font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--main); padding: 15px; margin: 0; }
        .app { max-width: 500px; margin: auto; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 20px; }
        .btn-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px; }
        .btn { border: none; padding: 14px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-cam { background: var(--accent); color: white; }
        .btn-mic { background: #e2e8f0; color: #475569; }
        .btn-reset { background: #1e293b; color: white; width: 100%; margin-top: 10px; }
        .btn-run { background: #ef4444; color: white; width: 100%; margin-top: 15px; font-size: 1.1rem; }
        #preview { display: flex; gap: 5px; margin: 10px 0; overflow-x: auto; }
        .thumb { width: 70px; height: 70px; object-fit: cover; border-radius: 6px; border: 1px solid #ddd; }
        textarea { width: 100%; border: 1.5px solid #e2e8f0; border-radius: 8px; padding: 10px; box-sizing: border-box; font-size: 1rem; }
        #out { margin-top: 20px; }
        .section { padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
        .section h3 { margin: 0 0 8px 0; font-size: 0.85rem; color: #64748b; text-transform: uppercase; }
        #status { display: none; text-align: center; color: var(--accent); font-weight: bold; padding: 10px; }
    </style>
</head>
<body>
    <div class="app">
        <h2 style="text-align:center; margin-top:0;">FIXIT PRO <small>v4.0</small></h2>
        <div class="btn-row">
            <button class="btn btn-cam" onclick="document.getElementById('f').click()">📸 PHOTO</button>
            <button class="btn btn-mic" id="mBtn" onclick="toggleMic()">🎤 DICTÉE</button>
        </div>
        <button class="btn btn-reset" onclick="resetAll()">🔄 NOUVEAU DIAGNOSTIC</button>
        
        <input type="file" id="f" accept="image/*" capture="environment" multiple hidden onchange="hFiles(this)">
        <div id="preview"></div>
        <textarea id="ctx" rows="2" placeholder="Symptômes constatés..."></textarea>
        
        <button class="btn btn-run" id="go" onclick="process()">GÉNÉRER LE RAPPORT</button>
        <div id="status">⚡ ANALYSE LLAMA 4 EN COURS...</div>
        <div id="out"></div>
    </div>
    <script>
        let photos = [];
        const out = document.getElementById('out');
        const ctx = document.getElementById('ctx');

        window.onload = () => {
            const last = localStorage.getItem('proReport');
            if(last) out.innerHTML = "<div style='opacity:0.6; font-size:0.8rem;'>Dernier diagnostic sauvegardé :</div>" + last;
        };

        function hFiles(i) {
            for(let f of i.files) {
                photos.push(f);
                let r = new FileReader();
                r.onload = (e) => {
                    let img = document.createElement('img');
                    img.src = e.target.result; img.className = 'thumb';
                    document.getElementById('preview').appendChild(img);
                };
                r.readAsDataURL(f);
            }
        }

        function resetAll() {
            if(confirm("Démarrer un nouveau diagnostic ?")) {
                localStorage.removeItem('proReport');
                window.location.reload();
            }
        }

        function toggleMic() {
            const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
            if(!Speech) return;
            const rec = new Speech(); rec.lang = 'fr-FR';
            rec.onresult = (e) => { ctx.value = e.results[0][0].transcript; };
            rec.start();
        }

        async function compress(file) {
            return new Promise(res => {
                const img = new Image(); img.src = URL.createObjectURL(file);
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const max = 1000; let w = img.width, h = img.height;
                    if(w > h && w > max) { h *= max/w; w = max; } else if(h > max) { w *= max/h; h = max; }
                    canvas.width = w; canvas.height = h;
                    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                    canvas.toBlob(blob => res(blob), 'image/jpeg', 0.8);
                }
            });
        }

        async function process() {
            if(!photos.length) return alert("Prendre une photo");
            document.getElementById('status').style.display = 'block';
            document.getElementById('go').disabled = true;
            const fd = new FormData();
            for(let p of photos) fd.append('images', await compress(p));
            fd.append('context', ctx.value);
            try {
                const res = await fetch('/analyze', { method: 'POST', body: fd });
                const html = await res.text();
                out.innerHTML = html;
                localStorage.setItem('proReport', html);
            } catch(e) { alert("Erreur API"); }
            finally { 
                document.getElementById('status').style.display = 'none';
                document.getElementById('go').disabled = false;
            }
        }
    </script>
</body>
</html>
"""
