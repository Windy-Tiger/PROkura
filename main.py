from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from datetime import datetime
import databases
import sqlalchemy
import httpx
import asyncio
import io
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
    sqlalchemy.Column("codigo", sqlalchemy.String, nullable=True),
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

def gerar_codigo(pedido_id: int) -> str:
    now = datetime.utcnow()
    months = ['JAN','FEV','MAR','ABR','MAI','JUN','JUL','AGO','SET','OUT','NOV','DEZ']
    return f"PK-{months[now.month-1]}-{pedido_id:04d}"

def gerar_pdf(codigo: str, produto: str, whatsapp: str, google: int, insta: int, tiktok: int, data_str: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY

    PRETO = colors.HexColor('#1a1a1a')
    VERMELHO = colors.HexColor('#c0392b')
    CINZA = colors.HexColor('#888888')
    CINZA_BG = colors.HexColor('#f5f3ef')
    CINZA_LINHA = colors.HexColor('#e8e4dc')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=25*mm, rightMargin=25*mm, topMargin=20*mm, bottomMargin=20*mm)

    s_brand = ParagraphStyle('brand', fontName='Times-Bold', fontSize=36, textColor=PRETO, alignment=TA_CENTER, spaceAfter=2, leading=40)
    s_tagline = ParagraphStyle('tagline', fontName='Times-Italic', fontSize=10, textColor=CINZA, alignment=TA_CENTER, spaceAfter=12, leading=13)
    s_h1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=12, textColor=PRETO, spaceAfter=6, spaceBefore=2)
    s_body = ParagraphStyle('body', fontName='Times-Roman', fontSize=10, textColor=PRETO, leading=16, spaceAfter=6, alignment=TA_JUSTIFY)
    s_small = ParagraphStyle('small', fontName='Helvetica', fontSize=8, textColor=CINZA, leading=12, spaceAfter=3)
    s_sign = ParagraphStyle('sign', fontName='Times-Roman', fontSize=10, textColor=PRETO, alignment=TA_RIGHT, leading=16, spaceAfter=3)

    def fmt(n):
        return f"{n:,}".replace(",", ".") if n and n > 0 else "Em curso"

    story = []
    story.append(Paragraph(
        '<font face="Times-Bold" color="#1a1a1a">PRO</font>'
        '<font face="Times-Roman" color="#c0392b">kura</font>',
        s_brand
    ))
    story.append(Paragraph('Porque quem PROkura sempre encontra', s_tagline))

    info = Table([
        ['Código do pedido', codigo],
        ['Produto', produto],
        ['Contacto', f'+{whatsapp}'],
        ['Data', data_str],
    ], colWidths=[42*mm, 118*mm])
    info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), CINZA),
        ('TEXTCOLOR', (1,0), (1,-1), PRETO),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (-1,-1), CINZA_BG),
        ('LINEBELOW', (0,0), (-1,-2), 0.4, colors.HexColor('#ddd7cc')),
    ]))
    story.append(info)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph('Resultados Preliminares', s_h1))
    resultados = Table([
        ['Fonte', 'Correspondências encontradas'],
        ['Google Angola', fmt(google)],
        ['Instagram (fontes Angola)', fmt(insta)],
        ['TikTok (fontes Angola)', fmt(tiktok)],
    ], colWidths=[80*mm, 80*mm])
    resultados.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRETO),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('TEXTCOLOR', (0,1), (-1,-1), PRETO),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('LINEBELOW', (0,0), (-1,-2), 0.4, CINZA_LINHA),
    ]))
    story.append(resultados)
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        'Mercados físicos accionados: Cidade da China · Hoji ya Henda · Grupos WhatsApp',
        s_small
    ))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph('Nota sobre este relatório', s_h1))
    disclaimer_paragraphs = [
        "Bem-vindo ao PROkura. Antes de mais, muito obrigado por nos contactar — é com muito prazer "
        "que faremos todos os possíveis para corresponder às suas expectativas. Este relatório preliminar foi "
        "produzido com o auxílio de ferramentas de programação e inteligência artificial, que "
        "automaticamente activam os nossos agentes nos mercados informais de Luanda com o pedido de "
        "cotação e realizam simultaneamente uma pesquisa pelo número de correspondências no universo "
        "digital de Angola. Serve de ponto de partida e de confirmação da existência de oferta no mercado.",

        "O PROkura existe precisamente para colmatar as lacunas do processo de encontrar algo em Angola "
        "— nomeadamente a informação desactualizada ou incorrecta que frequentemente circula. Por este "
        "motivo, reservamos um período de 24 horas para que o resultado final seja mais completo, mais "
        "correcto e confirmado por nós. Nesse período expandimos a pesquisa ao nosso catálogo interno, aos "
        "nossos fornecedores, ao mercado nacional e acima de tudo confirmamos a informação antes de a "
        "partilhar. Receberá a cotação completa no seu WhatsApp dentro de 24 horas.",
    ]
    for para in disclaimer_paragraphs:
        story.append(Paragraph(para, s_body))

    story.append(Spacer(1, 10*mm))
    story.append(Paragraph('Em nome da equipa PROkura,', s_sign))
    story.append(Paragraph('Obrigado.', s_sign))

    doc.build(story)
    return buffer.getvalue()

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
        codigo=None,
    )
    pedido_id = await database.execute(query)
    codigo = gerar_codigo(pedido_id)
    await database.execute(
        pedidos.update().where(pedidos.c.id == pedido_id).values(codigo=codigo)
    )
    await send_email(phone, pedido.message, google, insta, tiktok)

    return {
        "success": True,
        "id": pedido_id,
        "codigo": codigo,
        "google_resultados": google,
        "instagram_resultados": insta,
        "tiktok_resultados": tiktok,
    }

@app.get("/admin/pedidos/{codigo}/pdf")
async def download_pdf(codigo: str, password: str = ""):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Não autorizado")
    row = await database.fetch_one(pedidos.select().where(pedidos.c.codigo == codigo))
    if not row:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    r = dict(row)
    data_str = r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else ""
    pdf_bytes = gerar_pdf(
        codigo=r['codigo'],
        produto=r['produto'],
        whatsapp=r['whatsapp'],
        google=r.get('google_resultados') or 0,
        insta=r.get('instagram_resultados') or 0,
        tiktok=r.get('tiktok_resultados') or 0,
        data_str=data_str
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=prokura_{codigo}.pdf"}
    )

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