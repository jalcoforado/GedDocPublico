/**
 * Piso de tamanho para senha escolhida por pessoa.
 *
 * **Cópia de conveniência, não a regra.** A regra é `SENHA_MINIMA` em
 * `backend/app/auth/password.py`; aqui é só para o formulário avisar antes de
 * o usuário apertar o botão. A barreira real é o 422 do backend — nenhum teste
 * de frontend deve afirmar que esta constante protege coisa alguma.
 *
 * Existe como arquivo próprio porque o número estava escrito à mão em dois
 * componentes com valores DIFERENTES (4 no cadastro de cidadão, 6 no card de
 * troca), e a divergência entre eles espelhava a mesma divergência do backend.
 *
 * Divergir do backend agora produz um sintoma benigno e visível: ou o
 * formulário barra o que o servidor aceitaria, ou deixa passar o que o servidor
 * recusa com 422. Nos dois casos aparece na tela — não é falha silenciosa.
 */
export const SENHA_MINIMA = 8;
