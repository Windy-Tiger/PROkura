# PROkura Backend

## Deploy no Railway

1. Cria conta em railway.app
2. New Project → Deploy from GitHub repo
3. Adiciona PostgreSQL — Add Plugin → PostgreSQL
4. Em Variables adiciona:
   - DATABASE_URL (Railway preenche automaticamente)
   - RESEND_API_KEY (da tua conta resend.com)
   - ADMIN_EMAIL (prokura697@gmail.com)
   - ADMIN_PASSWORD (escolhe uma password segura)

## Endpoints

POST /pedido           → recebe pedido do site
GET  /admin/pedidos    → lista pedidos (requer password)
PUT  /admin/pedidos/:id/responder → marca como respondido
GET  /health           → verifica se está online
GET  /admin            → painel admin visual

## Actualizar o site (index.html)

Substitui o FORMSPREE_ENDPOINT pela URL do Railway:
const FORMSPREE_ENDPOINT = 'https://SEU-PROJECTO.railway.app/pedido';
