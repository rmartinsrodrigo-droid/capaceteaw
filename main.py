from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, init_db, get_db
from models import Solicitacao, Fornecedor, Logo, Comentario, Arquivo
import uuid
from datetime import datetime
import os
from typing import List
from validators import validar_cancelamento, validar_transicao_status, validar_aprovacao_arte
import shutil
from storage import salvar_arquivo
from auth import (generate_otp, send_otp_email, verify_otp_and_login,
                  get_current_user, exigir_perfil)
from models import Usuario

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Capacete AW - Personalizacao de Capacetes")

# No Vercel o disco e somente-leitura: uploads vao pra /tmp; static so monta se existir.
UPLOAD_DIR = "/tmp/uploads"
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except Exception:
    pass

_static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# ---------- Usuarios iniciais (perfis) ----------
def seed_usuarios():
    from database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(Usuario).count() == 0:
            base = [
                ("Marketing AW", "marketing@athiewohnrath.com.br", "Marketing"),
                ("Compras AW", "compras@athiewohnrath.com.br", "Compras"),
                ("Fornecedor Parceiro", "fornecedor@exemplo.com.br", "Fornecedor"),
                ("Solicitante AW", "solicitante@athiewohnrath.com.br", "Solicitante"),
            ]
            for nome, email, perfil in base:
                db.add(Usuario(nome=nome, email=email, perfil=perfil, ativo="Ativo"))
            db.commit()
    finally:
        db.close()

# Boot tolerante: se o banco ainda nao estiver conectado (ex: durante o build),
# nao derruba a aplicacao; tenta de novo a cada cold start.
_initialized = False
def _bootstrap():
    global _initialized
    if _initialized:
        return
    try:
        init_db()
        seed_usuarios()
        _initialized = True
    except Exception as e:
        print(f"[bootstrap adiado] {e}")

@app.middleware("http")
async def _ensure_init(request: Request, call_next):
    _bootstrap()
    return await call_next(request)

_bootstrap()

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ==================== AUTENTICAÇÃO + OTP ====================
@app.post("/auth/solicitar_otp")
async def solicitar_otp(email: str = Form(...), db: Session = Depends(get_db)):
    """Envia codigo de acesso para um e-mail cadastrado."""
    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.ativo == "Ativo").first()
    if not usuario:
        raise HTTPException(status_code=403, detail="E-mail nao autorizado. Fale com o Marketing.")
    otp = generate_otp(email, db)
    send_otp_email(email, otp)
    return {"message": "Codigo enviado para o e-mail.", "email": email}

@app.post("/auth/verificar_otp")
async def verificar_otp(email: str = Form(...), otp: str = Form(...), db: Session = Depends(get_db)):
    """Valida o codigo e devolve token de sessao + perfil real."""
    return verify_otp_and_login(email, otp, db)

@app.post("/usuarios/")
def cadastrar_usuario(
    nome: str = Form(...),
    email: str = Form(...),
    perfil: str = Form(...),
    user: dict = Depends(exigir_perfil("Marketing")),
    db: Session = Depends(get_db)
):
    """Cadastra uma pessoa real do time. Apenas Marketing pode."""
    if perfil not in ["Marketing", "Compras", "Fornecedor", "Solicitante"]:
        raise HTTPException(status_code=400, detail="Perfil invalido.")
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado.")
    novo = Usuario(nome=nome, email=email, perfil=perfil, ativo="Ativo")
    db.add(novo); db.commit(); db.refresh(novo)
    return {"message": "Usuario cadastrado", "id": novo.id, "perfil": perfil}

@app.get("/usuarios/")
def listar_usuarios(user: dict = Depends(exigir_perfil("Marketing")), db: Session = Depends(get_db)):
    return {"usuarios": [{"nome": u.nome, "email": u.email, "perfil": u.perfil, "ativo": u.ativo}
                         for u in db.query(Usuario).all()]}

@app.get("/auth/eu")
def quem_sou_eu(user: dict = Depends(get_current_user)):
    """Confere a sessao atual (quem esta logado e qual o perfil)."""
    return user


# ==================== BIBLIOTECA DE LOGOS ====================
@app.post("/logos/")
async def cadastrar_logo(
    empresa: str = Form(...), 
    site: str = Form(...), 
    db: Session = Depends(get_db)
):
    """Cadastra logo homologado"""
    logo = Logo(empresa=empresa, site=site, homologado=datetime.utcnow())
    db.add(logo)
    db.commit()
    db.refresh(logo)
    return {"message": "Logo cadastrado com sucesso", "id": logo.id}

@app.get("/logos/")
def listar_logos(db: Session = Depends(get_db)):
    """Lista logos homologados"""
    logos = db.query(Logo).all()
    return {"logos": logos}

@app.get("/logos/buscar")
def buscar_logo(empresa: str = None, site: str = None, db: Session = Depends(get_db)):
    """Busca logo por empresa ou site"""
    query = db.query(Logo)
    if empresa:
        query = query.filter(Logo.empresa.ilike(f"%{empresa}%"))
    if site:
        query = query.filter(Logo.site.ilike(f"%{site}%"))
    logo = query.first()
    if logo:
        return {"encontrado": True, "logo": logo}
    return {"encontrado": False}


# ==================== ATRIBUIÇÃO DE FORNECEDORES ====================
@app.post("/fornecedores/")
async def cadastrar_fornecedor(nome: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    """Cadastra novo fornecedor"""
    fornecedor = Fornecedor(nome=nome, email=email)
    db.add(fornecedor)
    db.commit()
    db.refresh(fornecedor)
    return {"message": "Fornecedor cadastrado", "id": fornecedor.id}

@app.get("/fornecedores/")
def listar_fornecedores(db: Session = Depends(get_db)):
    return {"fornecedores": db.query(Fornecedor).all()}

@app.post("/solicitacoes/{protocolo}/atribuir_fornecedor")
async def atribuir_fornecedor(
    protocolo: str, 
    fornecedor_id: int, 
    user: dict = Depends(exigir_perfil("Marketing", "Compras")),
    db: Session = Depends(get_db)
):
    """Atribui fornecedor à solicitação"""
    solicitacao = db.query(Solicitacao).filter(Solicitacao.protocolo == protocolo).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    
    solicitacao.fornecedor_id = fornecedor_id
    solicitacao.status = "Fornecedor Atribuído"
    
    db.commit()
    db.refresh(solicitacao)
    return {"message": "Fornecedor atribuído com sucesso", "protocolo": protocolo}


# ==================== NOTIFICAÇÕES (Simuladas) ====================
def enviar_notificacao(email: str, evento: str, protocolo: str):
    """Simula envio de notificações"""
    print(f"[NOTIFICAÇÃO] Para {email} - Evento: {evento} - Protocolo: {protocolo}")
    # Real: integrar com SMTP ou serviço externo

@app.post("/notificacoes/teste")
async def teste_notificacao(email: str, evento: str, protocolo: str):
    enviar_notificacao(email, evento, protocolo)
    return {"message": "Notificação enviada (simulada)"}


# ==================== DASHBOARD EXECUTIVO ====================
from fastapi.templating import Jinja2Templates
_tmpl_dir = os.path.join(BASE_DIR, "templates")
if not os.path.isdir(_tmpl_dir):
    _tmpl_dir = BASE_DIR
templates = Jinja2Templates(directory=_tmpl_dir)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/solicitacoes/")
def listar_solicitacoes(
    status: str = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista todas as solicitacoes. Filtro opcional por status."""
    q = db.query(Solicitacao)
    if status:
        q = q.filter(Solicitacao.status == status)
    pedidos = q.order_by(Solicitacao.data_abertura.desc()).all()
    return {
        "perfil": user["perfil"],
        "email": user["email"],
        "solicitacoes": [
            {
                "protocolo": s.protocolo,
                "solicitante": s.solicitante,
                "email": s.email,
                "cliente": s.cliente,
                "projeto": s.projeto,
                "quantidade": s.quantidade,
                "cidade": s.cidade,
                "estado": s.estado,
                "status": s.status,
                "data_abertura": s.data_abertura,
                "fornecedor_id": s.fornecedor_id,
            }
            for s in pedidos
        ]
    }


@app.get("/solicitacoes/lista")
def listar_solicitacoes(
    status: str = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(Solicitacao)
    if status:
        q = q.filter(Solicitacao.status == status)
    pedidos = q.order_by(Solicitacao.data_abertura.desc()).all()
    return {
        "perfil": user["perfil"],
        "email": user["email"],
        "solicitacoes": [
            {
                "protocolo": s.protocolo,
                "solicitante": s.solicitante,
                "email": s.email,
                "cliente": s.cliente,
                "projeto": s.projeto,
                "quantidade": s.quantidade,
                "cidade": s.cidade,
                "estado": s.estado,
                "status": s.status,
                "data_abertura": str(s.data_abertura)[:10] if s.data_abertura else "",
                "fornecedor_id": s.fornecedor_id,
            }
            for s in pedidos
        ]
    }

@app.post("/solicitacoes/")
async def criar_solicitacao(
    nome: str = Form(...),
    email: str = Form(...),
    cliente: str = Form(...),
    site_cliente: str = Form(None),
    parceiro: str = Form(None),
    site_parceiro: str = Form(None),
    quantidade: int = Form(...),
    projeto: str = Form(...),
    cidade: str = Form(...),
    estado: str = Form(...),
    observacoes: str = Form(None),
    db: Session = Depends(get_db)
):
    protocolo = f"ATV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    solicitacao = Solicitacao(
        protocolo=protocolo,
        solicitante=nome,
        email=email,
        cliente=cliente,
        site_cliente=site_cliente,
        parceiro=parceiro,
        site_parceiro=site_parceiro,
        quantidade=quantidade,
        projeto=projeto,
        cidade=cidade,
        estado=estado,
        observacoes=observacoes,
        status="Solicitação Recebida"
    )
    db.add(solicitacao)
    db.commit()
    db.refresh(solicitacao)
    
    return {"message": "Solicitação enviada com sucesso.", "protocolo": protocolo}

@app.get("/solicitacoes/{protocolo}")
def consultar_status(protocolo: str, db: Session = Depends(get_db)):
    solicitacao = db.query(Solicitacao).filter(Solicitacao.protocolo == protocolo).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    
    # Get arquivos
    arquivos = [{"nome": a.arquivo, "versao": a.versao, "data": a.data_upload} for a in solicitacao.arquivos]
    
    return {
        "protocolo": solicitacao.protocolo,
        "status": solicitacao.status,
        "solicitante": solicitacao.solicitante,
        "cliente": solicitacao.cliente,
        "arquivos": arquivos,
        "historico": []  # TODO: expandir com auditoria completa
    }

# ==================== UPLOAD DE ARTES + CONTROLE DE VERSÕES ====================

@app.post("/solicitacoes/{protocolo}/upload_arte")
async def upload_arte(
    protocolo: str,
    file: UploadFile = File(...),
    perfil: str = Form(...),  # Fornecedor, Marketing, etc.
    comentario: str = Form(None),
    db: Session = Depends(get_db)
):
    """Upload de arte com controle de versões (PDF, PNG, JPG)"""
    solicitacao = db.query(Solicitacao).filter(Solicitacao.protocolo == protocolo).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    
    # Validação de tipo de arquivo (PRD Seção 10)
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF, PNG ou JPG são permitidos.")
    
    # Controle de versão
    versao_atual = db.query(Arquivo).filter(Arquivo.solicitacao_id == solicitacao.id).count() + 1
    filename = f"arte_v{versao_atual}{file_ext}"

    # Salvar no Vercel Blob (ou /tmp em teste) e guardar a URL
    conteudo = await file.read()
    resultado = salvar_arquivo(f"{protocolo}/{filename}", conteudo, file.content_type or "application/octet-stream")

    novo_arquivo = Arquivo(
        solicitacao_id=solicitacao.id,
        arquivo=filename,
        versao=versao_atual,
        data_upload=datetime.utcnow(),
        url=resultado["url"]
    )
    db.add(novo_arquivo)
    
    # Atualizar status para "Arte Disponível para Aprovação" se for upload de fornecedor
    if perfil == "Fornecedor":
        solicitacao.status = "Arte Disponível para Aprovação"
    
    # Comentário
    if comentario:
        novo_comentario = Comentario(
            solicitacao_id=solicitacao.id,
            autor=perfil,
            comentario=f"Upload de arte v{versao_atual}: {comentario}"
        )
        db.add(novo_comentario)
    else:
        novo_comentario = Comentario(
            solicitacao_id=solicitacao.id,
            autor=perfil,
            comentario=f"Arte v{versao_atual} enviada por {perfil}"
        )
        db.add(novo_comentario)
    
    db.commit()
    db.refresh(solicitacao)
    
    return {
        "message": f"Arte v{versao_atual} enviada com sucesso!",
        "protocolo": protocolo,
        "versao": versao_atual,
        "filename": filename,
        "status": solicitacao.status
    }

@app.get("/solicitacoes/{protocolo}/arquivos")
def listar_arquivos(protocolo: str, db: Session = Depends(get_db)):
    """Lista todas as versões de arte de uma solicitação"""
    solicitacao = db.query(Solicitacao).filter(Solicitacao.protocolo == protocolo).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    
    arquivos = db.query(Arquivo).filter(Arquivo.solicitacao_id == solicitacao.id).order_by(Arquivo.versao.desc()).all()
    
    return {
        "protocolo": protocolo,
        "arquivos": [
            {
                "id": a.id,
                "versao": a.versao,
                "nome": a.arquivo,
                "data": a.data_upload,
                "url": a.url or f"/uploads/{protocolo}/{a.arquivo}"
            } for a in arquivos
        ]
    }

@app.get("/uploads/{protocolo}/{filename}")
def download_arte(protocolo: str, filename: str, db: Session = Depends(get_db)):
    """Abre a arte. No Blob, redireciona para a URL publica; em teste, serve do /tmp."""
    from fastapi.responses import RedirectResponse
    arq = (db.query(Arquivo).join(Solicitacao)
           .filter(Solicitacao.protocolo == protocolo, Arquivo.arquivo == filename).first())
    if arq and arq.url and arq.url.startswith("http"):
        return RedirectResponse(arq.url)
    file_path = os.path.join(UPLOAD_DIR, protocolo, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    return FileResponse(file_path, filename=filename)

# Existing endpoints (cancelar, transicao, aprovar_arte) remain the same
@app.post("/solicitacoes/{protocolo}/cancelar")
def cancelar_solicitacao(protocolo: str, motivo: str = Form(None), db: Session = Depends(get_db)):
    """Cancelamento com validação de 24h"""
    solicitacao = db.query(Solicitacao).filter(Solicitacao.protocolo == protocolo).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    
    validar_cancelamento(solicitacao)
    
    solicitacao.status = "Cancelado"
    solicitacao.data_encerramento = datetime.utcnow()
    
    if motivo:
        comentario = Comentario(
            solicitacao_id=solicitacao.id,
            autor="Sistema/Solicitante",
            comentario=f"Cancelamento: {motivo}"
        )
        db.add(comentario)
    
    db.commit()
    db.refresh(solicitacao)
    
    return {"message": "Solicitação cancelada com sucesso.", "protocolo": protocolo}


@app.post("/solicitacoes/{protocolo}/transicao")
def transitar_status(
    protocolo: str, 
    novo_status: str = Form(...),
    comentario: str = Form(None),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Transição de status. O perfil vem do login, não de um campo manipulável."""
    perfil = user["perfil"]
    solicitacao = db.query(Solicitacao).filter(Solicitacao.protocolo == protocolo).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    
    validar_transicao_status(solicitacao, novo_status, perfil)
    
    solicitacao.status = novo_status
    
    if novo_status in ["Concluído", "Cancelado"]:
        solicitacao.data_encerramento = datetime.utcnow()
    
    if comentario:
        novo_comentario = Comentario(
            solicitacao_id=solicitacao.id,
            autor=perfil,
            comentario=comentario
        )
        db.add(novo_comentario)
    
    db.commit()
    db.refresh(solicitacao)
    
    return {
        "message": f"Status atualizado para {novo_status}",
        "protocolo": protocolo,
        "novo_status": novo_status
    }


@app.post("/solicitacoes/{protocolo}/aprovar_arte")
def aprovar_arte(
    protocolo: str,
    acao: str = Form(...),
    comentario: str = Form(None),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aprovação de arte. Perfil vem do login."""
    perfil = user["perfil"]
    solicitacao = db.query(Solicitacao).filter(Solicitacao.protocolo == protocolo).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    
    validar_aprovacao_arte(solicitacao, acao, perfil)
    
    if acao == "Aprovar":
        solicitacao.status = "Arte Aprovada"
    elif acao == "Solicitar Ajuste":
        solicitacao.status = "Ajuste Solicitado"
    
    if comentario:
        novo_comentario = Comentario(
            solicitacao_id=solicitacao.id,
            autor=perfil,
            comentario=f"Ação na arte: {acao} - {comentario}"
        )
        db.add(novo_comentario)
    
    db.commit()
    db.refresh(solicitacao)
    
    return {
        "message": f"Arte {acao.lower()} com sucesso.",
        "novo_status": solicitacao.status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)