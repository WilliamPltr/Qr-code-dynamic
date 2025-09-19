# qr-minimal-white

Génère un QR code design, épuré : modules arrondis blancs sur fond transparent, logo PNG centré, faible densité, correction d’erreur H. Un mini-serveur Flask fournit une URL courte (ex: `/x`) redirigeant vers une cible contrôlée par `redirect.json`, pour pouvoir changer la destination sans régénérer le QR.

## Objectif
- PNG: modules arrondis, avant-plan blanc (`#FFFFFF`), fond transparent (RGBA), logo centré avec plaque blanche arrondie semi-transparente.
- SVG: avant-plan blanc, fond transparent (modules carrés côté SVG).
- Densité limitée (recommandé: URLs courtes, version ≤ 5 si possible), correction d’erreur **H**.

## Installation
- Prérequis: Python 3.10+
- Créer un environnement virtuel et installer:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Lancer la redirection
- Démarrer le serveur:
```bash
python redirect_server.py
```
- Le serveur répond `OK` sur `/` et redirige `/x` vers l’URL dans `redirect.json`.
- Modifier `redirect.json` pour changer la destination, sans régénérer le QR.

## Générer le QR
- Commande typique:
```bash
python make_qr.py --data http://localhost:8000/x --logo assets/logo.png
```
- Sorties dans `out/`:
  - `out/qr_white.png` (RGBA, transparent, modules arrondis)
  - `out/qr_white.svg` (transparent, modules carrés)

## Conseils design
- Avant-plan blanc ⇒ prévoir un **fond sombre** à l’usage, ou activer `--card` pour poser une carte arrondie blanche semi-transparente sous le QR.
- Ne pas masquer les 3 motifs de repérage (finder patterns) aux coins.
- Logo ≤ 22% de la largeur. Correction d’erreur **H** recommandée avec logo.
- Impression: utiliser **SVG** (net) ou PNG ≥ 2048 px.

## FAQ
- Pourquoi mon QR blanc ne scanne pas ?
  - Probable manque de contraste. Posez le QR sur un fond sombre ou activez `--card`.
- Comment réduire la densité ?
  - Utilisez un lien plus court / domaine court et gardez `--max-version` bas.

## Licence
MIT

## Publication sur GitHub (push du projet)

### Pré-requis
- Avoir un compte GitHub et `git` installé
- Optionnel: l’outil `gh` (GitHub CLI) simplifie la création du dépôt

### Étapes (au choix)
1) Création manuelle du dépôt sur GitHub (web), puis push:
```bash
cd qr-minimal-white
git init
git add .
git commit -m "Initial commit: qr-minimal-white"
git branch -M main
git remote add origin https://github.com/<votre_compte>/<votre_repo>.git
git push -u origin main
```

2) Via GitHub CLI (`gh`):
```bash
cd qr-minimal-white
git init && git add . && git commit -m "Initial commit"
gh repo create <votre_repo> --public --source=. --remote=origin --push
```

Après le push, votre code est accessible sur `https://github.com/<votre_compte>/<votre_repo>`.

## Déploiement sur un serveur Oracle Cloud (OCI)

Objectif: exposer une URL courte et stable (ex: `https://r.votre-domaine.tld/x`) qui redirige vers la cible courante définie dans `redirect.json`. Le QR code n’a pas besoin d’être régénéré quand la cible change.

### Option A — Docker (recommandé, simple et reproductible)
1) Connectez-vous à votre VM OCI et installez Docker
2) Clonez votre dépôt et construisez l’image:
```bash
git clone https://github.com/<votre_compte>/<votre_repo>.git
cd <votre_repo>
docker build -t qr-minimal-white .
```
3) Démarrez le conteneur (expose le service Flask interne 8000 vers le port 80 public):
```bash
sudo docker run -d --name qr-redirect -p 80:8000 qr-minimal-white
```
4) Test local (depuis votre machine):
```bash
curl -I http://<IP_PUBLIQUE_VM>/x
```
5) Nom de domaine + HTTPS (facultatif mais conseillé): placez un reverse-proxy (Caddy/Nginx) devant le conteneur pour TLS.

### Option B — Sans Docker (Python + systemd)
1) Installer Python 3.10+ et dépendances:
```bash
sudo apt update -y && sudo apt install -y python3-venv git
git clone https://github.com/<votre_compte>/<votre_repo>.git
cd <votre_repo>
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
2) Lancer en service (port 8000) puis mettre derrière un reverse-proxy:
```bash
PORT=8000 python redirect_server.py
```
3) Reverse-proxy HTTPS rapide avec Caddy (exemple):
Créez un fichier `Caddyfile` minimal:
```
r.votre-domaine.tld {
  reverse_proxy 127.0.0.1:8000
}
```
Puis:
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo tee /etc/apt/trusted.gpg.d/caddy-stable.asc
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
sudo mv Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
```
Let’s Encrypt est géré automatiquement par Caddy.

### Changer la destination sans régénérer le QR
- Éditez `redirect.json` sur le serveur et redémarrez le service si nécessaire (ou mettez un rechargement automatique si vous le souhaitez):
```json
{ "current_target": "https://colis.opack.fr/" }
```
Votre QR encodant `https://r.votre-domaine.tld/x` continuera de fonctionner et pointera vers la nouvelle destination.

### Générer un QR pointant vers l’URL courte publique
Une fois votre domaine configuré, générez votre QR une bonne fois:
```bash
python make_qr.py --data https://r.votre-domaine.tld/x
```
Ou mettez la valeur par défaut dans `DEFAULTS["data"]` en haut de `make_qr.py`.

### Dépannage
- Le QR ne scanne pas: manque de contraste (prévoir fond sombre ou `--card`) ou cible injoignable depuis le téléphone (vérifiez `curl -I https://r.votre-domaine.tld/x` sur réseau mobile).
- QR trop dense: utilisez une URL plus courte pour `--data` (sous-domaine court), gardez une version basse et un `error_level` plus bas si acceptable.
