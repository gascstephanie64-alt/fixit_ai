import os
import base64
import httpx
import asyncio
from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from dotenv import load_dotenv
from duckduckgo_search import DDGS

load_dotenv()

app = FastAPI()

# Configuration CORS pour usage mobile PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constantes de Production
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

# --- LOGIQUE DES AGENTS ---

async def get_web_resources(query):
    """Recherche gratuite sans clé API via DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(f"tuto réparation {query} outils achat", max_results=3)]
            if not results: return "<p>Aucune ressource web trouvée.</p>"
            html = "<ul>"
            for r in results:
                html += f"<li><a href='{r['href']}' target='_blank'>🔗 {r['title']}</a></li>"
            html += "</ul>"
            return html
    except Exception:
        return "<p>Recherche web momentanément indisponible.</p>"

async def run_agents_pipeline(image_b64, context):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # AGENT 1 : Vision & Diagnostic (Llama 4 Scout)
    prompt_v = f"""
    [MISSION PRODUCTION] Tu es un expert en bâtiment et bricolage.
    Analyse cette image avec le contexte suivant : {context}.
    1. Identifie la pièce ou la panne avec précision chirurgicale.
    2. Explique la cause.
    3. Propose la méthode de réparation DIY.
    Rends une réponse en HTML (divs uniquement).
    """
    
    completion_v = client.chat.completions.create(
        model=MODEL_VISION,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt_v},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
        ]}],
        temperature=0.1
    )
    diag_html = completion_v.choices[0].message.content

    # AGENT 2 & 3 : Sécurité, Outils et Tuto (Llama 3.3 70B pour le raisonnement)
    prompt_t = f"""
    Basé sur ce diagnostic : {diag_html}
    Génère deux sections HTML :
    1. Une section <div class='card danger'> sur la SÉCURITÉ et les OUTILS nécessaires (Amateur vs Pro).
    2. Une section <div class='card steps'> avec un TUTORIEL PAS-À-PAS ultra-débutant.
    """
    
    completion_t = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[{"role": "user", "content": prompt_t}]
    )
    tuto_html = completion_t.choices[0].message.content
    
    # Sourcing Web
    web_html = await get_web_resources(context if context else "réparation domestique")
    
    return f"{diag_html}{tuto_html}<div class='card info'><h3>🛒 Où acheter / Louer ?</h3>{web_html}</div>"

# --- ROUTES FASTAPI ---

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(image: UploadFile = File(...), context: str = Form("")):
    if not os.environ.get("GROQ_API_KEY"):
        return "<div class='card danger'>ERREUR: Clé API manquante sur le serveur.</div>"
    
    try:
        img_bytes = await image.read()
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        
        result_html = await run_agents_pipeline(img_b64, context)
        return result_html
    except Exception as e:
        return f"<div class='card danger'><h3>Erreur Critique</h3><p>{str(e)}</p></div>"

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
        :root { --p: #f97316; --s: #3b82f6; --d: #ef4444; --bg: #f9fafb; }
        body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); margin: 0; padding: 15px; }
        .app { max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 8px solid var(--p); }
        h1 { color: var(--p); text-align: center; margin-bottom: 20px; }
        .btn { width: 100%; padding: 16px; border-radius: 12px; border: none; font-weight: bold; cursor: pointer; margin-bottom: 10px; font-size: 1rem; color: white; transition: 0.2s; }
        .btn-cam { background: #4b5563; }
        .btn-qr { background: var(--s); }
        .btn-run { background: var(--p); font-size: 1.2rem; margin-top: 10px; }
        #preview { width: 100%; border-radius: 12px; margin-top: 10px; display: none; }
        #reader { width: 100%; display: none; margin-top: 10px; border-radius: 12px; overflow: hidden; }
        textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 10px; margin-top: 10px; box-sizing: border-box; font-family: inherit; }
        .card { padding: 15px; border-radius: 12px; margin-top: 15px; border-left: 5px solid #ddd; background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .card.danger { border-left-color: var(--d); background: #fef2f2; }
        .card.info { border-left-color: var(--s); background: #eff6ff; }
        .card.steps { border-left-color: #22c55e; background: #f0fdf4; }
        #loading { display: none; text-align: center; padding: 20px; font-weight: bold; color: var(--p); }
        .spinner { width: 30px; height: 30px; border: 4px solid #f3f3f3; border-top: 4px solid var(--p); border-radius: 50%; animation: spin 1s linear infinite; margin: auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="app">
        <h1>🛠️ FixIt AI PRO</h1>
        <button class="btn btn-cam" onclick="document.getElementById('in').click()">📸 PRENDRE UNE PHOTO</button>
        <button class="btn btn-qr" onclick="scanQR()">🔳 SCANNER UN QR CODE</button>
        
        <input type="file" id="in" accept="image/*" capture="environment" hidden onchange="pv(this)">
        <div id="reader"></div>
        <img id="preview">
        
        <textarea id="ctx" placeholder="Ex: Fuite sous le lavabo, marque Grohe..."></textarea>
        
        <button id="go" class="btn btn-run" onclick="run()">LANCER LE DIAGNOSTIC</button>
        
        <div id="loading"><div class="spinner"></div><br>Analyse Multi-Agents...</div>
        <div id="out"></div>
    </div>

    <script>
        let file;
        function pv(i) {
            file = i.files[0];
            const r = new FileReader();
            r.onload = (e) => { 
                const p = document.getElementById('preview');
                p.src = e.target.result; p.style.display = 'block';
                document.getElementById('reader').style.display = 'none';
            };
            r.readAsDataURL(file);
        }

        function scanQR() {
            const r = document.getElementById('reader');
            r.style.display = 'block';
            const scanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
            scanner.render((txt) => {
                document.getElementById('ctx').value += " [QR: " + txt + "]";
                scanner.clear();
                r.style.display = 'none';
            });
        }

        async function run() {
            if(!file) return alert("Photo requise !");
            const out = document.getElementById('out');
            const load = document.getElementById('loading');
            out.innerHTML = ""; load.style.display = "block";

            const fd = new FormData();
            fd.append('image', file);
            fd.append('context', document.getElementById('ctx').value);

            try {
                const res = await fetch('/analyze', { method: 'POST', body: fd });
                out.innerHTML = await res.text();
            } catch (e) {
                out.innerHTML = "<div class='card danger'>Erreur de connexion.</div>";
            } finally {
                load.style.display = "none";
            }
        }
    </script>
</body>
</html>
    """
