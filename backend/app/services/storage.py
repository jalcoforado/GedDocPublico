from typing import AsyncIterator, Protocol
from pathlib import Path
from ..config import get_settings, tenant_anexos_dir

class StorageBackend(Protocol):
    async def put(self, tenant_slug: str, e_doc: str, content: bytes) -> None:
        """Salva o conteúdo no storage."""
        ...
        
    async def get_stream(self, tenant_slug: str, e_doc: str) -> AsyncIterator[bytes]:
        """Lê o arquivo em pedaços (para StreamingResponse e hashes)."""
        ...
        
    async def get_bytes(self, tenant_slug: str, e_doc: str) -> bytes:
        """Lê o arquivo inteiro para a memória (uso interno se necessário)."""
        ...
        
    async def exists(self, tenant_slug: str, e_doc: str) -> bool:
        """Verifica se o arquivo existe."""
        ...
        
    async def delete(self, tenant_slug: str, e_doc: str) -> None:
        """Remove o arquivo físico (se aplicável/suportado)."""
        ...
        
    async def get_local_path_if_possible(self, tenant_slug: str, e_doc: str) -> Path | None:
        """Retorna o caminho físico SE for storage local. Útil para otimizações (FileResponse, Carimbador).
        Se for S3 no futuro, retornará None."""
        ...


class LocalFSStorage:
    def _resolve(self, tenant_slug: str, e_doc: str) -> Path | None:
        from ..config import resolve_anexo_path
        return resolve_anexo_path(tenant_slug, e_doc)

    async def put(self, tenant_slug: str, e_doc: str, content: bytes) -> None:
        p = tenant_anexos_dir(tenant_slug) / e_doc
        p.write_bytes(content)

    async def get_stream(self, tenant_slug: str, e_doc: str) -> AsyncIterator[bytes]:
        path = self._resolve(tenant_slug, e_doc)
        if not path:
            raise FileNotFoundError(f"Arquivo não encontrado no storage: {e_doc}")
        # Lendo de forma bloqueante no thread do event loop para o LocalFS.
        # Numa implementação madura assíncrona usar aiofiles ou rodar em threadpool.
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    async def get_bytes(self, tenant_slug: str, e_doc: str) -> bytes:
        path = self._resolve(tenant_slug, e_doc)
        if not path:
            raise FileNotFoundError(f"Arquivo não encontrado no storage: {e_doc}")
        return path.read_bytes()

    async def exists(self, tenant_slug: str, e_doc: str) -> bool:
        return self._resolve(tenant_slug, e_doc) is not None

    async def delete(self, tenant_slug: str, e_doc: str) -> None:
        path = self._resolve(tenant_slug, e_doc)
        if path and path.exists():
            path.unlink()

    async def get_local_path_if_possible(self, tenant_slug: str, e_doc: str) -> Path | None:
        return self._resolve(tenant_slug, e_doc)


class S3Storage:
    def _client(self):
        import aioboto3
        s = get_settings()
        session = aioboto3.Session(
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
        )
        return session.client("s3", endpoint_url=s.s3_endpoint_url if s.s3_endpoint_url else None)

    def _key(self, tenant_slug: str, e_doc: str) -> str:
        return f"tenants/{tenant_slug}/anexos/{e_doc}"

    async def put(self, tenant_slug: str, e_doc: str, content: bytes) -> None:
        s = get_settings()
        async with self._client() as client:
            await client.put_object(
                Bucket=s.s3_bucket,
                Key=self._key(tenant_slug, e_doc),
                Body=content,
            )

    async def get_stream(self, tenant_slug: str, e_doc: str) -> AsyncIterator[bytes]:
        import botocore.exceptions
        s = get_settings()
        async with self._client() as client:
            try:
                response = await client.get_object(
                    Bucket=s.s3_bucket,
                    Key=self._key(tenant_slug, e_doc),
                )
                async for chunk in response['Body'].iter_chunks(65536):
                    yield chunk
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise FileNotFoundError(f"Arquivo não encontrado no S3: {e_doc}")
                raise

    async def get_bytes(self, tenant_slug: str, e_doc: str) -> bytes:
        import botocore.exceptions
        s = get_settings()
        async with self._client() as client:
            try:
                response = await client.get_object(
                    Bucket=s.s3_bucket,
                    Key=self._key(tenant_slug, e_doc),
                )
                return await response['Body'].read()
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise FileNotFoundError(f"Arquivo não encontrado no S3: {e_doc}")
                raise

    async def exists(self, tenant_slug: str, e_doc: str) -> bool:
        import botocore.exceptions
        s = get_settings()
        async with self._client() as client:
            try:
                await client.head_object(
                    Bucket=s.s3_bucket,
                    Key=self._key(tenant_slug, e_doc),
                )
                return True
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    return False
                raise

    async def delete(self, tenant_slug: str, e_doc: str) -> None:
        s = get_settings()
        async with self._client() as client:
            await client.delete_object(
                Bucket=s.s3_bucket,
                Key=self._key(tenant_slug, e_doc),
            )

    async def get_local_path_if_possible(self, tenant_slug: str, e_doc: str) -> Path | None:
        return None


def obter_storage() -> StorageBackend:
    s = get_settings()
    if s.storage_backend.lower() == "s3":
        return S3Storage()
    return LocalFSStorage()
