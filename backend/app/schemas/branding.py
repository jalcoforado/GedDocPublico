from pydantic import BaseModel


class BrandingResponse(BaseModel):
    """Branding/white-label do tenant atual — público (não exige login).

    O frontend chama isso ANTES do login para customizar cor, logo, título.
    """
    slug: str
    nome: str
    cor_primaria: str | None = None
    # Tema do município (0131): com `cor_primaria`, o frontend deriva a paleta.
    cor_destaque: str | None = None
    cor_lateral: str | None = None
    logo_url: str | None = None
    # Tela de login (0129): marca própria e foto do painel esquerdo.
    logo_login_url: str | None = None
    imagem_login_url: str | None = None
    imagem_login_credito: str | None = None
