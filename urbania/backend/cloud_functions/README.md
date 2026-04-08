# URBANIA - Serverless Core (IBM Cloud Functions)

Esta carpeta contiene los wrappers necesarios para orquestar los agentes basados en IA y el flujo de Ingesta → Negocios usando **IBM Cloud Functions**, convirtiendo el núcleo del backend de URBANIA en una función serverless altamente escalable.

## Requisitos Previos

1. **IBM Cloud CLI**:
   - macOS: `brew install ibm-cloud-cli`
   - Linux: `curl -fsSL https://clis.cloud.ibm.com/install/linux | sh`
   - Windows: Descargar desde [GitHub IBM Cloud CLI](https://github.com/IBM-Cloud/ibm-cloud-cli-release)

2. Instalar el plugin de Cloud Functions:
   ```bash
   ibmcloud plugin install cloud-functions
   ```

3. Herramientas de sistema:
   - `python 3.11`
   - `pip`
   - `zip`

## Configuración y API Keys

Necesitarás configurar 3 variables críticas en un archivo `.env` o en tu entorno antes de desplegar:
- **`IBM_API_KEY`**: API Key general de tu cuenta de IBM Cloud (para el login del CLI).
- **`WATSONX_API_KEY`**: Credencial del servicio IAM para invocar modelos fundacionales Granite.
- **`WATSONX_PROJECT_ID`**: ID del proyecto dentro de la plataforma watsonx.ai.

## Despliegue Automatizado

Ejecuta el script proporcionado. Este se encargará de automatizar las descargas de paquetes (en sus carpetas aisaldas), comprimir e invocar a IBM CLI para la actualización nativa:

```bash
chmod +x deploy.sh
./deploy.sh
```

## Conexión del Frontend

Una vez desplegado con éxito, el script retornará una URL base del API Gateway de IBM Cloud. Configura esta URL en las variables de entorno de tu solución frontend (ej. Next.js, Vite, React).

Si usas Vercel:
```bash
vercel env add VITE_API_BASE_URL
```

Si usas Netlify:
```bash
netlify env:set VITE_API_BASE_URL <url>
```
*También puedes editar la variable VITE_API_BASE_URL en el dashboard gráfico Site Settings.*

## Testing Manual (CURL)

Puedes probar las rutas recién desplegadas:

```bash
# 1. Probar el analisis base
curl -X POST <API_URL>/analyze \
  -H "Content-Type: application/json" \
  -d '{"sector": "telecomunicaciones"}'

# 2. Refinar export global 
curl -X POST <API_URL>/export \
  -H "Content-Type: application/json" \
  -d '{"analysis_data": {...}}'
```

## Troubleshooting (FAQ)

- **CORS Errors**: Las IBM Cloud Functions usando API Gateway actúan directamente transmitiendo el output raw. Nuestros wrappers de `__main__.py` ya inyectan los headers `"Access-Control-Allow-Origin": "*"`. Si aún experimentas errores de CORS, verifica en el IBM Cloud Dashboard tu configuración local del Gateway que no lo esté limitando de manera estricta.
- **`TimeoutError / Cancelled`**: Ejecutar a los Agentes de Demanda y Riesgo en paralelo usualmente toma ~35s. El API Gateway de IBM Functions tiene un Hard Limit estricto de **60 Segundos**. El wrapper en `/analyze_action` tiene un catch automático a los `50s` para devolver una respuesta parcial en vez de arrojar `502 Bad Gateway`.
- **`Token Authentication Failed`**: Es habitual si el token IAM o el Project_ID de WatsonX cambiaron. Vuelve a actualizarlos en IBM Cloud ejecutando individualmente: `ibmcloud fn action update urbania/analyze --param WATSONX_API_KEY "KEY"`.

---
*Configuración oficial bajo la arquitectura final de **XOLUM URBANIA SaaS B2B**. 2026.*
