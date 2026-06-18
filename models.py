from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Solicitacao(Base):
    __tablename__ = 'solicitacoes'
    id = Column(Integer, primary_key=True, index=True)
    protocolo = Column(String(50), unique=True, index=True)
    data_abertura = Column(DateTime, default=func.now())
    solicitante = Column(String(100))
    email = Column(String(100))
    cliente = Column(String(100))
    site_cliente = Column(String(200))
    parceiro = Column(String(100))
    site_parceiro = Column(String(200))
    quantidade = Column(Integer)
    projeto = Column(String(100))
    cidade = Column(String(100))
    estado = Column(String(2))
    observacoes = Column(Text)
    status = Column(String(50), default="Solicitação Recebida")
    fornecedor_id = Column(Integer, ForeignKey('fornecedores.id'), nullable=True)
    data_encerramento = Column(DateTime, nullable=True)

    colaboradores = relationship("Colaborador", back_populates="solicitacao")
    arquivos = relationship("Arquivo", back_populates="solicitacao")
    comentarios = relationship("Comentario", back_populates="solicitacao")

class Colaborador(Base):
    __tablename__ = 'colaboradores'
    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey('solicitacoes.id'))
    nome = Column(String(100))
    solicitacao = relationship("Solicitacao", back_populates="colaboradores")

class Arquivo(Base):
    __tablename__ = 'arquivos'
    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey('solicitacoes.id'))
    arquivo = Column(String(255))
    versao = Column(Integer, default=1)
    data_upload = Column(DateTime, default=func.now())
    url = Column(String(500), nullable=True)
    solicitacao = relationship("Solicitacao", back_populates="arquivos")

class Comentario(Base):
    __tablename__ = 'comentarios'
    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey('solicitacoes.id'))
    autor = Column(String(100))
    comentario = Column(Text)
    data = Column(DateTime, default=func.now())
    solicitacao = relationship("Solicitacao", back_populates="comentarios")

class Fornecedor(Base):
    __tablename__ = 'fornecedores'
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100))
    email = Column(String(100))
    status = Column(String(20), default="Ativo")

class Logo(Base):
    __tablename__ = 'logos'
    id = Column(Integer, primary_key=True, index=True)
    empresa = Column(String(100))
    site = Column(String(200))
    logo = Column(String(255))
    homologado = Column(DateTime, nullable=True)
class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    perfil = Column(String(30))   # Marketing | Compras | Fornecedor | Solicitante
    ativo = Column(String(10), default="Ativo")

class OtpCode(Base):
    __tablename__ = 'otp_codes'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), index=True)
    code = Column(String(6))
    expires = Column(DateTime)
