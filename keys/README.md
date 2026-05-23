# JWT Keys

Diretório com o par RSA usado quando `JWT_ALGORITHM=RS256` (Fase 9.3).

## Arquivos

- `jwt_private.pem` — chave privada usada para **assinar** tokens (Python emissor)
- `jwt_public.pem` — chave pública usada para **validar** tokens (Python + qualquer cliente externo)

Ambos são `.gitignore`-ados. Gere localmente:

```bash
docker run --rm -v $(pwd)/keys:/out aprimora-py-backend:latest python -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
open('/out/jwt_private.pem','wb').write(
    k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
)
open('/out/jwt_public.pem','wb').write(
    k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
)
"
```

## Coexistência HS256 ↔ RS256

- Validação aceita **ambos** os algoritmos
- Emissão usa o que está em `JWT_ALGORITHM` (default `HS256` — mantém interop com PHP)
- Para cortar a interop com PHP e migrar pra RS256: setar `JWT_ALGORITHM=RS256` no `docker-compose.yml` e recriar backend
- Em produção: rotacionar a chave gerando par novo e atualizando os PEMs
