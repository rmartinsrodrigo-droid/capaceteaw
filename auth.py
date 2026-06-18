"""
Autenticacao por perfil adaptada para serverless (Vercel).

Diferenca chave do servidor tradicional: o codigo OTP NAO pode ficar na memoria,
porque cada requisicao no Vercel pode cair numa instancia diferente. Entao o OTP
fica gravado no banco (tabela otp_codes), assim "pedir codigo" e "validar codigo"
funcionam mesmo em instancias separadas.
"""
import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, OtpCode

SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao-aw-2026")
signer = URLSafeTimedSerializer(SECRET_KEY, salt="capaceteaw-session")
TOKEN_VALIDADE_SEGUNDOS = 60 * 60 * 8  # 8 horas

bearer = HTTPBearer(auto_error=False)


def generate_otp(email: str, db: Session) -> str:
    code = str(random.randint(100000, 999999))
    db.query(OtpCode).filter(OtpCode.email == email).delete()
    db.add(OtpCode(email=email, code=code, expires=datetime.utcnow() + timedelta(minutes=10)))
    db.commit()
    return code


def send_otp_email(email: str, otp: str) -> bool:
    host = os.getenv("SMTP_HOST")
    corpo = f"Seu codigo de acesso ao Capacete AW e: {otp}\n\nValido por 10 minutos."
    if not host:
        print(f"[MODO DEV - sem SMTP] OTP para {email}: {otp}")
        return True
    msg = MIMEText(corpo)
    msg["Subject"] = "Capacete AW - Codigo de acesso"
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "nao-responda@athiewohnrath.com.br"))
    msg["To"] = email
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[ERRO SMTP] {e} - OTP para {email}: {otp}")
        return False


def verify_otp_and_login(email: str, otp: str, db: Session) -> dict:
    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.ativo == "Ativo").first()
    if not usuario:
        raise HTTPException(status_code=403, detail="E-mail nao autorizado. Fale com o Marketing.")
    registro = db.query(OtpCode).filter(OtpCode.email == email).order_by(OtpCode.id.desc()).first()
    if not registro:
        raise HTTPException(status_code=400, detail="Codigo nao solicitado.")
    if datetime.utcnow() > registro.expires:
        raise HTTPException(status_code=400, detail="Codigo expirado. Solicite outro.")
    if registro.code != otp:
        raise HTTPException(status_code=400, detail="Codigo invalido.")
    db.query(OtpCode).filter(OtpCode.email == email).delete()
    db.commit()
    token = signer.dumps({"email": email, "perfil": usuario.perfil, "nome": usuario.nome})
    return {"token": token, "perfil": usuario.perfil, "nome": usuario.nome, "email": email}


def get_current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not cred:
        raise HTTPException(status_code=401, detail="Faca login para continuar.")
    try:
        dados = signer.loads(cred.credentials, max_age=TOKEN_VALIDADE_SEGUNDOS)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Sessao expirada. Entre novamente.")
    except BadSignature:
        raise HTTPException(status_code=401, detail="Sessao invalida.")
    return dados


def exigir_perfil(*perfis_permitidos):
    def _verifica(user: dict = Depends(get_current_user)) -> dict:
        if user["perfil"] not in perfis_permitidos:
            raise HTTPException(status_code=403,
                detail=f"Seu perfil ({user['perfil']}) nao tem permissao para esta acao.")
        return user
    return _verifica
