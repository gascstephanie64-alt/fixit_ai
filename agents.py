import os
from groq import Groq
from duckduckgo_search import DDGS

# Configuration du Client
def get_groq_client():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise ValueError("La clé GROQ_API_KEY est manquante.")
    return Groq(api_key=key)

# --- AGENT 1 : DIAGNOSTIC & SOLUTION (Vision) ---
def agent_diagnostic(image_b64, context, client):
    """Analyse l'image et détermine le problème et la solution technique."""
    prompt = f"""
    Tu es un Expert Bricolage et Bâtiment (Plomberie, Électricité, Menuiserie).
    Contexte utilisateur : {context}
    
    Analyse cette image et fournis une réponse structurée HTML (sans balises <html> ou <body>, juste le contenu div) :
    1. Identifie le problème précis (ex: siphon percé, charnière arrachée).
    2. Explique la cause probable.
    3. Donne la solution technique 'Do It Yourself' la plus durable.
    
    Format de sortie HTML attendu :
    <div class='card warning'>
        <h3>🔍 Diagnostic</h3>
        <p><strong>Problème :</strong> ...</p>
        <p><strong>Cause :</strong> ...</p>
    </div>
    <div class='card success'>
        <h3>💡 La Solution Technique</h3>
        <p>...</p>
    </div>
    """
    
    completion = client.chat.completions.create(
        model="llama-3.2-11b-vision-preview", # Ou "meta-llama/llama-4-scout-17b-16e-instruct" si disponible
        messages=[{
            "role": "user", 
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        }],
        temperature=0.2
    )
    return completion.choices[0].message.content

# --- AGENT 2 : SÉCURITÉ & OUTILLAGE (Texte) ---
def agent_securite_outils(diagnostic_text, client):
    """Définit les outils et le niveau de risque."""
    prompt = f"""
    Basé sur ce diagnostic : {diagnostic_text}
    
    Agis comme un Chef de Chantier responsable de la sécurité.
    1. Estime la difficulté (1-5) et le danger (Électricité ? Gaz ?).
    2. Liste les outils "Amateur" (débrouille) vs "Pro" (idéal).
    3. Liste les consommables à acheter (joints, vis, colle...).
    
    Format HTML de sortie (divs uniquement) :
    <div class='card danger'>
        <h3>🛡️ Sécurité & Difficulté</h3>
        <p><strong>Niveau :</strong> .../5</p>
        <p><strong>Risques :</strong> ...</p>
        <p><strong>EPI recommandés :</strong> Gants, Lunettes...</p>
    </div>
    <div class='card info'>
        <h3>🛠️ Outillage Nécessaire</h3>
        <ul>
            <li><strong>Indispensable :</strong> ...</li>
            <li><strong>Optionnel (Confort) :</strong> ...</li>
            <li><strong>A acheter (Consommables) :</strong> ...</li>
        </ul>
    </div>
    """
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile", # Modèle texte rapide et intelligent
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content

# --- AGENT 3 : COACH TUTO & SOURCING (Recherche + Tuto) ---
def agent_coach_tuto(diagnostic_text, client):
    """Génère le tuto pas à pas et cherche des liens."""
    
    # Recherche Web via DuckDuckGo (Gratuit & Robuste)
    search_query = f"tuto réparation {diagnostic_text[:50]} achat pièces"
    try:
        results = DDGS().text(search_query, max_results=3)
        links_html = "<ul>"
        for r in results:
            links_html += f"<li><a href='{r['href']}' target='_blank'>🔗 {r['title']}</a></li>"
        links_html += "</ul>"
    except:
        links_html = "<p>Recherche web momentanément indisponible.</p>"

    prompt = f"""
    Tu es un Coach Bricolage pour débutants absolus.
    Basé sur le diagnostic, rédige un tutoriel "Pas à Pas" ultra simple.
    Utilise des termes simples (ex: "Tourne vers la droite" au lieu de "Sens horaire").
    
    Format HTML de sortie :
    <div class='card step-by-step'>
        <h3>📝 Le Tuto Pas à Pas</h3>
        <ol>
            <li><strong>Étape 1 :</strong> ...</li>
            <li><strong>Étape 2 :</strong> ...</li>
            <li><strong>Étape 3 :</strong> ...</li>
            <li><strong>Finitions :</strong> ...</li>
        </ol>
    </div>
    """
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    
    tuto_content = completion.choices[0].message.content
    sourcing_content = f"<div class='card web'><h3>🛒 Où trouver les pièces ?</h3>{links_html}</div>"
    
    return tuto_content + sourcing_content