from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import databases
import sqlalchemy
import httpx
import asyncio
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prokura.db")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "prokura697@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "prokura2026")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

SEARCH_LIMIT_PER_MONTH = 200

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

pedidos = sqlalchemy.Table(
    "pedidos", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("whatsapp", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("produto", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("estado", sqlalchemy.String, default="pendente"),
    sqlalchemy.Column("criado_em", sqlalchemy.DateTime, default=datetime.utcnow),
    sqlalchemy.Column("respondido_em", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("notas", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("google_resultados", sqlalchemy.Integer, nullable=True),
    sqlalchemy.Column("instagram_resultados", sqlalchemy.Integer, nullable=True),
    sqlalchemy.Column("tiktok_resultados", sqlalchemy.Integer, nullable=True),
)

engine = sqlalchemy.create_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://") if "postgresql" in DATABASE_URL else DATABASE_URL
)
metadata.create_all(engine)

app = FastAPI(title="PROkura Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PedidoInput(BaseModel):
    whatsapp: str
    message: str

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

async def get_monthly_search_count() -> int:
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    query = sqlalchemy.select(
        sqlalchemy.func.count()
    ).select_from(pedidos).where(
        sqlalchemy.and_(
            pedidos.c.criado_em >= start_of_month,
            pedidos.c.google_resultados != None
        )
    )
    result = await database.fetch_val(query)
    return result or 0

async def serp_google(produto: str) -> int:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "api_key": SERPAPI_KEY,
                    "engine": "google",
                    "q": f"{produto} Luanda Angola",
                    "num": 1,
                    "gl": "ao",
                    "hl": "pt"
                }
            )
            data = r.json()
            total_str = data.get("search_information", {}).get("total_results", "0")
            return int(str(total_str).replace(",", "").replace(".", "").split()[0]) if total_str else 0
    except Exception as e:
        print(f"Google search error: {e}")
        return -1

async def serp_instagram(produto: str) -> int:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "api_key": SERPAPI_KEY,
                    "engine": "google",
                    "q": f"{produto} Angola fonte site:instagram.com",
                    "num": 1,
                    "gl": "ao",
                    "hl": "pt"
                }
            )
            data = r.json()
            total_str = data.get("search_information", {}).get("total_results", "0")
            return int(str(total_str).replace(",", "").replace(".", "").split()[0]) if total_str else 0
    except Exception as e:
        print(f"Instagram search error: {e}")
        return -1

async def serp_tiktok(produto: str) -> int:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "api_key": SERPAPI_KEY,
                    "engine": "google",
                    "q": f"{produto} Angola fonte site:tiktok.com",
                    "num": 1,
                    "gl": "ao",
                    "hl": "pt"
                }
            )
            data = r.json()
            total_str = data.get("search_information", {}).get("total_results", "0")
            return int(str(total_str).replace(",", "").replace(".", "").split()[0]) if total_str else 0
    except Exception as e:
        print(f"TikTok search error: {e}")
        return -1

async def send_email(whatsapp: str, produto: str, google: int, insta: int, tiktok: int):
    if not RESEND_API_KEY:
        print(f"EMAIL: Novo pedido de {whatsapp} — {produto}")
        return
    def fmt(n):
        return f"{n:,} resultados".replace(",", ".") if n > 0 else "Em curso..."
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": "PROkura <onboarding@resend.dev>",
                "to": [ADMIN_EMAIL],
                "subject": f"Novo pedido — {produto[:40]}",
                "html": f"""
                <div style="font-family:sans-serif;max-width:500px;margin:0 auto">
                  <h2 style="color:#1a1a1a">Novo pedido PROkura</h2>
                  <table style="width:100%;border-collapse:collapse">
                    <tr><td style="padding:8px;color:#888;width:120px">WhatsApp</td>
                        <td style="padding:8px;font-weight:500">+{whatsapp}</td></tr>
                    <tr style="background:#f5f3ef"><td style="padding:8px;color:#888">Produto</td>
                        <td style="padding:8px;font-weight:500">{produto}</td></tr>
                    <tr><td style="padding:8px;color:#888">Google Angola</td>
                        <td style="padding:8px">{fmt(google)}</td></tr>
                    <tr style="background:#f5f3ef"><td style="padding:8px;color:#888">Instagram</td>
                        <td style="padding:8px">{fmt(insta)}</td></tr>
                    <tr><td style="padding:8px;color:#888">TikTok</td>
                        <td style="padding:8px">{fmt(tiktok)}</td></tr>
                    <tr style="background:#f5f3ef"><td style="padding:8px;color:#888">Data</td>
                        <td style="padding:8px">{datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr>
                  </table>
                  <p style="color:#c0392b;font-size:12px;margin-top:16px">PROkura · prokura.ao</p>
                </div>
                """
            }
        )

@app.post("/pedido")
async def criar_pedido(pedido: PedidoInput):
    phone = pedido.whatsapp.replace("+", "").replace(" ", "").replace("-", "")

    monthly_count = await get_monthly_search_count()

    if monthly_count < SEARCH_LIMIT_PER_MONTH and SERPAPI_KEY:
        # Run all 3 searches in parallel — counts as 3 searches
        google, insta, tiktok = await asyncio.gather(
            serp_google(pedido.message),
            serp_instagram(pedido.message),
            serp_tiktok(pedido.message)
        )
    else:
        print(f"Limite mensal atingido ({monthly_count}/{SEARCH_LIMIT_PER_MONTH})")
        google, insta, tiktok = -1, -1, -1

    query = pedidos.insert().values(
        whatsapp=phone,
        produto=pedido.message,
        estado="pendente",
        criado_em=datetime.utcnow(),
        google_resultados=google if google >= 0 else None,
        instagram_resultados=insta if insta >= 0 else None,
        tiktok_resultados=tiktok if tiktok >= 0 else None,
    )
    pedido_id = await database.execute(query)
    await send_email(phone, pedido.message, google, insta, tiktok)

    return {
        "success": True,
        "id": pedido_id,
        "google_resultados": google,
        "instagram_resultados": insta,
        "tiktok_resultados": tiktok,
    }

@app.get("/admin/pedidos")
async def listar_pedidos(password: str = "", estado: str = ""):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Não autorizado")
    query = pedidos.select().order_by(pedidos.c.criado_em.desc())
    if estado:
        query = pedidos.select().where(pedidos.c.estado == estado).order_by(pedidos.c.criado_em.desc())
    rows = await database.fetch_all(query)
    return [dict(r) for r in rows]

@app.put("/admin/pedidos/{pedido_id}/responder")
async def marcar_respondido(pedido_id: int, password: str = "", notas: str = ""):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Não autorizado")
    query = pedidos.update().where(pedidos.c.id == pedido_id).values(
        estado="respondido",
        respondido_em=datetime.utcnow(),
        notas=notas
    )
    await database.execute(query)
    return {"success": True}

@app.get("/health")
async def health():
    monthly_count = await get_monthly_search_count()
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "searches_this_month": monthly_count,
        "search_limit": SEARCH_LIMIT_PER_MONTH
    }

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    with open("admin.html", "r") as f:
        return f.read()