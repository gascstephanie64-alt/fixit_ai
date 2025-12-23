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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"

def get_market_data(query: str):
    """Recherche réelle. Retourne une liste vide si rien de pertinent."""
    links = []
    try:
        with DDGS() as ddgs:
            search_query = f"{query} tutoriel reparation outils leroy merlin kiloutou"
            results = list(ddgs.text(search_query, max_results=4))
            for r in results:
                links.append(f"<li><a href='{r['href']}' target='_blank'>{r['title']}</a></li>")
    except: pass
    return "".join(links)

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    try:
        imgs_b64 = [base64.b64encode(await i.read()).decode('utf-8') for i in images]
        
        # PROMPT UNIQUE : Force le formatage Pro et évite les répétitions
        prompt = f"""
        Tu es un expert en maintenance industrielle et bâtiment. 
        Analyse les photos avec ce contexte : {context}.
        
        Génère un rapport HTML structuré avec ces sections précises :
        1. <div class='section'><h3>🔍 DIAGNOSTIC TECHNIQUE</h3><p>Description factuelle du problème identifié.</p></div>
        2. <div class='section risk-card'><h3>⚠️ ÉVALUATION DU RISQUE : [X]/10</h3><p>Précautions de sécurité obligatoires.</p></div>
        3. <div class='section'><h3>🛠️ LISTE DU MATÉRIEL</h3><ul><li>Pièces spécifiques</li><li>Outillage nécessaire</li></ul></div>
        4. <div class='section'><h3>⚙️ PROCÉDURE DE RÉPARATION (SOP)</h3><ol><li>Action 1</li><li>Action 2...</li></ol></div>
        
        IMPORTANT : Pas d'introduction, pas de conclusion, pas de répétitions. Utilise des balises HTML propres.
        """
        
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}] + 
                [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in imgs_b64]}]
        
        diag_res = client.chat.completions.create(model=MODEL_VISION, messages=msgs, temperature=0)
        report_content = diag_res.choices[0].message.content

        # Recherche de ressources réelles
        links_html = get_market_data(context)
        footer = ""
        if links_html:
            footer = f"<div class='section links'><h3>🔗 RESSOURCES & SOURCING</h3><ul>{links_html}</ul></div>"

        return f"<div class='report-wrapper'>{report_content}{footer}</div>"

    except Exception as e:
        return f"<div class='error'>ERREUR : {str(e)}</div>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>FixIt Pro</title>
    <style>
        :root { --accent: #2563eb; --danger: #be123c; --bg: #f8fafc; --text: #1e293b; }
        body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 15px; }
        .app-card { max-width: 550px; margin: auto; background: white; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1); overflow: hidden; }
        header { background: #1e293b; color: white; padding: 20px; text-align: center; }
        .ui-body { padding: 20px; }
        .btn-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .btn { border: none; padding: 14px; border-radius: 10px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-blue { background: var(--accent); color: white; }
        .btn-gray { background: #e2e8f0; color: #475569; }
        .btn-main { width: 100%; background: #1e293b; color: white; font-size: 1rem; margin-top: 15px; }
        textarea { width: 100%; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 12px; box-sizing: border-box; font-size: 1rem; resize: none; margin-top: 10px; }
        #preview { display: flex; gap: 10px; overflow-x: auto; margin-bottom: 10px; }
        .thumb { width: 80px; height: 80px; object-fit: cover; border-radius: 8px; border: 2px solid #e2e8f0; }
        
        /* Formatage du Rapport */
        .report-wrapper { margin-top: 25px; border-top: 2px solid #f1f5f9; }
        .section { padding: 15px 0; border-bottom: 1px solid #f1f5f9; }
        .section h3 { margin: 0 0 10px 0; font-size: 0.9rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
        .risk-card { background: #fff1f2; border-radius: 10px; padding: 15px; border: 1px solid #fecdd3; }
        .links a { color: var(--accent); text-decoration: none; font-weight: 500; }
        #loading { display: none; text-align: center; padding: 20px; color: var(--accent); font-weight: bold; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="app-card">
        <header><strong>FIXIT PRO</strong> <small>Expert System</small></header>
        <div class="ui-body">
            <div class="btn-row">
                <button class="btn btn-blue" onclick="document.getElementById('f').click()">📸 PHOTOS</button>
                <button class="btn btn-gray" id="micBtn" onclick="toggleMic()">🎤 DICTÉE</button>
            </div>
            <button class="btn btn-gray" style="width:100%" onclick="window.location.reload()">🔄 NOUVEAU DIAGNOSTIC</button>
            
            <input type="file" id="f" accept="image/*" capture="environment" multiple hidden onchange="hFiles(this)">
            <div id="preview"></div>
            
            <textarea id="ctx" rows="3" placeholder="Notes complémentaires (facultatif)..."></textarea>
            
            <button class="btn btn-main" id="go" onclick="process()">GÉNÉRER LE RAPPORT</button>
            <div id="loading">🛠️ GÉNÉRATION DU RAPPORT...</div>
            <div id="out"></div>
        </div>
    </div>
    <script>
        let photos = [];
        const ctx = document.getElementById('ctx');
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
        const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
        const rec = Speech ? new Speech() : null;
        if(rec) {
            rec.lang = 'fr-FR';
            rec.onresult = (e) => { ctx.value += e.results[0][0].transcript; };
            rec.onend = () => { document.getElementById('micBtn').style.background = "#e2e8f0"; };
        }
        function toggleMic() {
            if(!rec) return;
            document.getElementById('micBtn').style.background = "#fecdd3";
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
                    canvas.toBlob(blob => res(blob), 'image/jpeg', 0.7);
                }
            });
        }
        async function process() {
            if(!photos.length) return alert("Photo manquante");
            document.getElementById('loading').style.display = 'block';
            document.getElementById('go').disabled = true;
            const fd = new FormData();
            for(let p of photos) fd.append('images', await compress(p));
            fd.append('context', ctx.value);
            try {
                const res = await fetch('/analyze', { method: 'POST', body: fd });
                document.getElementById('out').innerHTML = await res.text();
            } catch(e) { alert("Erreur réseau"); }
            finally { 
                document.getElementById('loading').style.display = 'none';
                document.getElementById('go').disabled = false;
            }
        }
    </script>
</body>
</html>
"""
