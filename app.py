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

MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

def get_market_data(query: str):
    data = {"vids": [], "shops": []}
    try:
        with DDGS() as ddgs:
            v = list(ddgs.text(f"site:youtube.com tuto reparation {query}", max_results=2))
            s = list(ddgs.text(f"{query} acheter louer outils leroy merlin castorama kiloutou", max_results=3))
            data["vids"] = v
            data["shops"] = s
    except: pass
    return data

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    try:
        imgs_b64 = [base64.b64encode(await i.read()).decode('utf-8') for i in images]
        
        prompt_v = f"""[STRICT MODE] Expert maintenance. Analyse les photos.
        Contexte : {context}
        RETOURNE EXCLUSIVEMENT :
        1. Diagnostic technique précis.
        2. Score de Risque (1-10).
        3. Liste exhaustive des outils et pièces.
        Formatte en HTML simple."""
        
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt_v}] + 
                [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in imgs_b64]}]
        
        diag = client.chat.completions.create(model=MODEL_VISION, messages=msgs, temperature=0, seed=42).choices[0].message.content
        market = get_market_data(context or "bricolage")
        
        prompt_t = f"Diagnostic : {diag}. Rédige la procédure technique SOP pas-à-pas en HTML. Ajoute une section 'Où acheter/louer' avec les enseignes Leroy Merlin, Castorama ou Kiloutou."
        tuto = client.chat.completions.create(model=MODEL_TEXT, messages=[{"role": "user", "content": prompt_t}], temperature=0).choices[0].message.content

        links_html = "<h3>🔗 Ressources & Sourcing Réel</h3><ul>"
        for item in (market['vids'] + market['shops']):
            links_html += f"<li><a href='{item['href']}' target='_blank'>{item['title']}</a></li>"
        links_html += "</ul>"

        return f"<div class='report-container'>{diag}{tuto}{links_html}</div>"
    except Exception as e:
        return f"<div style='color:red'>Erreur technique : {str(e)}</div>"

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
        body { font-family: monospace; background: var(--bg); color: var(--text); padding: 15px; margin: 0; }
        .app { max-width: 600px; margin: auto; border: 1px solid #334155; padding: 20px; background: var(--card); border-radius: 8px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .btn { background: #334155; border: 1px solid #475569; padding: 15px; color: white; font-weight: bold; cursor: pointer; border-radius: 4px; }
        .btn-run { background: var(--main); width: 100%; font-size: 1.2rem; border: none; margin-top: 15px; }
        .btn-new { background: #64748b; grid-column: span 2; }
        #preview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin: 10px 0; }
        .thumb { width: 100%; aspect-ratio: 1; object-fit: cover; border: 1px solid var(--main); }
        textarea { width: 100%; background: #020617; color: #4ade80; border: 1px solid #334155; padding: 12px; box-sizing: border-box; font-size: 1rem; }
        .report-container { background: white; color: #0f172a; padding: 20px; margin-top: 20px; border-radius: 4px; }
        #status { display: none; color: #fbbf24; text-align: center; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="app">
        <h2 style="text-align:center; color:var(--main);">FIXIT PRO EXPERT</h2>
        <div class="grid">
            <button class="btn" onclick="document.getElementById('f').click()">📷 PHOTOS</button>
            <button class="btn" id="micBtn" onclick="toggleMic()">🎤 DICTION</button>
            <button class="btn btn-new" onclick="window.location.reload()">🔄 NOUVEAU DIAGNOSTIC</button>
        </div>
        <input type="file" id="f" accept="image/*" capture="environment" multiple hidden onchange="handleFiles(this)">
        <div id="preview"></div>
        <textarea id="ctx" rows="3" placeholder="Symptômes..."></textarea>
        <button class="btn btn-run" onclick="process()">LANCER LE DIAGNOSTIC</button>
        <div id="status">ANALYSE EN COURS...</div>
        <div id="out"></div>
    </div>
    <script>
        let photos = [];
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
        const recognition = (window.SpeechRecognition || window.webkitSpeechRecognition) ? new (window.SpeechRecognition || window.webkitSpeechRecognition)() : null;
        if(recognition) {
            recognition.lang = 'fr-FR';
            recognition.onresult = (e) => { ctx.value += e.results[0][0].transcript; };
            recognition.onend = () => { document.getElementById('micBtn').style.background = "#334155"; };
        }
        function toggleMic() {
            if(!recognition) return alert("Micro non supporté");
            document.getElementById('micBtn').style.background = "red";
            recognition.start();
        }
        async function compress(file) {
            return new Promise(res => {
                const img = new Image(); img.src = URL.createObjectURL(file);
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const max = 1024; let w = img.width, h = img.height;
                    if(w > h && w > max) { h *= max/w; w = max; } else if(h > max) { w *= max/h; h = max; }
                    canvas.width = w; canvas.height = h;
                    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                    canvas.toBlob(blob => res(blob), 'image/jpeg', 0.8);
                }
            });
        }
        async function process() {
            if(!photos.length) return alert("PHOTOS MANQUANTES");
            document.getElementById('status').style.display = 'block';
            const fd = new FormData();
            for(let p of photos) fd.append('images', await compress(p));
            fd.append('context', ctx.value);
            try {
                const res = await fetch('/analyze', { method: 'POST', body: fd });
                document.getElementById('out').innerHTML = await res.text();
            } catch(e) { alert("Erreur serveur"); }
            finally { document.getElementById('status').style.display = 'none'; }
        }
    </script>
</body>
</html>
"""
