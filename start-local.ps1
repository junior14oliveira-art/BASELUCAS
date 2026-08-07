# Script de Inicialização Local para Testes - Plataforma SaaS Omnichannel AI
Write-Host "============================================================" -ForegroundColor Cipher
Write-Host "🚀 Iniciando Plataforma SaaS Omnichannel AI (BaseLinker Spec)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cipher

# 1. Subir Infraestrutura Docker Compose (Postgres, Redis, RabbitMQ)
Write-Host "`n📦 Subindo containers Docker (PostgreSQL, Redis, RabbitMQ)..." -ForegroundColor Yellow
docker-compose up -d

# 2. Instruções do Backend FastAPI
Write-Host "`n🐍 Para executar o Backend Python FastAPI:" -ForegroundColor Cyan
Write-Host "   cd apps/api"
Write-Host "   pip install -r requirements.txt"
Write-Host "   python -m uvicorn src.main:app --reload --port 8000"
Write-Host "   Swagger Docs: http://localhost:8000/api/v1/docs"

# 3. Instruções do Frontend Next.js MD3
Write-Host "`n⚛️ Para executar o Frontend Next.js (Material Design 3):" -ForegroundColor Cyan
Write-Host "   cd apps/web"
Write-Host "   npm install"
Write-Host "   npm run dev"
Write-Host "   Interface Web: http://localhost:3000"

Write-Host "`n============================================================" -ForegroundColor Cipher
Write-Host "✨ Testes Locais Prontos! Modo MOCK_INTEGRATIONS ativado." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cipher
