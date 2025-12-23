import os
import base64
import json
import asyncio
import re
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

# CONFIGURATION EXPERTE
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_TEXT = "llama-3.3-70b-versatile"

# --- MOTEUR DE RECHERCHE STRICT (Sourcing Réel) ---
def search_real_links(keywords_tools: str, problem_context: str):
    """
    Ne génère rien. Cherche de vrais liens existants.
    """
    results = {
        "videos": [],
        "shopping_tools": [],
        "renting": []
    }
    
    with DDGS() as ddgs:
        # 1. Tutos Vidéos (Youtube uniquement)
        query_vid = f"site:youtube.com tutoriel réparation {problem_context}"
        try:
            vids = list(ddgs.text(query_vid, max_results=3))
            results["videos"] = [{"title": v['title'], "link": v['href']} for v in vids]
        except: pass

        # 2. Achat Outils & Pièces (Commerces FR)
        # On nettoie les mots clés pour la recherche
        clean_tools = keywords_tools.replace(" et ", " ").replace(",", " ")
        query_shop = f"achat en ligne {clean_tools} site:leroymerlin.fr OR site:manomano.fr OR site:castorama.fr"
        try:
            shops = list(ddgs.text(query_shop, max_results=3))
            results["shopping_tools"] = [{"title": s['title'], "link": s['href'], "source": "Achat"} for s in shops]
        except: pass

        # 3. Location (Si outillage lourd détecté)
        if any(x in clean_tools.lower() for x in ['perforateur', 'scie', 'ponceuse', 'déboucheur', 'caméra']):
            query_rent = f"location {clean_tools} kiloutou loxam"
            try:
                rents = list(ddgs.text(query_rent, max_results=2))
                results["renting"] = [{"title": r['title'], "link": r['href'], "source": "Location"} for r in rents]
            except: pass

    return results

# --- FONCTION DE FORMATAGE HTML (Template Fiche Technique) ---
def format_final_report(diagnosis_text, procedure_text, links_data):
    
    # Construction HTML des liens
    video_html = ""
    if links_data["videos"]:
        video_html = "<div class='section'><h4>📺 VIDEOS DE RÉFÉRENCE (Preuves)</h4><ul class='video-list'>"
        for v in links_data["videos"]:
            video_html += f"<li><a href='{v['link']}' target='_blank'>▶️ {v['title'].replace('...','')}</a></li>"
        video_html += "</ul></div>"
    else:
        video_html = "<div class='alert'>Aucune vidéo certifiée trouvée pour ce problème spécifique.</div>"

    tools_html = ""
    all_tools = links_data["shopping_tools"] + links_data["renting"]
    if all_tools:
        tools_html = "<div class='section'><h4>🛒 SOURCING OUTILS & PIÈCES (Disponibilité)</h4><table class='tool-table'>"
        for t in all_tools:
            icon = "🔑" if t['source'] == "Location" else "🛒"
            tools_html += f"<tr><td>{icon}</td><td><a href='{t['link']}' target='_blank'>{t['title'][:40]}...</a></td></tr>"
        tools_html += "</table></div>"

    return f"""
    <div class='technical-sheet'>
        <div class='header-diag'>
            <h3>📋 FICHE D'INTERVENTION</h3>
        </div>
        
        {diagnosis_text} {tools_html}
        
        {procedure_text} {video_html}
    </div>
    """

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(images: List[UploadFile] = File(...), context: str = Form("")):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    try:
        # 1. PRÉPARATION IMAGES
        images_b64 = []
        for img in images:
            content = await img.read()
            images_b64.append(base64.b64encode(content).decode('utf-8'))

        # 2. PHASE 1 : DIAGNOSTIC TECHNIQUE & EXTRACTION KEYWORDS (Llama 4 Vision)
        # On demande du JSON ou un format très strict pour extraire les outils
        prompt_vision = f"""
        CONTEXTE: {context}
        MISSION: Tu es un Expert Technique Bâtiment. Analyse l'image.
        
        FORMAT DE REPONSE ATTENDU (Strictement HTML) :
        <div class='diag-section'>
            <p><strong>Panne / Défaut :</strong> [Nom technique précis]</p>
            <p><strong>Cause Racine :</strong> [Origine physique]</p>
            <p style="display:none" id="raw_tools">[Liste simple des outils et pièces spécifiques nécessaires séparés par des virgules pour le moteur de recherche]</p>
        </div>
        """
        
        vision_content = [{"type": "text", "text": prompt_vision}]
        for img in images_b64:
            vision_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
        
        diag_response = client.chat.completions.create(
            model=MODEL_VISION, messages=[{"role": "user", "content": vision_content}], temperature=0.0
        ).choices[0].message.content

        # Extraction "Sale" mais efficace des mots clés outils depuis la réponse cachée
        try:
            raw_tools = diag_response.split('id="raw_tools">')[1].split('</p>')[0]
        except:
            raw_tools = "outillage plomberie bricolage standard"

        # Extraction du nom du problème pour la recherche vidéo
        try:
            problem_name = diag_response.split('<strong>Panne / Défaut :</strong>')[1].split('</p>')[0]
        except:
            problem_name = context

        # 3. PHASE 2 : SOURCING WEB RÉEL (Python + DDG)
        real_links = search_real_links(raw_tools, problem_name)

        # 4. PHASE 3 : RÉDACTION PROCÉDURE STANDARDISÉE (Llama 3 Texte)
        prompt_proc = f"""
        Agis comme une Manuel de Réparation Technique. Pas de politesse. Pas de créativité.
        Diagnostic : {diag_response}
        Outils disponibles identifiés : {raw_tools}
        
        Rédige la PROCÉDURE DE RÉPARATION NORMALISÉE (SOP) en HTML :
        - Liste à puces concise.
        - Verbes à l'impératif (Dévisser, Remplacer, Tester).
        - Précisions techniques (Diamètres, Sens de rotation).
        - Avertissements de sécurité en ROUGE et GRAS si nécessaire.
        
        Structure HTML attendue :
        <div class='proc-section'>
            <h4>⚙️ PROTOCOLE DE RÉPARATION</h4>
            <ol>
                <li>...</li>
            </ol>
        </div>
        """
        
        proc_response = client.chat.completions.create(
            model=MODEL_TEXT, messages=[{"role": "user", "content": prompt_proc}], temperature=0.1
        ).choices[0].message.content

        # 5. ASSEMBLAGE
        final_html = format_final_report(diag_response, proc_response, real_links)
        return final_html

    except Exception as e:
        return f"<div class='alert'>ERREUR SYSTÈME : {str(e)}</div>"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>FixIt AI - EXPERT MODE</title>
    <style>
        :root { --dark: #1e293b; --blue: #2563eb; --alert: #dc2626; --bg: #f8fafc; }
        body { font-family: 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--dark); margin: 0; padding: 10px; }
        
        .app-container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }
        
        /* HEADER PRO */
        header { background: var(--dark); color: white; padding: 15px; text-align: center; }
        header h1 { margin: 0; font-size: 1.2rem; text-transform: uppercase; letter-spacing: 1px; }
        header span { font-size: 0.7rem; color: #94a3b8; }

        /* CONTROLS */
        .controls { padding: 15px; background: #f1f5f9; border-bottom: 1px solid #e2e8f0; }
        .btn-row { display: flex; gap: 10px; margin-bottom: 10px; }
        .btn { flex: 1; border: none; padding: 12px; border-radius: 6px; font-weight: 600; cursor: pointer; color: white; font-size: 0.9rem; display: flex; align-items: center; justify-content: center; gap: 5px; }
        .btn-photo { background: #334155; }
        .btn-mic { background: #475569; }
        .btn-run { background: var(--blue); width: 100%; margin-top: 10px; font-size: 1rem; text-transform: uppercase; }
        .btn-reset { background: #cbd5e1; color: #333; width: auto; flex: 0.3; }

        /* INPUTS */
        #img-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin-top: 10px; }
        .thumb { width: 100%; height: 60px; object-fit: cover; border: 1px solid #cbd5e1; border-radius: 4px; }
        textarea { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box; margin-top: 10px; font-family: monospace; font-size: 0.9rem; }

        /* FICHE TECHNIQUE RESULTAT */
        .technical-sheet { padding: 0; }
        .header-diag { background: #e2e8f0; padding: 10px 20px; border-bottom: 2px solid var(--blue); }
        .header-diag h3 { margin: 0; font-size: 1rem; color: var(--dark); }

        .diag-section, .proc-section, .section { padding: 15px 20px; border-bottom: 1px solid #f1f5f9; }
        
        h4 { margin: 0 0 10px 0; font-size: 0.85rem; text-transform: uppercase; color: #64748b; font-weight: 700; }
        
        /* TABLES ET LISTES */
        .tool-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        .tool-table td { padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
        .tool-table a { color: var(--blue); text-decoration: none; font-weight: 600; }
        
        .video-list { list-style: none; padding: 0; margin: 0; }
        .video-list li { margin-bottom: 8px; }
        .video-list a { display: block; padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; color: #0f172a; text-decoration: none; font-weight: 500; }
        .video-list a:hover { background: #eff6ff; border-color: var(--blue); }

        ol { padding-left: 20px; margin: 0; }
        li { margin-bottom: 5px; line-height: 1.5; font-size: 0.95rem; }

        #loading { padding: 30px; text-align: center; display: none; color: #64748b; font-weight: 600; }
    </style>
</head>
<body>
    <div class="app-container">
        <header>
            <h1>FixIt Pro • Expert System</h1>
            <span>VERSION PRODUCTION 2.4.0</span>
        </header>

        <div class="controls">
            <div class="btn-row">
                <button class="btn btn-photo" onclick="document.getElementById('fin').click()">📷 PHOTOS</button>
                <button class="btn btn-mic" id="mBtn" onclick="tMic()">🎤 DICTER</button>
                <button class="btn btn-reset" onclick="resetApp()">🗑️</button>
            </div>
            
            <input type="file" id="fin" accept="image/*" multiple hidden onchange="hFiles(this)">
            <div id="img-grid"></div>
            
            <textarea id="ctx" placeholder="CONTEXTE TECHNIQUE (Facultatif)..."></textarea>
            
            <button class="btn btn-run" onclick="run()">GÉNÉRER PROTOCOLE RÉPARATION</button>
        </div>

        <div id="loading">📥 CONSULTATION DES BASES DE DONNÉES...</div>
        <div id="out"></div>
    </div>

    <script>
        let files = [];
        
        // --- LOGIQUE CLIENT ---
        function hFiles(i) {
            const g = document.getElementById('img-grid');
            for(let f of i.files) {
                files.push(f);
                const r = new FileReader();
                r.onload = (e) => {
                    const img = document.createElement('img');
                    img.src = e.target.result; img.className = 'thumb';
                    g.appendChild(img);
                };
                r.readAsDataURL(f);
            }
        }

        async function compress(file) {
            return new Promise(res => {
                const r = new FileReader(); r.readAsDataURL(file);
                r.onload = ev => {
                    const i = new Image(); i.src = ev.target.result;
                    i.onload = () => {
                        const c = document.createElement('canvas');
                        const m = 1000; let w = i.width, h = i.height;
                        if(w > h && w > m) { h *= m/w; w = m; }
                        else if(h > m) { w *= m/h; h = m; }
                        c.width = w; c.height = h;
                        c.getContext('2d').drawImage(i, 0, 0, w, h);
                        c.toBlob(b => res(b), 'image/jpeg', 0.8);
                    }
                }
            });
        }

        const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
        let rec = Rec ? new Rec() : null;
        if(rec) { rec.lang = 'fr-FR'; rec.onresult = e => { document.getElementById('ctx').value += " " + e.results[0][0].transcript; tMic(); }; }
        function tMic() { 
            const b = document.getElementById('mBtn');
            if(b.style.background.includes('220')) { rec.stop(); b.style.background = '#475569'; }
            else { rec.start(); b.style.background = 'rgb(220, 38, 38)'; }
        }

        function resetApp() {
            files = []; document.getElementById('img-grid').innerHTML = ""; document.getElementById('out').innerHTML = "";
            document.getElementById('ctx').value = "";
        }

        async function run() {
            if(!files.length) return alert("ERREUR: Preuve visuelle requise.");
            const out = document.getElementById('out');
            const load = document.getElementById('loading');
            out.innerHTML = ""; load.style.display = "block";

            const fd = new FormData();
            for(let f of files) fd.append('images', await compress(f));
            fd.append('context', document.getElementById('ctx').value);

            try {
                const r = await fetch('/analyze', { method: 'POST', body: fd });
                out.innerHTML = await r.text();
            } catch(e) {
                out.innerHTML = "<div style='padding:20px;color:red'>ERREUR RÉSEAU</div>";
            } finally {
                load.style.display = "none";
            }
        }
    </script>
</body>
</html>
    """
