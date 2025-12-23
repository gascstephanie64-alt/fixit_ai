import os
import base64
import json
from typing import List
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from dotenv import load_dotenv
from duckduckgo_search import DDGS

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration des Modèles de production
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

async def fetch_sourcing_data(query: str):
    """Recherche ciblée YouTube et Enseignes de bricolage."""
    try:
        with DDGS() as ddgs:
            vids = [r for r in ddgs.text(f"tuto vidéo youtube réparation {query}", max_results=2)]
            stores = [r for r in ddgs.text(f"achat location outils {query} Leroy Merlin Castorama Kiloutou Brico Dépôt", max_results=3)]
            
            html = "<div class='card sourcing'><h4>📺 Vidéos & Tutos</h4><ul>"
            for v in vids: html += f"<li><a href='{v['href']}' target='_blank'>▶️ {v['title']}</a></li>"
            html += "</ul><h4>🛒 Sourcing Matériel</h4><ul>"
            for s in stores: html += f"<li><a href='{s['href']}' target='_blank'>📍 {s['title']}</a></li>"
            html += "</ul></div>"
            return html
    except: return ""

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    try:
        images_b64 = []
        for img in images:
            content = await img.read()
            images_b64.append(base64.b64encode(content).decode('utf-8'))
        
        # AGENT 1 : Vision & Diagnostic (Llama 4 Scout)
        vision_content = [{"type": "text", "text": f"Expert DIY. Analyse ces images. Contexte : {context}."}]
        for img in images_b64:
            vision_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
        
        diag_res = client.chat.completions.create(model=MODEL_VISION, messages=[{"role": "user", "content": vision_content}], temperature=0.1).choices[0].message.content

        # AGENT 2 & 3 : Risque & Tuto
        logic_prompt = f"Basé sur : {diag_res}. Donne en HTML : 1. Score de risque /10 (Alerte pro si >7). 2. Liste outils (Acheter chez Lidl/Brico vs Louer chez Kiloutou/Loxam). 3. Tuto pas-à-pas."
        logic_res = client.chat.completions.create(model=MODEL_TEXT, messages=[{"role": "user", "content": logic_prompt}]).choices[0].message.content
        
        web_html = await fetch_sourcing_data(context)
        return f"{diag_res}{logic_res}{web_html}"
    except Exception as e:
        return f"<div class='card danger'>Erreur technique : {str(e)}</div>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>FixIt AI PRO</title>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <style>
        :root { --p: #f97316; --s: #2563eb; --d: #dc2626; --bg: #f8fafc; }
        body { font-family: sans-serif; background: var(--bg); padding: 10px; margin: 0; }
        .app { max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 8px solid var(--p); }
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .btn { border: none; padding: 15px; border-radius: 12px; font-weight: bold; cursor: pointer; color: white; display: flex; align-items: center; justify-content: center; gap: 5px; }
        .btn-cam { background: #475569; grid-column: span 2; }
        .btn-mic { background: #7c3aed; }
        .btn-hist { background: #0f172a; }
        .btn-run { background: var(--p); width: 100%; font-size: 1.1rem; margin-top: 10px; }
        .recording { background: var(--d) !important; animation: pulse 1.5s infinite; }
        #pv-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin: 10px 0; }
        .pv-img { width: 100%; height: 70px; object-fit: cover; border-radius: 8px; border: 1px solid #ddd; }
        textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 10px; box-sizing: border-box; min-height: 80px; }
        .card { padding: 15px; border-radius: 12px; margin-top: 15px; border-left: 5px solid #ddd; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .danger { border-left-color: var(--d); background: #fef2f2; }
        .sourcing { border-left-color: var(--s); background: #eff6ff; }
        #loading { display: none; text-align: center; padding: 20px; color: var(--p); font-weight: bold; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <div class="app">
        <h1>🛠️ FixIt AI PRO</h1>
        <div class="btn-grid">
            <button class="btn btn-cam" onclick="document.getElementById('fin').click()">📸 AJOUTER DES PHOTOS</button>
            <button id="mBtn" class="btn btn-mic" onclick="tMic()">🎤 DICTER</button>
            <button class="btn btn-hist" onclick="tHist()">📜 HISTORIQUE</button>
        </div>
        <input type="file" id="fin" accept="image/*" capture="environment" multiple hidden onchange="hFiles(this)">
        <div id="pv-grid"></div>
        <textarea id="ctx" placeholder="Décrivez la panne..."></textarea>
        <button id="go" class="btn btn-run" onclick="run()">LANCER LE DIAGNOSTIC</button>
        <div id="loading">🚀 Analyse en cours (Llama 4 Scout)...</div>
        <div id="hist" style="display:none; background:#eee; padding:10px; border-radius:10px; margin-top:10px;"></div>
        <div id="out"></div>
    </div>

    <script>
        let files = [];
        const out = document.getElementById('out');

        window.onload = () => {
            const last = localStorage.getItem('last');
            if(last) out.innerHTML = "<h3>Dernier Diagnostic :</h3>" + last;
        };

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

        // --- COMPRESSION (Correction Erreur 413) ---
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

        // --- MICRO ---
        const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
        let rec = Rec ? new Rec() : null;
        if(rec) {
            rec.lang = 'fr-FR';
            rec.onresult = e => { document.getElementById('ctx').value += " " + e.results[0][0].transcript; tMic(); };
        }
        function tMic() {
            const b = document.getElementById('mBtn');
            if(b.classList.contains('recording')) { rec.stop(); b.classList.remove('recording'); b.innerHTML = "🎤 DICTER"; }
            else { rec.start(); b.classList.add('recording'); b.innerHTML = "🛑 ÉCOUTE..."; }
        }

        function tHist() {
            const h = document.getElementById('hist');
            const data = JSON.parse(localStorage.getItem('h') || '[]');
            h.innerHTML = data.length ? data.map(i => `<div style='cursor:pointer;border-bottom:1px solid #ccc;padding:5px' onclick='document.getElementById("out").innerHTML="${i.h.replace(/"/g,"&quot;")}"'>${i.d}</div>`).join('') : "Vide";
            h.style.display = h.style.display === 'none' ? 'block' : 'none';
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
                out.innerHTML = resHtml;
                localStorage.setItem('last', resHtml);
                const h = JSON.parse(localStorage.getItem('h') || '[]');
                h.push({ d: new Date().toLocaleString(), h: resHtml });
                localStorage.setItem('h', JSON.stringify(h.slice(-5)));
            } catch(e) { out.innerHTML = "Erreur de connexion."; }
            finally { document.getElementById('loading').style.display = 'none'; }
        }
    </script>
</body>
</html>
    """
