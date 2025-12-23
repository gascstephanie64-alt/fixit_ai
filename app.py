import os
import base64
import json
import asyncio
from typing import List
from fastapi import FastAPI, UploadFile, Form, File, HTTPException
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

# Configuration des Modèles
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

# --- LOGIQUE DE RECHERCHE WEB (Sourcing & Tutos) ---
async def fetch_sourcing_data(query: str):
    """Recherche ciblée sur les enseignes FR et YouTube."""
    try:
        with DDGS() as ddgs:
            # Recherche de tutoriels
            vids = [r for r in ddgs.text(f"tuto vidéo youtube réparation {query}", max_results=2)]
            # Recherche de commerces/location
            stores = [r for r in ddgs.text(f"acheter ou louer outils {query} Leroy Merlin Castorama Kiloutou Loxam Lidl Brico Dépôt", max_results=3)]
            
            html = "<div class='card sourcing'><h4>📺 Tutoriels & Vidéos</h4><ul>"
            for v in vids:
                html += f"<li><a href='{v['href']}' target='_blank'>▶️ {v['title']}</a></li>"
            html += "</ul><h4>🛒 Où se procurer le matériel ?</h4><ul>"
            for s in stores:
                html += f"<li><a href='{s['href']}' target='_blank'>📍 {s['title']}</a></li>"
            html += "</ul><p><small>Enseignes suggérées : Leroy Merlin, Castorama, Brico Dépôt, Lidl (Parkside), Kiloutou, Loxam.</small></p></div>"
            return html
    except:
        return "<div class='card info'>Recherche web indisponible.</div>"

# --- PIPELINE MULTI-AGENTS ---
async def run_fixit_pipeline(images_b64: List[str], context: str):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # AGENT 1 : VISION & DIAGNOSTIC (Llama 4 Scout)
    vision_content = [{"type": "text", "text": f"ANALYSE DE PRODUCTION. Contexte : {context}. Analyse les images et donne un diagnostic technique précis."}]
    for img in images_b64:
        vision_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
    
    diag_res = client.chat.completions.create(
        model=MODEL_VISION,
        messages=[{"role": "user", "content": vision_content}],
        temperature=0.1
    ).choices[0].message.content

    # AGENT 2 & 3 : ANALYSE DE RISQUE, SÉCURITÉ ET LOGISTIQUE (Llama 3.3 70B)
    prompt_logic = f"""
    Basé sur ce diagnostic : {diag_res}
    Génère un rapport HTML structuré avec ces sections :
    1. <div class='card risk'>SCORE DE RISQUE : X/10. (Si >7, RECOMMANDATION PROFESSIONNELLE OBLIGATOIRE).
    2. SÉCURITÉ : EPI nécessaires (gants, lunettes, coupure circuit).
    3. LOGISTIQUE OUTILS : 
       - À ACHETER (consommables ou outils <30€ type tournevis, joints chez Lidl/Brico Dépôt).
       - À LOUER (outillage lourd type perfo, déboucheur haute pression chez Kiloutou/Loxam).
    4. GUIDE PAS-À-PAS : Étapes de réparation ultra-simplifiées.
    """
    
    logic_res = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role": "user", "content": prompt_logic}]
    ).choices[0].message.content
    
    sourcing_html = await fetch_sourcing_data(context if context else "bricolage")
    
    return f"{diag_res}{logic_res}{sourcing_html}"

# --- ROUTES ---
@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    try:
        images_b64 = []
        for img in images:
            content = await img.read()
            images_b64.append(base64.b64encode(content).decode('utf-8'))
        
        final_html = await run_fixit_pipeline(images_b64, context)
        return final_html
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
    <title>FixIt AI PRO - Expert DIY</title>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <style>
        :root { --p: #f97316; --s: #2563eb; --d: #dc2626; --bg: #f8fafc; }
        body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); margin: 0; padding: 10px; color: #1e293b; }
        .app-card { max-width: 650px; margin: auto; background: white; padding: 20px; border-radius: 24px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); border-top: 10px solid var(--p); }
        h1 { color: var(--p); text-align: center; margin: 10px 0; font-size: 1.6rem; }
        
        /* Boutons */
        .btn-group { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px; }
        .btn { border: none; padding: 14px; border-radius: 14px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; color: white; transition: 0.2s; font-size: 0.9rem; }
        .btn-main { background: #475569; grid-column: span 2; }
        .btn-sec { background: var(--s); }
        .btn-history { background: #0f172a; }
        .btn-mic { background: #7c3aed; }
        .btn-run { background: var(--p); width: 100%; font-size: 1.1rem; box-shadow: 0 4px 14px rgba(249, 115, 22, 0.4); }
        .recording { background: var(--d) !important; animation: pulse 1.5s infinite; }
        
        /* Zones */
        #preview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 10px 0; }
        .pv-item { width: 100%; height: 70px; object-fit: cover; border-radius: 10px; border: 2px solid #e2e8f0; }
        textarea { width: 100%; padding: 15px; border: 2px solid #e2e8f0; border-radius: 14px; box-sizing: border-box; font-family: inherit; font-size: 1rem; margin-top: 10px; }
        
        /* Rendu Rapport */
        .card { padding: 18px; border-radius: 16px; margin-top: 15px; border-left: 6px solid #e2e8f0; background: white; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        .risk { border-left-color: var(--d); background: #fef2f2; }
        .sourcing { border-left-color: var(--s); background: #eff6ff; }
        .history-item { padding: 10px; border-bottom: 1px solid #eee; font-size: 0.8rem; cursor: pointer; }
        
        #loading { display: none; text-align: center; padding: 30px; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid var(--p); border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="app-card">
        <h1>🛠️ FixIt AI PRO</h1>
        
        <div class="btn-group">
            <button class="btn btn-main" onclick="document.getElementById('fileIn').click()">📸 AJOUTER DES PHOTOS</button>
            <button id="micBtn" class="btn btn-mic" onclick="toggleMic()">🎤 DICTER</button>
            <button class="btn btn-sec" onclick="startQR()">🔳 SCAN QR</button>
            <button class="btn btn-history" onclick="toggleHistory()">📜 HISTORIQUE</button>
        </div>

        <input type="file" id="fileIn" accept="image/*" capture="environment" multiple hidden onchange="handleFiles(this)">
        <div id="preview-grid"></div>
        <div id="qr-reader" style="display:none; border-radius: 12px; overflow: hidden;"></div>

        <textarea id="ctx" placeholder="Détails du problème..."></textarea>
        
        <button id="runBtn" class="btn btn-run" onclick="runAnalysis()">LANCER LE SHAZAM RÉPARATION</button>

        <div id="loading">
            <div class="spinner"></div>
            <p>Analyse des experts Llama 4 Scout...</p>
        </div>

        <div id="history-panel" style="display:none; background:#f1f5f9; border-radius:12px; margin-top:15px; padding:10px;">
            <h4>Historique des Diagnostics</h4>
            <div id="history-list"></div>
            <button onclick="clearHistory()" style="font-size:0.7rem;">Effacer tout</button>
        </div>

        <div id="output"></div>
    </div>

    <script>
        let files = [];
        const out = document.getElementById('output');

        // Initialisation : Charger dernier diagnostic & historique
        window.onload = () => {
            const last = localStorage.getItem('last_fixit');
            if(last) out.innerHTML = "<h4>Dernier Diagnostic :</h4>" + last;
            renderHistory();
        };

        function handleFiles(input) {
            const grid = document.getElementById('preview-grid');
            for(let f of input.files) {
                files.push(f);
                const r = new FileReader();
                r.onload = (e) => {
                    const img = document.createElement('img');
                    img.src = e.target.result; img.className = 'pv-item';
                    grid.appendChild(img);
                };
                r.readAsDataURL(f);
            }
        }

        // --- VOCAL ---
        const recognition = window.SpeechRecognition || window.webkitSpeechRecognition ? new (window.SpeechRecognition || window.webkitSpeechRecognition)() : null;
        if(recognition) {
            recognition.lang = 'fr-FR';
            recognition.onresult = (e) => {
                document.getElementById('ctx').value += " " + e.results[0][0].transcript;
                toggleMic();
            };
        }

        function toggleMic() {
            const b = document.getElementById('micBtn');
            if(b.classList.contains('recording')) {
                recognition.stop(); b.classList.remove('recording'); b.innerHTML = "🎤 DICTER";
            } else {
                recognition.start(); b.classList.add('recording'); b.innerHTML = "🛑 ÉCOUTE...";
            }
        }

        // --- QR CODE ---
        function startQR() {
            const r = document.getElementById('qr-reader'); r.style.display = 'block';
            const s = new Html5QrcodeScanner("qr-reader", { fps: 10, qrbox: 250 });
            s.render((txt) => {
                document.getElementById('ctx').value += " [QR Info: " + txt + "]";
                s.clear(); r.style.display = 'none';
            });
        }

        // --- HISTORIQUE ---
        function toggleHistory() {
            const p = document.getElementById('history-panel');
            p.style.display = p.style.display === 'none' ? 'block' : 'none';
        }

        function renderHistory() {
            const list = document.getElementById('history-list');
            const data = JSON.parse(localStorage.getItem('fixit_history') || '[]');
            list.innerHTML = data.length ? "" : "Aucun historique.";
            data.reverse().forEach((item, idx) => {
                const d = document.createElement('div');
                d.className = 'history-item';
                d.innerHTML = `<strong>${item.date}</strong>: ${item.title}`;
                d.onclick = () => { out.innerHTML = item.html; };
                list.appendChild(d);
            });
        }

        function clearHistory() { localStorage.removeItem('fixit_history'); renderHistory(); }

        // --- ANALYSE ---
        async function runAnalysis() {
            if(!files.length) return alert("Photo obligatoire");
            const load = document.getElementById('loading');
            const btn = document.getElementById('runBtn');
            load.style.display = 'block'; btn.disabled = true;

            const fd = new FormData();
            files.forEach(f => fd.append('images', f));
            fd.append('context', document.getElementById('ctx').value);

            try {
                const res = await fetch('/analyze', { method: 'POST', body: fd });
                const html = await res.text();
                out.innerHTML = html;
                
                // Sauvegarde
                localStorage.setItem('last_fixit', html);
                const history = JSON.parse(localStorage.getItem('fixit_history') || '[]');
                history.push({ 
                    date: new Date().toLocaleString(), 
                    title: document.getElementById('ctx').value.substring(0, 30) || "Réparation", 
                    html: html 
                });
                localStorage.setItem('fixit_history', JSON.stringify(history.slice(-10))); // Garder les 10 derniers
                renderHistory();
            } catch (e) {
                out.innerHTML = "Erreur de connexion au serveur.";
            } finally {
                load.style.display = 'none'; btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""
