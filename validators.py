from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Solicitacao
from fastapi import HTTPException

def validar_cancelamento(solicitacao: Solicitacao):
    """Valida se solicitação pode ser cancelada (até 24h)"""
    if not solicitacao.data_abertura:
        return
    
    limite = solicitacao.data_abertura + timedelta(hours=24)
    if datetime.utcnow() > limite:
        raise HTTPException(
            status_code=400, 
            detail="Cancelamento permitido apenas nas primeiras 24 horas após a abertura."
        )

def validar_transicao_status(solicitacao: Solicitacao, novo_status: str, perfil: str):
    """Valida transições de status conforme regras de negócio"""
    status_atual = solicitacao.status
    
    # Mapa de transições permitidas conforme PRD Seção 7 e 8
    transicoes_permitidas = {
        "Solicitação Recebida": ["Aguardando Aprovação Marketing"],
        "Aguardando Aprovação Marketing": ["Aguardando Aprovação Compras", "Cancelado"],
        "Aguardando Aprovação Compras": ["Aguardando Design", "Cancelado"],
        "Aguardando Design": ["Fornecedor Atribuído"],
        "Fornecedor Atribuído": ["Em Desenvolvimento de Arte"],
        "Em Desenvolvimento de Arte": ["Arte Disponível para Aprovação"],
        "Arte Disponível para Aprovação": ["Ajuste Solicitado", "Arte Aprovada"],
        "Ajuste Solicitado": ["Em Desenvolvimento de Arte"],
        "Arte Aprovada": ["Aguardando Liberação Produção"],
        "Aguardando Liberação Produção": ["Em Produção"],
        "Em Produção": ["Produção Finalizada"],
        "Produção Finalizada": ["Em Transporte"],
        "Em Transporte": ["Disponível para Retirada"],
        "Disponível para Retirada": ["Concluído"],
        # Estados finais
        "Cancelado": [],
        "Concluído": [],
    }
    
    if novo_status not in transicoes_permitidas.get(status_atual, []):
        raise HTTPException(
            status_code=400,
            detail=f"Transição inválida de '{status_atual}' para '{novo_status}'. Verifique o fluxo operacional."
        )
    
    # Regras específicas por perfil
    if perfil == "Marketing" and novo_status not in ["Aguardando Aprovação Compras", "Ajuste Solicitado", "Arte Aprovada"]:
        # Allow for now - expand later
        pass
    
    if perfil == "Solicitante" and novo_status not in ["Ajuste Solicitado", "Arte Aprovada"]:
        raise HTTPException(status_code=403, detail="Solicitante só pode aprovar ou solicitar ajuste na arte.")
    
    return True

def validar_aprovacao_arte(solicitacao: Solicitacao, acao: str, perfil: str):
    """Valida ações de aprovação de arte"""
    if solicitacao.status != "Arte Disponível para Aprovação":
        raise HTTPException(
            status_code=400, 
            detail="Aprovação de arte só disponível no status correto."
        )
    
    if acao not in ["Aprovar", "Solicitar Ajuste"]:
        raise HTTPException(status_code=400, detail="Ação inválida.")
    
    return True