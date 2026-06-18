"""
Armazenamento de arquivos de arte adaptado pro Vercel.

No Vercel o disco e somente-leitura (menos /tmp, que e apagado). Entao os arquivos
vao pro Vercel Blob quando o token BLOB_READ_WRITE_TOKEN existir (a plataforma cria
esse token quando voce adiciona um Blob Store). Sem token, grava em /tmp so pra
nao quebrar em teste local (nao persiste).
"""
import os
import httpx

BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
TMP_DIR = "/tmp/uploads"


def salvar_arquivo(pathname: str, conteudo: bytes, content_type: str) -> dict:
    """Salva e devolve {'url': ..., 'persistente': bool}."""
    if BLOB_TOKEN:
        resp = httpx.put(
            f"https://blob.vercel-storage.com/{pathname}",
            headers={
                "authorization": f"Bearer {BLOB_TOKEN}",
                "x-content-type": content_type,
                "x-add-random-suffix": "0",
            },
            content=conteudo,
            timeout=30,
        )
        resp.raise_for_status()
        return {"url": resp.json()["url"], "persistente": True}

    # Fallback local (teste): /tmp
    destino = os.path.join(TMP_DIR, pathname)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(conteudo)
    return {"url": f"/uploads-local/{pathname}", "persistente": False}
