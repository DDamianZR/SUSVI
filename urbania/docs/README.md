# Documentación Arquitectónica - URBANIA PlantUML

Esta carpeta contiene la documentación técnica de la plataforma URBANIA generada bajo el estándar UML a través de [PlantUML](https://plantuml.com/).

## 📁 Diagramas Incluidos:

1. **`component_diagram.puml`**: Mapeo macroscópico de los módulos Frontend (Vite) y Backend (FastAPI, Ingestion, Agents).
2. **`sequence_diagram.puml`**: Línea de tiempo end-to-end de un request desde la UI al ecosistema de Watsonx y su respuesta en tiempo real.
3. **`class_diagram.puml`**: Relaciones, atributos y métodos de la Lógica de Negocios en Python (Agents, Utils, Features).
4. **`deployment_diagram.puml`**: Nodos físicos e instancias cloud (Local Dev, Cloud Functions Serverless).

## 🛠️ Cómo Renderizar los Diagramas

El código es texto plano `.puml` que requiere ser renderizado a imágenes (`.png`, `.svg` o embebido).

### Opción 1: Visualizador Online (Sin Instalar Nada)
1. Ve a [PlantUML Web Server](https://www.plantuml.com/plantuml/).
2. Copia y pega el contenido de cualquier archivo `.puml` en el recuadro de texto.
3. El diagrama se dibujará automáticamente en la parte inferior.

### Opción 2: Extensión de VS Code (Recomendado)
1. Instala la extensión **PlantUML** (`jebbs.plantuml`) en Visual Studio Code.
2. Abre cualquier archivo `.puml`.
3. Presiona `Alt + D` (o `Opción + D` en Mac) para previsualizar el diagrama en una pestaña paralela junto a tu código.
4. Usa Click Derecho -> "Export Current Diagram" para guardarlo como PNG/SVG.

### Opción 3: PlantUML CLI o Java
Si tienes Java instalado en tu equipo, puedes renderizar todos los diagramas de golpe en la consola:
```bash
# Descarga plantuml.jar desde su web (o via brew install plantuml)
# Ejecuta en este directorio
plantuml *.puml
```
Esto generará los archivos de imagen directamente en esta misma carpeta, listos para adjuntarse a presentaciones u otros documentos.
