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

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Constantes de modèle
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

def get_market_data(query: str):
    """Récupère les liens réels de tutoriels et de commerce."""
    data = {"vids": [], "shops": []}
    try:
        with DDGS() as ddgs:
            # Tutos YouTube
            v = list(ddgs.text(f"site:youtube.com tuto reparation {query}", max_results=2))
            # Commerces et Location FR
            s = list(ddgs.text(f"{query} acheter louer outils leroy merlin castorama kiloutou loxam", max_results=3))
            data["vids"] = v
            data["shops"] = s
    except: pass
    return data

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    try:
        # 1. Encodage images
        imgs_b64 = [base64.b64encode(await i.read()).decode('utf-8') for i in images]
        
        # 2. Diagnostic Technique (Temperature 0 pour stabilité totale)
        prompt_v = f"""[STRICT MODE] Tu es un expert en maintenance. Analyse les photos. 
        Contexte : {context}
        RETOURNE EXCLUSIVEMENT : 
        1. Identification technique de la panne.
        2. Score de Risque (1-10).
        3. Liste précise des outils nécessaires.
        Ne sois pas créatif, reste factuel."""
        
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt_v}] + 
                [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in imgs_b64]}]
        
        diag = client.chat.completions.create(
            model=MODEL_VISION, 
            messages=msgs, 
            temperature=0, # Force la répétabilité
            seed=42        # Graine pour résultat identique
        ).choices[0].message.content

        # 3. Recherche de liens réels
        market = get_market_data(context or "bricolage")
        
        # 4. Génération de la procédure (Standard Operating Procedure)
        prompt_t = f"Diagnostic : {diag}. Rédige la procédure SOP de réparation en HTML. Ajoute une section : 'Acheter ou Louer ?' basée sur la complexité."
        tuto = client.chat.completions.create(
            model=MODEL_TEXT, 
            messages=[{"role": "user", "content": prompt_t}],
            temperature=0
        ).choices[0].message.content

        # 5. Construction du rapport formaté
        links_html = "<h3>🔗 Ressources & Achat / Location</h3><ul>"
        for item in (market['vids'] + market['shops']):
            links_html += f"<li><a href='{item['href']}' target='_blank'>{item['title']}</a></li>"
        links_html += "</ul>"

        return f"<div class='report-container'>{diag}{tuto}{links_html}</div>"

    except Exception as e:
        return f"<div class='error'>ERREUR TECHNIQUE : {str(e)}</div>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>FixIt Pro V3</title>
    <style>
        :root { --main: #e11d48; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { font-family: ui-monospace, SFMono-Regular, monospace; background: var(--bg); color: var(--text); padding: 15px; margin: 0; }
        .app { max-width: 600px; margin: auto; border: 1px solid #334155; padding: 20px; background: var(--card); border-radius: 8px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .btn { background: #334155; border: 1px solid #475569; padding: 15px; color: white; font-weight: bold; cursor: pointer; border-radius: 4px; }
        .btn-run { background: var(--main); width: 100%; font-size: 1.2rem; border: none; margin-top: 15px; }
        .btn-new { background: #64748b; grid-column: span 2; }
        #preview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin: 10px 0; }
        .thumb { width: 100%; aspect-ratio: 1; object-fit: cover; border: 1px solid var(--main); }
        textarea { width: 100%; background: #020617; color: #4ade80; border: 1px solid #334155; padding: 12px; box-sizing: border-box; font-family: monospace; font-size: 1rem; }
        .report-container { background: white; color: #0f172a; padding: 20px; margin-top: 20px; line-height: 1.6; border-radius: 4px; }
        .report-container h2, h3 { color: var(--main); border-bottom: 1px solid #ddd; }
        #status { display: none; color: #fbbf24; text-align: center; margin: 15px 0; font-weight: bold; }
    </style>
</head>
<body>
    <div class="app">
        <h2 style="text-align:center; color:var(--main);">FIXIT PRO EXPERT</h2>
        
        <div class="grid">
            <button class="btn" onclick="document.getElementById('f').click()">📷 CAPTURE PHOTOS</button>
            <button class="btn" id="micBtn" onclick="toggleMic()">🎤 DICTION</button>
            <button class="btn btn-new" onclick="window.location.reload()">🔄 NOUVEAU DIAGNOSTIC</button>
        </div>

        <input type="file" id="f" accept="image/*" capture="environment" multiple hidden onchange="handleFiles(this)">
        <div id="preview"></div>
        
        <textarea id="ctx" rows="3" placeholder="CONTEXTE OU SYMPTÔMES..."></textarea>
        
        <button class="btn btn-run" onclick="process()">LANCER LE DIAGNOSTIC TECHNIQUE</button>
        
        <div id="status">ANALYSE EN COURS (LLAMA 4 STABLE)...</div>
        <div id="out"></div>
    </div>

    <script>
        let photos = [];
        const out = document.getElementById('out');
        const ctx = document.getElementById('ctx');

        function handleFiles(input) {
            for(let file of input.files) {
                photos.push(file);
                let reader = new FileReader();
                reader.onload = (e) => {
                    let img = document.createElement('img');
                    img.src = e.target.result; img.className = 'thumb';
                    document.getElementById('preview').appendChild(img);
                };
                reader.readAsDataURL(file);
            }
        }

        // --- DICTION ---
        const recognition = window.SpeechRecognition || window.webkitSpeechRecognition ? new (window.SpeechRecognition || window.webkitSpeechRecognition)() : null;
        if(recognition) {
            recognition.lang = 'fr-FR';
            recognition.continuous = false;
            recognition.onresult = (e) => { ctx.value += e.results[0][0].transcript; };
            recognition.onend = () => { document.getElementById('micBtn').style.borderColor = "#475569"; };
        }

        function toggleMic() {
            if(!recognition) return alert("Micro non supporté");
            document.getElementById('micBtn').style.borderColor = "red";
            recognition.start();
        }

        // --- COMPRESSION ---
        async function compress(file) {
            return new Promise(res => {
                const img = new Image(); img.src = URL.createObjectURL(file);
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const max = 1024;
                    let w = img.width, h = img.height;
                    if(w > h && w > max) { h *= max/w; w = max; }
                    else if(h > max) { w *= max/h; h = max; }
                    canvas.width = w; canvas.height = h;
                    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                    canvas.toBlob(blob => res(blob), 'image/jpeg', 0.8);
                }
            });
        }

        // --- ENVOI ---
        async function process() {
            if(!photos.length) return alert("ERREUR : PHOTOS MANQUANTES");
            document.getElementById('status').style.display = 'block';
            out.innerHTML = "";
            
            const fd = new FormData();
            for(let p of photos) fd.append('images', await compress(p));
            fd.append('context', ctx.value);
            
            try {
                const res = await fetch('/analyze', { method: 'POST', body: fd });
                out.innerHTML = await res.text();
            } catch(e) { out.innerHTML = "<p style='color:red'>ERREUR SERVEUR</p>"; }
            finally { document.getElementById('status').style.display = 'none'; }
        }
    </script>
</body>
</html>
