#!/bin/bash
# ============================================================
# REQUISITOS PREVIOS — instalar ibmcloud CLI:
#   macOS:   brew install ibm-cloud-cli
#   Linux:   curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
#   Windows: descargar desde https://github.com/IBM-Cloud/ibm-cloud-cli-release
# Después: ibmcloud login --apikey TU_API_KEY -r us-south
#          ibmcloud plugin install cloud-functions
# ============================================================

set -e  # salir en cualquier error

# Variables (leer de .env si existe)
source .env 2>/dev/null || true
NAMESPACE="urbania-hackathon"
REGION="us-south"

echo "🚀 Desplegando URBANIA en IBM Cloud Functions..."

# 1. Login y namespace
ibmcloud login --apikey "$IBM_API_KEY" -r $REGION -q
ibmcloud fn namespace create $NAMESPACE 2>/dev/null || true
ibmcloud fn namespace target $NAMESPACE

# 2. Empaquetar analyze_action
echo "📦 Empaquetando analyze_action..."
cd analyze_action
# Copiar las dependencias intrínsecas de URBANIA para serverless zip
cp -r ../../agents .
cp -r ../../data .
pip install -r requirements.txt --target ./packages --quiet
zip -r ../analyze_action.zip __main__.py packages/ agents/ data/ -x "*.pyc" -x "*/__pycache__/*"
# Cleanup temporales
rm -rf agents data
cd ..

# 3. Desplegar analyze_action
echo "🚀 Desplegando analyze_action..."
ibmcloud fn action update urbania/analyze analyze_action.zip \
  --kind python:3.11 \
  --memory 512 \
  --timeout 60000 \
  --param WATSONX_API_KEY "$WATSONX_API_KEY" \
  --param WATSONX_PROJECT_ID "$WATSONX_PROJECT_ID" \
  --param URBANIA_PROD_MODE "false"

# 4. Empaquetar export_action
echo "📦 Empaquetando export_action..."
cd export_action
pip install -r requirements.txt --target ./packages --quiet 2>/dev/null || true
zip -r ../export_action.zip __main__.py packages/ -x "*.pyc" -x "*/__pycache__/*"
cd ..

# 5. Desplegar export_action
echo "🚀 Desplegando export_action..."
ibmcloud fn action update urbania/export export_action.zip \
  --kind python:3.11 \
  --memory 256 \
  --timeout 30000

# 6. Crear rutas API (IBM API Gateway nativo de Cloud Functions, gratuito)
echo "🌐 Configurando API Gateway..."
ibmcloud fn api create /urbania /analyze   POST urbania/analyze --response-type json 2>/dev/null || \
ibmcloud fn api update /urbania /analyze   POST urbania/analyze --response-type json

ibmcloud fn api create /urbania /export    POST urbania/export  --response-type json 2>/dev/null || \
ibmcloud fn api update /urbania /export    POST urbania/export  --response-type json

ibmcloud fn api create /urbania /mock-zone GET  urbania/analyze --response-type json 2>/dev/null || true

# 7. Obtener y mostrar URLs
echo ""
echo "✅ Despliegue completado."
echo ""
API_URL=$(ibmcloud fn api list --output json | python3 -c "
import sys, json
try:
    apis = json.load(sys.stdin)
    for api in apis.get('apis', []):
        url = api.get('value', {}).get('apidoc', {}).get('basePath', '')
        if 'urbania' in url.lower():
            print(url)
            break
except:
    print('<API_URL>')
")
echo "📡 Base URL de la API: $API_URL"
echo "   POST $API_URL/analyze   ← análisis principal"
echo "   POST $API_URL/export    ← exportar GeoJSON / PDF ready"
echo ""
echo "🔧 Actualiza VITE_API_BASE_URL en el frontend con esta URL."
echo "   Si usas Vercel: vercel env add VITE_API_BASE_URL"
echo "   Si usas Netlify: netlify env:set VITE_API_BASE_URL <url>"
