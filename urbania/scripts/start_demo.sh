#!/bin/bash
# Ejecutar desde la raiz de urbania: bash scripts/start_demo.sh
echo "🚀 Iniciando URBANIA en modo demo..."
cd backend && python scripts/demo_seed.py
cd ..
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 &
cd ../frontend && npm run dev &
echo "✅ URBANIA disponible en http://localhost:5173"
echo "📊 API docs en http://localhost:8000/docs"
