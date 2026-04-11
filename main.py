from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import databases
import sqlalchemy
import httpx
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prokura.db")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "prokura697@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "prokura2026")

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

class AdminLogin(BaseModel):
    password: str

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

async def send_email(whatsapp: str, produto: str):
    if not RESEND_API_KEY:
        print(f"EMAIL: Novo pedido de {whatsapp} — {produto}")
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": "PROkura <noreply@prokura.ao>",
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
                    <tr><td style="padding:8px;color:#888">Data</td>
                        <td style="padding:8px">{datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr>
                  </table>
                  <div style="margin-top:20px;padding:12px;background:#fafaf8;border:1px solid #eee;border-radius:4px">
                    <p style="margin:0;font-size:13px;color:#888">
                      Abre o WhatsApp e envia a confirmação para <strong>+{whatsapp}</strong>
                    </p>
                  </div>
                  <p style="color:#c0392b;font-size:12px;margin-top:16px">PROkura · prokura.ao</p>
                </div>
                """
            }
        )

@app.post("/pedido")
async def criar_pedido(pedido: PedidoInput):
    phone = pedido.whatsapp.replace("+", "").replace(" ", "").replace("-", "")
    query = pedidos.insert().values(
        whatsapp=phone,
        produto=pedido.message,
        estado="pendente",
        criado_em=datetime.utcnow()
    )
    pedido_id = await database.execute(query)
    await send_email(phone, pedido.message)
    return {"success": True, "id": pedido_id}

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
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    with open("admin.html", "r") as f:
        return f.read()
