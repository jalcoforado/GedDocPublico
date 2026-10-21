import { PainelDeControle } from "@/components/protocolo/PainelDeControle";

/**
 * Porta do módulo Protocolo, como o Painel de Controle do SEI: é a raiz do
 * menu (`menuProtocolo.raiz`) e o primeiro item do grupo "Processos". O
 * conteúdo vive no componente para a página não exportar nada além do
 * default (guarda `guarda-export-de-pagina`).
 */
export default function PainelDoProtocoloPage() {
  return <PainelDeControle />;
}
