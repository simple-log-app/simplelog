# SimpleLog — Guide de test des providers

Ce guide explique comment créer un compte (gratuit ou trial), obtenir les credentials, générer des logs, et configurer SimpleLog pour chaque provider.

---

## ✅ Providers déjà validés

- **Vercel** — fonctionne
- **AWS CloudWatch** — fonctionne
- **Cloudflare Workers** — fonctionne

---

## 🧪 Providers à tester

---

## 1. Docker (local)

**Pas de compte nécessaire.** Docker tourne en local.

### Installation
```bash
# Ubuntu/Debian
sudo apt install docker.io
sudo usermod -aG docker $USER   # puis se reconnecter

# Vérifier
docker --version
```

### Générer des logs
```bash
# Lancer un container qui génère des logs en continu
docker run -d --name simplelog-test nginx

# Ou un container avec logs verbeux
docker run -d --name log-generator alpine \
  sh -c 'while true; do echo "[$(date)] request received from 1.2.3.4"; sleep 2; done'
```

### Configurer SimpleLog
- **Source** : Docker
- **Host** : laisser vide (Docker local)
- Sélectionner le container `simplelog-test` ou `log-generator`

---

## 2. SSH (fichier distant)

**Pas de compte nécessaire.** Utilise n'importe quel serveur SSH (VPS, VM, même `localhost`).

### Test avec localhost (le plus simple)
```bash
# Générer un fichier de logs en continu sur votre machine
while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO user=test action=login ip=192.168.1.$(shuf -i1-254 -n1)"
  sleep 1
done >> /tmp/simplelog-test.log &

echo "Log generator PID: $!"
```

### Clé SSH pour localhost
```bash
# Si vous n'avez pas de clé SSH
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Autoriser la clé sur localhost
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Tester
ssh -i ~/.ssh/id_ed25519 $(whoami)@localhost echo "OK"
```

### Configurer SimpleLog
- **Host** : `localhost`
- **Port** : `22`
- **User** : votre username (`whoami`)
- **SSH Key** : `~/.ssh/id_ed25519`
- **Remote path** : `/tmp/simplelog-test.log`

---

## 3. Grafana Loki (local via Docker)

**Pas de compte nécessaire.** Loki tourne entièrement en local.

### Lancer Loki + Grafana
```bash
# Loki
docker run -d --name loki -p 3100:3100 grafana/loki:latest

# Vérifier que Loki répond
curl http://localhost:3100/ready
# → "ready"
```

### Générer des logs
```bash
# Envoyer des logs à Loki via l'API push
NOW=$(date +%s)000000000

curl -X POST http://localhost:3100/loki/api/v1/push \
  -H "Content-Type: application/json" \
  -d "{
    \"streams\": [{
      \"stream\": {\"app\": \"simplelog-test\", \"env\": \"dev\"},
      \"values\": [
        [\"${NOW}\", \"INFO server started on port 8080\"],
        [\"${NOW}\", \"INFO GET /api/health 200 12ms\"],
        [\"${NOW}\", \"WARN slow query detected: 450ms\"],
        [\"${NOW}\", \"ERROR failed to connect to database\"]
      ]
    }]
  }"
```

### Configurer SimpleLog
- **URL** : `http://localhost:3100`
- **Username** : laisser vide
- **Password** : laisser vide
- **Query (LogQL)** : `{app="simplelog-test"}`

---

## 4. Elasticsearch (local via Docker)

**Pas de compte nécessaire.** Elasticsearch tourne en local.

### Lancer Elasticsearch
```bash
docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  elasticsearch:8.13.0

# Attendre ~30s puis vérifier
curl http://localhost:9200
# → {"name":"...","cluster_name":"docker-cluster",...}
```

### Générer des logs
```bash
# Créer un index et insérer des logs
for i in $(seq 1 10); do
  curl -s -X POST "http://localhost:9200/app-logs/_doc" \
    -H "Content-Type: application/json" \
    -d "{
      \"@timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",
      \"level\": \"INFO\",
      \"message\": \"Request #$i processed successfully\",
      \"service\": \"api\",
      \"duration_ms\": $((RANDOM % 500))
    }" > /dev/null
  sleep 0.5
done
echo "10 logs insérés dans l'index app-logs"
```

### Configurer SimpleLog
- **URL** : `http://localhost:9200`
- **Index** : `app-logs`
- **API Key** : laisser vide
- **Username / Password** : laisser vide

---

## 5. Railway

### Créer un compte
1. Aller sur **railway.app**
2. **Sign up** → GitHub ou email
3. Tu reçois **$5 de crédit gratuit** (suffisant pour tester)

### Déployer un service qui génère des logs
1. Dashboard Railway → **New Project**
2. **Deploy from GitHub repo** ou **Template**
3. Cherche le template **"Node.js"** ou **"Hello World"**
4. Clique **Deploy** — Railway génère automatiquement des logs de build et runtime

### Obtenir le token API
1. Railway Dashboard → **Account Settings** (icône en haut à droite)
2. **Tokens** → **Create Token**
3. Copie le token

### Configurer SimpleLog
- **Token** : le token copié ci-dessus
- Sélectionner le projet et le service dans la liste

---

## 6. Fly.io

### Créer un compte
1. Aller sur **fly.io**
2. **Sign up** → email + carte bancaire (pas de débit sur le plan gratuit)
3. Plan gratuit : 3 VMs partagées, 160 GB bande passante

### Installer la CLI et se connecter
```bash
# Installation
curl -L https://fly.io/install.sh | sh

# Connexion
fly auth login
# → ouvre le navigateur pour s'authentifier
```

### Déployer une app qui génère des logs
```bash
mkdir fly-test && cd fly-test

# Créer un serveur minimal
cat > server.js << 'EOF'
const http = require('http');
const server = http.createServer((req, res) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url} from ${req.socket.remoteAddress}`);
  res.end('OK\n');
});
server.listen(8080, () => console.log('Server running on 8080'));
EOF

cat > package.json << 'EOF'
{"name":"fly-test","version":"1.0.0","main":"server.js"}
EOF

# Initialiser et déployer
fly launch --name simplelog-test-$(date +%s) --region cdg --now
```

### Obtenir le token
```bash
fly auth token
# → imprime le token
```

### Configurer SimpleLog
- **Token** : la sortie de `fly auth token`
- Sélectionner l'app dans la liste

---

## 7. GCP Cloud Logging

### Créer un compte
1. Aller sur **console.cloud.google.com**
2. **Get started for free** → compte Google requis
3. Tu reçois **$300 de crédit gratuit** valable 90 jours
4. Carte bancaire requise (pas de débit pendant le trial)

### Créer un projet et activer Cloud Logging
1. Console GCP → **New Project** → nom : `simplelog-test`
2. Menu → **APIs & Services** → **Enable APIs**
3. Cherche "Cloud Logging API" → **Enable**

### Créer un Service Account
1. Menu → **IAM & Admin** → **Service Accounts**
2. **Create Service Account**
   - Name : `simplelog-reader`
   - Role : `Logging > Logs Viewer`
3. Clique sur le compte créé → **Keys** → **Add Key** → **JSON**
4. Télécharge le fichier JSON → sauvegarde-le ex: `~/gcp-simplelog-key.json`

### Générer des logs
```bash
# Installer la CLI Google Cloud
curl https://sdk.cloud.google.com | bash
gcloud auth activate-service-account --key-file=~/gcp-simplelog-key.json
gcloud config set project simplelog-test  # ton project ID

# Écrire des logs
gcloud logging write simplelog-test-log "INFO: server started" --severity=INFO
gcloud logging write simplelog-test-log "WARN: high memory usage 85%" --severity=WARNING
gcloud logging write simplelog-test-log "ERROR: database connection failed" --severity=ERROR
```

### Configurer SimpleLog
- **Project ID** : ex `simplelog-test` (visible dans la console GCP)
- **Credentials file** : chemin vers `~/gcp-simplelog-key.json`
- **Resource type** : `global`
- **Severity** : `DEBUG` (pour tout voir)

---

## 8. Azure Monitor

### Créer un compte
1. Aller sur **portal.azure.com**
2. **Start free** → compte Microsoft requis
3. Tu reçois **$200 de crédit gratuit** + services gratuits 12 mois
4. Carte bancaire requise (pas de débit pendant le trial)

### Créer un Log Analytics Workspace
1. Portal Azure → **Create a resource** → "Log Analytics Workspace"
2. **Resource Group** : créer `simplelog-rg`
3. **Name** : `simplelog-workspace`
4. **Region** : West Europe
5. **Review + Create**

### Obtenir le Workspace ID
Menu du workspace → **Settings** → **Agents** → copie le **Workspace ID**

### Créer une App Registration (pour l'auth)
1. **Azure Active Directory** → **App registrations** → **New registration**
2. Name : `simplelog-app` → **Register**
3. Copie le **Application (client) ID** et le **Directory (tenant) ID**
4. **Certificates & secrets** → **New client secret** → copie la **Value** (visible une seule fois)

### Donner accès au workspace
1. Log Analytics Workspace → **Access control (IAM)**
2. **Add role assignment**
3. Role : **Log Analytics Reader**
4. Members : sélectionne `simplelog-app`

### Générer des logs
```bash
# Envoyer des logs via l'API HTTP Data Collector (ancienne méthode, compatible)
WORKSPACE_ID="ton-workspace-id"
PRIMARY_KEY="ta-primary-key"  # Settings > Agents > Primary key

DATE=$(date -u "+%a, %d %b %Y %H:%M:%S GMT")
BODY='[{"TimeGenerated":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","Message":"Test log from SimpleLog","Level":"Info","Source":"simplelog-test"}]'
CONTENT_LENGTH=${#BODY}

SIGNATURE=$(echo -n "POST\n${CONTENT_LENGTH}\napplication/json\nx-ms-date:${DATE}\n/api/logs" | \
  openssl dgst -sha256 -hmac "$(echo $PRIMARY_KEY | base64 -d)" -binary | base64)

curl -X POST "https://${WORKSPACE_ID}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01" \
  -H "Content-Type: application/json" \
  -H "Log-Type: SimpleLogTest" \
  -H "x-ms-date: ${DATE}" \
  -H "Authorization: SharedKey ${WORKSPACE_ID}:${SIGNATURE}" \
  -d "$BODY"
```

> Attendre ~5 minutes pour que les logs apparaissent dans Log Analytics.

### Configurer SimpleLog
- **Workspace ID** : copié depuis le workspace
- **Tenant ID** : depuis App Registration
- **Client ID** : depuis App Registration
- **Client Secret** : la Value copiée
- **Query (KQL)** : `SimpleLogTest_CL | take 50`

---

## 9. Datadog

### Créer un compte
1. Aller sur **app.datadoghq.com**
2. **Get Started Free** → email + mot de passe
3. Trial gratuit **14 jours** (carte non requise)
4. Sélectionner **US1** comme site pendant l'inscription

### Obtenir les clés API
1. Menu gauche → **Organization Settings** → **API Keys**
2. **New Key** → nom : `simplelog-test` → copie la clé
3. Menu → **Organization Settings** → **Application Keys**
4. **New Key** → nom : `simplelog-test` → copie la clé

### Générer des logs
```bash
DD_API_KEY="ta-api-key"

# Envoyer des logs via l'API
curl -X POST "https://http-intake.logs.datadoghq.com/api/v2/logs" \
  -H "Content-Type: application/json" \
  -H "DD-API-KEY: ${DD_API_KEY}" \
  -d '[
    {"ddsource":"simplelog","service":"api","message":"INFO server started on port 8080"},
    {"ddsource":"simplelog","service":"api","message":"INFO GET /health 200 5ms"},
    {"ddsource":"simplelog","service":"api","message":"WARN response time > 500ms"},
    {"ddsource":"simplelog","service":"api","message":"ERROR null pointer exception in UserController"}
  ]'

# Attendre ~1 minute puis vérifier dans Datadog → Logs
```

### Configurer SimpleLog
- **Site** : `US1 (datadoghq.com)`
- **API Key** : ta clé API
- **Application Key** : ta clé application
- **Query** : `service:api` ou laisser vide pour tout voir

---

## 10. Kubernetes (local avec minikube)

**Pas de compte nécessaire.** Minikube crée un cluster K8s en local.

### Installer minikube et kubectl
```bash
# Ubuntu/Debian
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Démarrer le cluster
minikube start

# Vérifier
kubectl get nodes
# → NAME       STATUS   ROLES    AGE   VERSION
# → minikube   Ready    control-plane ...
```

### Déployer un pod qui génère des logs
```bash
# Pod qui génère des logs toutes les secondes
kubectl run log-generator \
  --image=busybox \
  --restart=Never \
  -- sh -c 'i=0; while true; do
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] INFO request-$i processed status=200 duration=$((RANDOM%500))ms"
    i=$((i+1))
    sleep 1
  done'

# Vérifier que ça tourne
kubectl get pods
kubectl logs -f log-generator
```

### Configurer SimpleLog
- **Context** : `minikube` (ou laisser vide pour le contexte courant)
- **Namespace** : `default`
- Sélectionner le pod `log-generator`

---

## Récapitulatif

| Provider | Compte requis | Coût | Difficulté setup |
|---|---|---|---|
| Docker | Non | Gratuit | ⭐ Très facile |
| SSH | Non | Gratuit | ⭐ Très facile |
| Grafana Loki | Non | Gratuit | ⭐⭐ Facile |
| Elasticsearch | Non | Gratuit | ⭐⭐ Facile |
| Railway | Oui (GitHub) | $5 crédit | ⭐⭐ Facile |
| Fly.io | Oui (CB requise) | Gratuit | ⭐⭐ Facile |
| Kubernetes | Non | Gratuit | ⭐⭐⭐ Moyen |
| GCP | Oui (CB requise) | $300 crédit | ⭐⭐⭐ Moyen |
| Datadog | Oui | Trial 14j | ⭐⭐ Facile |
| Azure | Oui (CB requise) | $200 crédit | ⭐⭐⭐⭐ Complexe |

**Ordre recommandé** : Docker → SSH → Loki → Elasticsearch → Railway → Fly.io → Kubernetes → Datadog → GCP → Azure
