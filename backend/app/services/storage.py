"""Abstração do armazenamento físico de anexos (backlog §3.1 "Object storage").

Hoje o padrão é — e continua sendo — o filesystem local por tenant
(`{tenants_storage_root}/{slug}/anexos/`), com o fallback de leitura para o
path legado (`uploads_dir`) que `config.resolve_anexo_path` já fazia.
`LocalFSStorage` só embrulha esse comportamento; nada muda com
`STORAGE_BACKEND` vazio ou `local`.

`S3Storage` é **experimental e desligado por padrão**: nunca foi exercitado
contra um bucket real, e ainda há consumidores que pressupõem arquivo local
(ver a docstring da classe). Não ligar em ambiente nenhum antes de fechar
esses pontos.

**O storage não autoriza nada.** Ele recebe `tenant_slug` + `e_doc` e devolve
bytes. Quem serve conteúdo de anexo tem de passar ANTES por
`anexos.get_anexo_path_autorizado` (sigilo LAI + tenant), que é quem decide se
o chamador pode saber que o anexo existe — `tests/test_guarda_anexo_sigiloso.py`.
"""
from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator, Protocol

from ..config import get_settings, resolve_anexo_path, tenant_anexos_dir

_CHUNK = 65536


class StorageBackend(Protocol):
    async def put(self, tenant_slug: str, e_doc: str, content: bytes) -> None:
        """Salva o conteúdo no storage."""
        ...

    def get_stream(self, tenant_slug: str, e_doc: str) -> AsyncIterator[bytes]:
        """Lê o arquivo em pedaços (para StreamingResponse e hashes).

        Declarado sem `async`: as implementações são geradores assíncronos, e
        chamá-los devolve o iterador direto, sem `await`."""
        ...

    async def get_bytes(self, tenant_slug: str, e_doc: str) -> bytes:
        """Lê o arquivo inteiro para a memória. Levanta `FileNotFoundError`."""
        ...

    async def exists(self, tenant_slug: str, e_doc: str) -> bool:
        """Verifica se o arquivo existe."""
        ...

    async def delete(self, tenant_slug: str, e_doc: str) -> None:
        """Remove o arquivo físico (se existir)."""
        ...

    async def get_local_path_if_possible(self, tenant_slug: str, e_doc: str) -> Path | None:
        """Caminho físico, SE o storage for local (permite `FileResponse`).
        Storage remoto devolve None."""
        ...


class LocalFSStorage:
    """Filesystem local por tenant, com fallback de leitura para o legado.

    Comportamento idêntico ao anterior à abstração: grava em
    `tenant_anexos_dir(slug)` e lê via `resolve_anexo_path`."""

    def _resolve(self, tenant_slug: str, e_doc: str) -> Path | None:
        return resolve_anexo_path(tenant_slug, e_doc)

    async def put(self, tenant_slug: str, e_doc: str, content: bytes) -> None:
        (tenant_anexos_dir(tenant_slug) / e_doc).write_bytes(content)

    async def get_stream(self, tenant_slug: str, e_doc: str) -> AsyncIterator[bytes]:
        path = self._resolve(tenant_slug, e_doc)
        if path is None:
            raise FileNotFoundError(f"Arquivo não encontrado no storage: {e_doc}")
        # Leitura bloqueante, como era antes da abstração (hash_anexo lia
        # assim). Chunks de 64 KiB limitam o tempo de cada bloqueio.
        with open(path, "rb") as f:
            while chunk := f.read(_CHUNK):
                yield chunk

    async def get_bytes(self, tenant_slug: str, e_doc: str) -> bytes:
        path = self._resolve(tenant_slug, e_doc)
        if path is None:
            raise FileNotFoundError(f"Arquivo não encontrado no storage: {e_doc}")
        return path.read_bytes()

    async def exists(self, tenant_slug: str, e_doc: str) -> bool:
        return self._resolve(tenant_slug, e_doc) is not None

    async def delete(self, tenant_slug: str, e_doc: str) -> None:
        # Só o path do tenant: o diretório legado é compartilhado e não é
        # deste storage apagar nele.
        (tenant_anexos_dir(tenant_slug) / e_doc).unlink(missing_ok=True)

    async def get_local_path_if_possible(self, tenant_slug: str, e_doc: str) -> Path | None:
        return self._resolve(tenant_slug, e_doc)


class S3Storage:
    """S3 / MinIO via `aioboto3`. **EXPERIMENTAL — desligado por padrão.**

    Nunca foi testado contra bucket real; não há credencial em ambiente algum.
    `aioboto3` é dependência OPCIONAL (`pip install -e ".[s3]"`) e só é
    importado aqui dentro, de forma tardia — com `STORAGE_BACKEND=local` a
    aplicação não precisa dele instalado.

    Pendências conhecidas antes de ligar:
    - consumidores que ainda pressupõem arquivo local e ignoram a abstração:
      downloads de pagamentos (`pagamentos_anexos.get_anexo_debito_path_autorizado`,
      `pagamentos_lotes.get_comprovante_path_autorizado` → `FileResponse(path)`),
      o tamanho em `routers/pagamentos_debitos._anexos_debito_out` e a task
      `tasks/carimbar_anexos.py`;
    - não há fallback para anexos legados (`uploads_dir`): eles precisam ser
      migrados para o bucket antes;
    - o cache de carimbados e os jobs continuam no disco local.
    """

    def _client(self):
        import aioboto3  # import tardio: dependência opcional

        s = get_settings()
        session = aioboto3.Session(
            aws_access_key_id=s.s3_access_key or None,
            aws_secret_access_key=s.s3_secret_key or None,
            region_name=s.s3_region,
        )
        return session.client("s3", endpoint_url=s.s3_endpoint_url or None)

    @staticmethod
    def _key(tenant_slug: str, e_doc: str) -> str:
        return f"tenants/{tenant_slug}/anexos/{e_doc}"

    @staticmethod
    def _nao_existe(e) -> bool:
        return e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404")

    async def put(self, tenant_slug: str, e_doc: str, content: bytes) -> None:
        s = get_settings()
        async with self._client() as client:
            await client.put_object(
                Bucket=s.s3_bucket, Key=self._key(tenant_slug, e_doc), Body=content
            )

    async def get_stream(self, tenant_slug: str, e_doc: str) -> AsyncIterator[bytes]:
        import botocore.exceptions

        s = get_settings()
        async with self._client() as client:
            try:
                response = await client.get_object(
                    Bucket=s.s3_bucket, Key=self._key(tenant_slug, e_doc)
                )
            except botocore.exceptions.ClientError as e:
                if self._nao_existe(e):
                    raise FileNotFoundError(f"Arquivo não encontrado no storage: {e_doc}")
                raise
            async for chunk in response["Body"].iter_chunks(_CHUNK):
                yield chunk

    async def get_bytes(self, tenant_slug: str, e_doc: str) -> bytes:
        import botocore.exceptions

        s = get_settings()
        async with self._client() as client:
            try:
                response = await client.get_object(
                    Bucket=s.s3_bucket, Key=self._key(tenant_slug, e_doc)
                )
            except botocore.exceptions.ClientError as e:
                if self._nao_existe(e):
                    raise FileNotFoundError(f"Arquivo não encontrado no storage: {e_doc}")
                raise
            return await response["Body"].read()

    async def exists(self, tenant_slug: str, e_doc: str) -> bool:
        import botocore.exceptions

        s = get_settings()
        async with self._client() as client:
            try:
                await client.head_object(Bucket=s.s3_bucket, Key=self._key(tenant_slug, e_doc))
                return True
            except botocore.exceptions.ClientError as e:
                if self._nao_existe(e):
                    return False
                raise

    async def delete(self, tenant_slug: str, e_doc: str) -> None:
        s = get_settings()
        async with self._client() as client:
            await client.delete_object(Bucket=s.s3_bucket, Key=self._key(tenant_slug, e_doc))

    async def get_local_path_if_possible(self, tenant_slug: str, e_doc: str) -> Path | None:
        return None


def obter_storage() -> StorageBackend:
    """Backend configurado em `STORAGE_BACKEND` (`local` por padrão)."""
    if get_settings().storage_backend == "s3":
        return S3Storage()
    return LocalFSStorage()
