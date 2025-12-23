# 🛠️ FixIt AI - Assistant de Réparation Intelligent (DIY)

**FixIt AI** est une application web progressive (PWA) conçue pour aider les particuliers à diagnostiquer, sécuriser et réparer les pannes domestiques (plomberie, électricité, menuiserie) à partir d'une simple photo.

L'application utilise une chaîne d'agents IA autonomes pour transformer une image en un tutoriel de réparation pas-à-pas sécurisé.



## 🚀 Fonctionnalités

* **📸 Diagnostic Visuel Instantané** : Analyse technique de la panne via le modèle **Llama 4 Scout** (Vision).
* **🛡️ Garde-Fou Sécurité** : Évaluation automatique des risques (gaz, haute tension) et recommandation des EPI (Équipements de Protection Individuelle).
* **📝 Coach Pas-à-Pas** : Génération de tutoriels simplifiés pour débutants complets.
* **🛒 Sourcing Automatique** : Recherche des pièces détachées et outils nécessaires via **DuckDuckGo** (sans API payante).
* **🔳 Scanner QR Code** : Intégration d'un lecteur QR pour récupérer des contextes de maintenance spécifiques.
* **📱 Interface Mobile First** : Design adapté aux smartphones pour une utilisation "sur le chantier".

## 🧠 Architecture des Agents

Le système repose sur un pipeline de 3 agents spécialisés :

1.  **Agent Diagnostiqueur (Vision)** : Identifie le problème matériel et la cause racine.
2.  **Agent Chef de Chantier (Logique)** : Valide la faisabilité DIY, liste les outils (Pro vs Amateur) et les consignes de sécurité.
3.  **Agent Coach (Rédaction & Web)** : Rédige le guide et trouve les liens d'achat/location.

## 🛠️ Stack Technique

* **Backend** : Python, FastAPI
* **IA Vision & LLM** : Groq API (Llama 3.2 Vision / Llama 4 Scout)
* **Recherche Web** : `duckduckgo-search` (Gratuit, respectueux de la vie privée)
* **Frontend** : HTML5, CSS3, Vanilla JS (Aucun framework lourd requis)
* **Hébergement** : Compatible Railway, Render, Docker.

## ⚙️ Installation en Local

### Prérequis
* Python 3.9 ou supérieur
* Une clé API Groq (gratuite ou payante)

### 1. Cloner le projet
```bash
git clone [https://github.com/votre-pseudo/fixit-ai.git](https://github.com/votre-pseudo/fixit-ai.git)
cd fixit-ai