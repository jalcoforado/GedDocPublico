import { NextResponse, type NextRequest } from "next/server";

import { DESTINO_PADRAO, destinoSeguro } from "@/lib/destino-login";

// `/brand` são os logos de tenant (`tenant.logo_url`), exibidos já na tela de login.
// `/validar` é a conferência pública de assinatura: o link `/validar/<codigo>`
// vai impresso no documento assinado, para QUALQUER pessoa abrir. Ficou fora
// desta lista e redirecionava para o login — o terceiro que recebia o documento
// não tinha como conferi-lo. A API que a página consome já era pública.
const PUBLIC_PATHS = ["/login", "/cidadao", "/validar", "/_next", "/favicon.ico", "/brand"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const token = req.cookies.get("aprimora_token")?.value;
  if (!token) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    // Preserva o destino (F3, Tarefa 1). Antes o clone trocava só o pathname e
    // a `search` do destino original vinha junto por acidente, poluindo a URL
    // do login com filtros da tela que ninguém chegou a ver; agora a query é
    // reconstruída do zero e carrega só o `next`.
    //
    // `destinoSeguro` roda também AQUI, na escrita, e não só na leitura: o que
    // não é destino válido não deve nem aparecer na barra de endereços. Um
    // `?next=https://evil.example` visível já é metade do golpe, mesmo que o
    // login depois o recuse.
    const destino = destinoSeguro(req.nextUrl.pathname + req.nextUrl.search);
    url.search = destino === DESTINO_PADRAO ? "" : `?next=${encodeURIComponent(destino)}`;
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
