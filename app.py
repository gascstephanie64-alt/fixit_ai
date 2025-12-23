import os
import base64
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Import de nos agents
from agents import get_groq_client, agent_diagnostic, agent_securite_outils, agent_coach_tuto

load_dotenv()
app = FastAPI()

# --- CSS & JS INTÉGRÉS POUR UNE PWA RAPIDE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>FixIt AI - Assistant Bricolage</title>
    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root { --primary: #f97316; --secondary: #3b82f6; --danger: #ef4444; --success: #22c55e; --bg: #f3f4f6; }
        body { font-family: 'Roboto', sans-serif; background: var(--bg); margin: 0; padding: 0; color: #1f2937; }
        
        .header { background: var(--primary); color: white; padding: 20px; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .header h1 { margin: 0; font-size: 1.5rem; }
        .header p { margin: 5px 0 0 0; opacity: 0.9; font-size: 0.9rem; }

        .container { max-width: 600px; margin: auto; padding: 15px; }
        
        /* Boutons Actions */
        .action-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .btn { border: none; padding: 15px; border-radius: 12px; font-weight: bold; cursor: pointer; font-size: 1rem; transition: transform 0.1s; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .btn:active { transform: scale(0.98); }
        .btn-camera { background: #4b5563; grid-column: span 2; }
        .btn-qr { background: var(--secondary); }
        .btn-gallery { background: #6b7280; }
        .btn-go { background: var(--primary); width: 100%; margin-top: 15px; font-size: 1.2rem; }

        /* Zones d'affichage */
        #preview-zone { margin-top: 15px; display: none; border-radius: 12px; overflow: hidden; border: 3px solid var(--primary); }
        #preview-zone img { width: 100%; display: block; }
        
        #reader { width: 100%; display: none; margin-top: 15px; border-radius: 12px; overflow: hidden; }

        textarea { width: 100%; padding: 15px; border-radius: 12px; border: 1px solid #d1d5db; margin-top: 15px; font-family: inherit; box-sizing: border-box; resize: vertical; min-height: 80px; }

        /* Cartes de Résultat */
        .card { background: white; padding: 20px; border-radius: 12px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 5px solid #ccc; }
        .card h3 { margin-top: 0; display: flex; align-items: center; gap: 8px; font-size: 1.1rem; }
        .card.warning { border-left-color: var(--primary); }
        .card.success { border-left-color: var(--success); }
        .card.danger { border-left-color: var(--danger); background: #fef2f2; }
        .card.info { border-left-color: var(--secondary); }
        .card.web { border-left-color: #8b5cf6; background: #f5f3ff; }
        .card ul, .card ol { padding-left: 20px; }
        .card li { margin-bottom: 8px; }
        .card a { color: var(--secondary); text-decoration: none; font-weight: bold; }

        /* Loader */
        #loading { display: none; text-align: center; padding: 40px; }
        .spinner { width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite; margin: auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛠️ FixIt AI</h1>
        <p>Expert Réparation & DIY</p>
    </div>

    <div class="container">
        
        <div class="action-grid">
            <button class="btn btn-camera" onclick="document.getElementById('fileInput').click()">
                <span>📸</span> Prendre une Photo
            </button>
            <button class="btn btn-qr" onclick="startQR()">
                <span>🔳</span> Scan QR
            </button>
            <button class="btn btn-gallery" onclick="document.getElementById('fileInput').click()">
                <span>🖼️</span> Galerie
            </button>
        </div>

        <input type="file" id="fileInput" accept="image/*" capture="environment" hidden onchange="handleFile(this)">
        
        <div id="reader"></div>

        <div id="preview-zone">
            <img id="preview-img">
        </div>

        <textarea id="context" placeholder="Décrivez le problème (ex: L'eau coule sous l'évier quand j'ouvre le robinet...)"></textarea>

        <button id="submitBtn" class="btn btn-go" onclick="analyze()">LANCER LE DIAGNOSTIC</button>

        <div id="loading">
            <div class="spinner"></div>
            <p>Analyse des Agents en cours...</p>
            <p style="font-size:0.8em; color:#666;">Diagnostic • Sécurité • Recherche Tutos</p>
        </div>

        <div id="results"></div>

    </div>

    <script>
        let selectedFile = null;
        let html5QrcodeScanner = null;

        // Gestion Fichier/Photo
        function handleFile(input) {
            if (input.files && input.files[0]) {
                selectedFile = input.files[0];
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('preview-img').src = e.target.result;
                    document.getElementById('preview-zone').style.display = 'block';
                    document.getElementById('reader').style.display = 'none'; // Cacher QR si ouvert
                    if(html5QrcodeScanner) html5QrcodeScanner.clear();
                }
                reader.readAsDataURL(selectedFile);
            }
        }

        // Gestion QR Code
        function startQR() {
            const readerDiv = document.getElementById('reader');
            readerDiv.style.display = 'block';
            document.getElementById('preview-zone').style.display = 'none';
            
            html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
            html5QrcodeScanner.render((decodedText, decodedResult) => {
                // Succès du scan
                document.getElementById('context').value += " [Info QR: " + decodedText + "]";
                alert("QR Code détecté ! Info ajoutée au contexte.");
                html5QrcodeScanner.clear();
                readerDiv.style.display = 'none';
            }, (errorMessage) => {
                // Erreur de scan (ignorer ou logger)
            });
        }

        // Envoi Analyse
        async function analyze() {
            if (!selectedFile) {
                alert("Merci de prendre une photo d'abord !");
                return;
            }

            const resDiv = document.getElementById('results');
            const loadDiv = document.getElementById('loading');
            const btn = document.getElementById('submitBtn');

            resDiv.innerHTML = "";
            loadDiv.style.display = "block";
            btn.disabled = true;
            btn.style.opacity = "0.7";

            const formData = new FormData();
            formData.append('image', selectedFile);
            formData.append('context', document.getElementById('context').value);

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const html = await response.text();
                    resDiv.innerHTML = html;
                } else {
                    resDiv.innerHTML = "<div class='card danger'><h3>Erreur</h3><p>Le serveur n'a pas pu traiter la demande.</p></div>";
                }
            } catch (error) {
                resDiv.innerHTML = "<div class='card danger'><h3>Erreur Réseau</h3><p>Vérifiez votre connexion internet.</p></div>";
            } finally {
                loadDiv.style.display = "none";
                btn.disabled = false;
                btn.style.opacity = "1";
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_TEMPLATE

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_endpoint(image: UploadFile = File(...), context: str = Form("")):
    try:
        # 1. Préparation
        client = get_groq_client()
        img_bytes = await image.read()
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # 2. Exécution des Agents en cascade
        # Agent 1 : Vision & Diagnostic
        diagnostic_html = agent_diagnostic(img_b64, context, client)
        
        # Agent 2 : Sécurité & Outils (basé sur la sortie de l'Agent 1)
        securite_html = agent_securite_outils(diagnostic_html, client)
        
        # Agent 3 : Tutos & Web (basé sur la sortie de l'Agent 1)
        coach_html = agent_coach_tuto(diagnostic_html, client)
        
        # 3. Assemblage du rapport final
        final_report = f"""
        <div class="report-container">
            {diagnostic_html}
            {securite_html}
            {coach_html}
        </div>
        """
        return final_report

    except Exception as e:
        return f"<div class='card danger'><h3>Erreur Système</h3><p>{str(e)}</p></div>"