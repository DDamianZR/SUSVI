# PITCH_TECHNICAL - Guía para el Hackathon 🎙️

Esta guía proporciona el orden exacto del flujo a mostrar en tu demostración de 3 minutos para convencer al jurado técnico y de negocios, junto a las respuestas magistralmente curadas a preguntas esperadas del jurado.

## Flujo de Demo (3 Minutos Exactos)

1. **(0:00 - 0:20) [Apertura & Planteo de Problema]**  
   Abrir la aplicación web mostrando el **mapa oscuro con las contornos limpios de la CDMX**. _"Bienvenidos a URBANIA. En México, abrir o desarrollar infraestructura territorial a gran escala se decide por instinto, tomando meses de consultoría. Esto cuesta tiempo y millones en zonas inviables. Hoy, lo resolvemos instantáneamente."_
   
2. **(0:20 - 0:40) [Parametrización IA]**  
   Ir al panel de configuración (Sector Selector), seleccionar el target **"Telecomunicaciones"** y fijar rápidamente algunos parámetros de negocio como el Ticket Inversión y Tasa Descuento.
   
3. **(0:40 - 1:10) [Ejecución & Efecto WOAH]**  
   Clicar en el botón ámbar de **"Analizar Zona / Cargar Análisis"**.  
   _Muestra cómo_ el mapa en pantalla parpadea con el loading visual, y tras uno o dos segundos, **los polígonos explotan visualmente con los colores predictivos**. Relata que 13B Watsonx.ai Agents y Math Metrics acaban de perfilar el polígono dinámicamente frente al entorno.

4. **(1:10 - 1:40) [Interacción & Dashboard C-Suite]**  
   Activa/desactiva los toggles flotantes, mostrando las variaciones espaciales y clica concretamente en un polígono (zona VERDE). Que la mesa de jueces observe el Popup con su **clasificación sectorial y la narrativa extraída de IA**.
   
5. **(1:40 - 2:30) [Decisiones Financieras (The Core Value)]**  
   Atrae la mirada al panel lateral de la izquierda de **"Escenarios de Despliegue"**. Explica brevemente el escenario *Equilibrado* indicando su **ROI y el Payback**, y detalla cómo esto traduce Big Geo-Data pura en KPI's operacionales y bancarios.
   
6. **(2:30 - 3:00) [Cierre y Reporte Físico]**  
   Clica el botón maestro de **"Descargar PDF Ejecutivo"**. Se genera el reporte ReportLab. Abre el PDF frente a la cámara mostrando la tabla con el Zebra Striping y la paleta formal, y cierra con: _"URBANIA reduce 4 meses de due-diligence en Big Data georreferencial a este único PDF gerencial generado en menos de un minuto."_


## QA y Defensas Preparadas Contra Jurados Exigentes 🛡️

**¿Cómo usan IBM Watsonx específicamente?**  
→ Tres agentes especializados con *Granite 13B* paralelos. Cada agente recibe datos estructurados geoespaciales y produce un JSON parseable (Agente de Demandas, Agente de Riesgo). Nuestro "Agente de Negocios" usa el modelo fundacional como un traductor algorítmico, convirtiendo scores secos y matemáticos a un lenguaje cualitativo o ejecutivo y estructurando escenarios que los CFOs de la vida real exigen. El fallback algorítmico nos permite mantener la operatividad sin sacrificar el frontend aunque Watsonx estuviera apagado.

**¿Por qué tres agentes separados en lugar de uno?**  
→ Separación de responsabilidades y *Hyper-paralelismo asíncrono*, usando funciones nativas Python (`asyncio.gather`). Demanda y Riesgo corren de manera agnóstica al mismo tiempo, recortando por completo la latencia. Cada Agente posee un System Prompt estrictamente delimitado permitiendo generar arquitecturas predecibles y de alta especialidad. Un Big-Agent causaría "desvarios", latencias brutales y generaría tokens mal-formados.

**¿Cómo escalaría esto a datos reales de todo México?**  
→ La estructura está armada. Con setear la variable booleana `URBANIA_PROD_MODE=true` reactivamos las canalizaciones nativas que creamos en nuestro modulo M1 (Ingesta) con extractores espaciales hacia DENUE, SNSP y la infraestructura VIIRS satelital. Sumado a nuestra arquitectura serverless `Action-Based` desplegable enteramente a **IBM Cloud Functions**, Urbania puede computar infinitas manzanas a la vez, escalando bajo una política estricta _Pay-per-Compute_ transparente y sin servidores durmientes.

**¿Qué tan precisos son sus "scores"?**  
→ Es importante aclarar que son *indicadores relativos macro*, NO predicciones absolutas de machine learning supervisado. Su tracción reside en categorizar y rankear dinámicamente. Sabemos con certidumbre que una zona categorizada en 85pts por acceso logístico e ingresos generará un performance diferencial aplastante en contraste con una de 30pts en entorno equivalente. Además, los pesos algorítmicos son hiper-optimizables basándonos en el performance de los primeros despliegues de un cliente real.

**Si uso Google Maps Platform o ArcGis, ¿Ya hago esto no?**  
→ No. Google Maps y ESRI proveen visualización, y dejan el cálculo de oportunidad, el descarte matemático y la inferencia puramente en ti. URBANIA fue concebido para ser un **Motor B2B de inteligencia financiera**, es decir, no sólo muestra sino que **dictamina a un comité qué locaciones son INVIABLES (zona descarte)**, precalculando ROI y ahorrando millones en operaciones riesgosas de calle (crimen/delincuencia, accesibilidad y rentabilidad proyectada). Somos un SAAS transaccional analítico.

---
### Métricas Impactantes Relevantes:
- De **3-6 meses de consultorías externas** tradicionales pasamos a **< 2 min de procesamiento AI**.
- La rentabilidad (SaaS Tier) frente al costo por proyecto de análisis privado asciende al **30X+ ROI**.
- Despliegue agnóstico (Local/Cloud), 3 Agentes especializados, PDF offline autogenerado.
