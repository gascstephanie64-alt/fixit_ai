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

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

def search_real_links(query: str):
    results = {"vids": [], "links": []}
    try:
        with DDGS() as ddgs:
            v = list(ddgs.text(f"site:youtube.com tuto reparation {query}", max_results=2))
            l = list(ddgs.text(f"acheter louer outils {query} leroy merlin loxam", max_results=3))
            results["vids"] = v
            results["links"] = l
    except: pass
    return results

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    try:
        imgs_b64 = [base64.b64encode(await i.read()).decode('utf-8') for i in images]
        
        # Diagnostic Vision
        prompt_v = f"Expert Maintenance. Diagnostic strict via photos. Contexte: {context}. Identifie panne et outils precis."
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt_v}] + 
                [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in imgs_b64]}]
        
        diag = client.chat.completions.create(model=MODEL_VISION, messages=msgs, temperature=0).choices[0].message.content
        
        # Sourcing & Tuto
        web = search_real_links(context or "reparation")
        prompt_t = f"Diagnostic: {diag}. Redige protocole technique SOP (Standard Operating Procedure) HTML. Pas de blabla."
        tuto = client.chat.completions.create(model=MODEL_TEXT, messages=[{"role": "user", "content": prompt_t}], temperature=0).choices[0].message.content
        
        # Formatage Final
        links_html = "".join([f"<li><a href='{x['href']}' target='_blank'>{x['title']}</a></li>" for x in web['vids'] + web['links']])
        return f"<div class='report'>{diag}{tuto}<ul>{links_html}</ul></div>"
    except Exception as e:
        return f"<div class='err'>Erreur: {str(e)}</div>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>FIXIT PRO</title>
    <style>
        body { font-family: monospace; background: #0f172a; color: #f8fafc; padding: 15px; margin: 0; }
        .container { max-width: 600px; margin: auto; border: 1px solid #334155; padding: 20px; background: #1e293b; }
        .ctrl-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .btn { background: #3b82f6; border: none; padding: 15px; color: white; font-weight: bold; cursor: pointer; text-transform: uppercase; }
        .btn-reset { background: #64748b; }
        .btn-run { background: #ef4444; width: 100%; margin-top: 10px; font-size: 1.1rem; }
        #preview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin: 10px 0; }
        .thumb { width: 100%; height: 60px; object-fit: cover; border: 1px solid #475569; }
        textarea { width: 100%; background: #0f172a; color: #22c55e; border: 1px solid #334155; padding: 10px; box-sizing: border-box; font-family: monospace; }
        .report { background: white; color: #0f172a; padding: 15px; margin-top: 20px; border-radius: 4px; }
        .report a { color: #2563eb; }
        #loading { display: none; color: #fbbf24; text-align: center; padding: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="text-align:center; color:#ef4444;">FIXIT PRO - SYSTEM</h2>
        
        <div class="ctrl-grid">
            <button class="btn" onclick="document.getElementById('f').click()">📷 PHOTOS</button>
            <button class="btn" id="m" onclick="runMic()">🎤 DICTION</button>
            <button class="btn btn-reset" style="grid-column: span 2;" onclick="resetAll()">🔄 NOUVEAU DIAGNOSTIC</button>
        </div>

        <input type="file" id="f" accept="image/*" capture="environment" multiple hidden onchange="pv(this)">
        <div id="preview"></div>
        
        <textarea id="t" rows="4" placeholder="DESCRIPTION TECHNIQUE..."></textarea>
        
        <button class="btn btn-run" onclick="send()">LANCER L'ANALYSE</button>
        
        <div id="loading">TRAITEMENT EN COURS...</div>
        <div id="out"></div>
    </div>

    <script>
        let filesList = [];
        const out = document.getElementById('out');
        const t = document.getElementById('t');

        function pv(input) {
            for(let file of input.files) {
                filesList.push(file);
                let r = new FileReader();
                r.onload = (e) => {
                    let img = document.createElement('img');
                    img.src = e.target.result; img.className = 'thumb';
                    document.getElementById('preview').appendChild(img);
                };
                r.readAsDataURL(file);
            }
        }

        function resetAll() {
            filesList = [];
            document.getElementById('preview').innerHTML = "";
            t.value = "";
            out.innerHTML = "";
            document.getElementById('f').value = "";
        }

        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'fr-FR';
        recognition.onresult = (e) => { t.value += e.results[0][0].transcript; };

        function runMic() {
            try { recognition.start(); } catch(e) { recognition.stop(); }
        }

        async function compress(file) {
            return new Promise(res => {
                const img = new Image(); img.src = URL.createObjectURL(file);
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const scale = Math.min(1024 / img.width, 1024 / img.height);
                    canvas.width = img.width * scale; canvas.height = img.height * scale;
                    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                    canvas.toBlob(blob => res(blob), 'image/jpeg', 0.8);
                }
            });
        }

        async function send() {
            if(!filesList.length) return alert("PHOTOS REQUISES");
            document.getElementById('loading').style.display = 'block';
            const fd = new FormData();
            for(let f of filesList) fd.append('images', await compress(f));
            fd.append('context', t.value);
            
            try {
                const res = await fetch('/analyze', { method: 'POST', body: fd });
                out.innerHTML = await res.text();
            } catch(e) { out.innerHTML = "ERREUR SERVEUR"; }
            finally { document.getElementById('loading').style.display = 'none'; }
        }
    </script>
</body>
</html>
    """
