import asyncio
from pyhanko.sign import signers

class TestSigner(signers.Signer):
    def __init__(self):
        super().__init__()

    async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run=False) -> bytes:
        print("Data length:", len(data))
        return b"fake_cms"

print("Dir of Signer:", dir(signers.Signer))
