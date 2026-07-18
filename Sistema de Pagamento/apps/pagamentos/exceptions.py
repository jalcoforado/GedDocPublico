class RegraDeNegocioError(Exception):
    """Base para violações de regra de negócio no fluxo de pagamento."""


class TransicaoInvalidaError(RegraDeNegocioError):
    pass


class DocumentacaoObrigatoriaError(RegraDeNegocioError):
    pass


class SegregacaoFuncoesError(RegraDeNegocioError):
    pass


class SaldoInsuficienteError(RegraDeNegocioError):
    pass


class AlcadaExcedidaError(RegraDeNegocioError):
    pass
