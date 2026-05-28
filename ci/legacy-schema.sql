--
-- PostgreSQL database dump
--


-- Dumped from database version 13.23 (Debian 13.23-1.pgdg13+1)
-- Dumped by pg_dump version 13.23 (Debian 13.23-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: aprimora_py; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA aprimora_py;


--
-- Name: protocolos; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA protocolos;


--
-- Name: utils; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA utils;


--
-- Name: origem; Type: TYPE; Schema: utils; Owner: -
--

CREATE TYPE utils.origem AS ENUM (
    'acl',
    'agendasol',
    'extra'
);


--
-- Name: tipo_pessoa; Type: TYPE; Schema: utils; Owner: -
--

CREATE TYPE utils.tipo_pessoa AS ENUM (
    'f',
    'j'
);


--
-- Name: copia_id_ordem_anexo_processo_func(); Type: FUNCTION; Schema: protocolos; Owner: -
--

CREATE FUNCTION protocolos.copia_id_ordem_anexo_processo_func() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'protocolos'
    AS $$
	BEGIN
		NEW.ordem := NEW.id;
		RETURN NEW;
	END;
$$;


--
-- Name: func_aud_empenho_processo(); Type: FUNCTION; Schema: protocolos; Owner: -
--

CREATE FUNCTION protocolos.func_aud_empenho_processo() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: id_processo
	IF operacao IN ('I', 'D') OR antigo.id_processo <> novo.id_processo THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('empenho_processo', novo.id, 'id_processo', antigo.id_processo, novo.id_processo, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_empenho
	IF operacao IN ('I', 'D') OR antigo.id_empenho <> novo.id_empenho THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('empenho_processo', novo.id, 'id_empenho', antigo.id_empenho, novo.id_empenho, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: ctrcod
	IF operacao IN ('I', 'D') OR antigo.ctrcod <> novo.ctrcod THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('empenho_processo', novo.id, 'ctrcod', antigo.ctrcod, novo.ctrcod, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: liccod
	IF operacao IN ('I', 'D') OR antigo.liccod <> novo.liccod THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('empenho_processo', novo.id, 'liccod', antigo.liccod, novo.liccod, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: data_criacao
	IF operacao IN ('I', 'D') OR antigo.data_criacao <> novo.data_criacao THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('empenho_processo', novo.id, 'data_criacao', antigo.data_criacao, novo.data_criacao, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR antigo.excluido <> novo.excluido THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('empenho_processo', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario
	IF operacao IN ('I', 'D') OR antigo.id_usuario <> novo.id_usuario THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('empenho_processo', novo.id, 'id_usuario', antigo.id_usuario, novo.id_usuario, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_liquidacao_despesas_processo(); Type: FUNCTION; Schema: protocolos; Owner: -
--

CREATE FUNCTION protocolos.func_aud_liquidacao_despesas_processo() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: id_processo
	IF operacao IN ('I', 'D') OR antigo.id_processo <> novo.id_processo THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('liquidacao_despesas_processo', novo.id, 'id_processo', antigo.id_processo, novo.id_processo, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_feempliq
	IF operacao IN ('I', 'D') OR antigo.id_feempliq <> novo.id_feempliq THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('liquidacao_despesas_processo', novo.id, 'id_feempliq', antigo.id_feempliq, novo.id_feempliq, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: data_criacao
	IF operacao IN ('I', 'D') OR antigo.data_criacao <> novo.data_criacao THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('liquidacao_despesas_processo', novo.id, 'data_criacao', antigo.data_criacao, novo.data_criacao, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR antigo.excluido <> novo.excluido THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('liquidacao_despesas_processo', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario
	IF operacao IN ('I', 'D') OR antigo.id_usuario <> novo.id_usuario THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('liquidacao_despesas_processo', novo.id, 'id_usuario', antigo.id_usuario, novo.id_usuario, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_solicitacao_pagamento_processo(); Type: FUNCTION; Schema: protocolos; Owner: -
--

CREATE FUNCTION protocolos.func_aud_solicitacao_pagamento_processo() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: id_processo
	IF operacao IN ('I', 'D') OR antigo.id_processo <> novo.id_processo THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('solicitacao_pagamento_processo', novo.id, 'id_processo', antigo.id_processo, novo.id_processo, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_solicitacao_pagamento
	IF operacao IN ('I', 'D') OR antigo.id_solicitacao_pagamento <> novo.id_solicitacao_pagamento THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('solicitacao_pagamento_processo', novo.id, 'id_solicitacao_pagamento', antigo.id_solicitacao_pagamento, novo.id_solicitacao_pagamento, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: data_criacao
	IF operacao IN ('I', 'D') OR antigo.data_criacao <> novo.data_criacao THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('solicitacao_pagamento_processo', novo.id, 'data_criacao', antigo.data_criacao, novo.data_criacao, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR antigo.excluido <> novo.excluido THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('solicitacao_pagamento_processo', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario
	IF operacao IN ('I', 'D') OR antigo.id_usuario <> novo.id_usuario THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('solicitacao_pagamento_processo', novo.id, 'id_usuario', antigo.id_usuario, novo.id_usuario, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: tipo_pagamento
	IF operacao IN ('I', 'D') OR antigo.tipo_pagamento <> novo.tipo_pagamento THEN
		INSERT INTO protocolos.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('solicitacao_pagamento_processo', novo.id, 'tipo_pagamento', antigo.tipo_pagamento, novo.tipo_pagamento, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: gera_fonte_auditoria(character varying, character varying, boolean); Type: FUNCTION; Schema: protocolos; Owner: -
--

CREATE FUNCTION protocolos.gera_fonte_auditoria(schema character varying, tabela character varying, executar boolean) RETURNS text
    LANGUAGE plpgsql
    AS $_$
DECLARE
	nome VARCHAR(128);
	saida 				text;
	coluna 				text;
	tuplas		 		text;
	tipo_campo			text;
	campo_new_cast		text;
	campo_old_cast		text;
	retornoSelect		record;
BEGIN
	nome := 'aud_' || tabela;
	tuplas := '';
	campo_new_cast := '';
	campo_old_cast := '';

	FOR retornoSelect in SELECT column_name, data_type FROM information_schema.Columns WHERE table_schema = schema AND table_name = tabela AND column_name != 'id' LOOP
		coluna := retornoSelect.column_name;
		tipo_campo := retornoSelect.data_type;

		campo_new_cast := '';
		campo_old_cast := '';
		
		IF(tipo_campo = 'json') THEN
			campo_new_cast := '::TEXT';
			campo_old_cast := '::TEXT';
		END IF;
		
		tuplas := tuplas || e'\n	-- Campo: ' || coluna;
		tuplas := tuplas || e'\n	IF operacao IN (''I'', ''D'') OR antigo.' || coluna || campo_new_cast || ' <> novo.' || coluna || campo_new_cast || ' THEN';
		tuplas := tuplas || e'\n		INSERT INTO ' || schema || '.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ';
		tuplas := tuplas || '(''' || tabela || ''', novo.id, ''' || coluna || ''', antigo.' || coluna || campo_old_cast || ', novo.' || coluna || campo_new_cast || ', NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());';
		tuplas := tuplas || e'\n	END IF;\n';
	END LOOP;

	saida 	:= 'CREATE OR REPLACE FUNCTION ' || schema || '.func_' || nome || '()'
		|| e'\n RETURNS trigger AS $aud_trigger$'
		|| e'\n DECLARE'
		|| e'\n	operacao varchar(2);'
		|| e'\n	antigo record;'
		|| e'\n	novo record;'
		|| e'\n BEGIN'
		|| e'\n'
		|| e'\n	IF (TG_OP = ''INSERT'') THEN'
		|| e'\n		operacao := ''I''; '
		|| e'\n		antigo := new; '
		|| e'\n		novo := new; '
		|| e'\n	ELSEIF (TG_OP = ''UPDATE'' AND old.excluido <> new.excluido AND new.excluido = true) THEN'
		|| e'\n		operacao := ''LE''; '
		|| e'\n		antigo := old; '
		|| e'\n		novo := new; '
		|| e'\n	ELSEIF (TG_OP = ''UPDATE'') THEN'
		|| e'\n		operacao := ''U''; '
		|| e'\n		antigo := old; '
		|| e'\n		novo := new; '
		|| e'\n	ELSEIF (TG_OP = ''DELETE'') THEN'
		|| e'\n		operacao := ''D''; '
		|| e'\n		antigo := old; '
		|| e'\n		novo := old; '
		|| e'\n	END IF;'
		|| e'\n'
		|| tuplas
		|| e'\n'
		|| e'\n RETURN NEW;'
 		|| e'\nEND; \n' || e'$aud_trigger$ LANGUAGE plpgsql;'
		|| e'\n\n'
		|| e'DROP TRIGGER IF EXISTS trigger_' || nome || ' ON ' || schema || '.' || tabela || ';'
		|| e'\nCREATE TRIGGER trigger_' || nome
		|| e'\nAFTER INSERT OR UPDATE OR DELETE ON ' || schema || '.' || tabela
		|| e'\nFOR EACH ROW'
		|| e'\nEXECUTE PROCEDURE ' || schema || '.func_' || nome || '();';

	raise info e'\n+-+-+-+-+-TRIGGER % -+-+-+-+-+\n\n%\n\n+-+-+-+-+-TRIGGER % -+-+-+-+-+', schema||'.'||nome, saida, schema||'.'||nome;

	IF(executar = TRUE) THEN
		EXECUTE saida;
	END IF;

	return saida;
END
$_$;


--
-- Name: gerar_numero_processo_string(); Type: FUNCTION; Schema: protocolos; Owner: -
--

CREATE FUNCTION protocolos.gerar_numero_processo_string() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
	numero_processo varchar(50);
	zeros varchar(6);
	tamanho_string  integer;
	diferenca  integer;
begin
	numero_processo := nextval('protocolos.numero_processo')::text;
	tamanho_string := length(numero_processo);
	diferenca := 6 - tamanho_string;
	zeros := '';

	if diferenca > 1 then
		for i in 1..diferenca loop
			zeros := concat(zeros, '0');
		end loop;
	end if;

  	return (select concat('P', zeros, numero_processo, '/', extract('Year' From now())));
end;
$$;


--
-- Name: copia_sistemas_tipochamados(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.copia_sistemas_tipochamados() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
	valor_aleatorio integer;
BEGIN
	valor_aleatorio := floor(random() * 100) + 1;
    -- Verifica se existe um registro com o mesmo tipo ou permissao_acesso
	IF TG_OP = 'INSERT' THEN
		INSERT INTO sistema_chamados.tipo_chamado (tipo, permissao_acesso, id_setor)
        VALUES (new.sistema, 'chamadoPermissao_' || valor_aleatorio || '_' || new.app , 2);
	ELSEIF TG_OP = 'UPDATE' THEN 
		UPDATE sistema_chamados.tipo_chamado
		SET tipo = new.sistema--,-- permissao_acesso = 'chamadoPermissao_' || valor_aleatorio || '_' || new.app 
		WHERE old.sistema = tipo and id = (SELECT id FROM sistema_chamados.tipo_chamado where tipo = old.sistema ORDER BY id LIMIT 1);
	END IF;
    RETURN NULL;
END;
$$;


--
-- Name: fc_valida_cnpj(character varying, boolean); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.fc_valida_cnpj(p_cnpj character varying, p_fg_permite_nulo boolean DEFAULT false) RETURNS boolean
    LANGUAGE plpgsql
    AS $_$
declare
    
    v_cnpj_invalidos character varying[10] 
    default array['00000000000000', '11111111111111',
                  '22222222222222', '33333333333333',
                  '44444444444444', '55555555555555',
                  '66666666666666', '77777777777777',
                  '88888888888888', '99999999999999'];
                  
    v_cnpj_quebrado smallint[];
    
    c_posicao_dv1 constant smallint default 13;
    v_arranjo_dv1 smallint[12] default array[5,4,3,2,9,8,7,6,5,4,3,2];
    v_soma_dv1 smallint default 0;
    v_resto_dv1 double precision default 0;
    
    c_posicao_dv2 constant smallint default 14;
    v_arranjo_dv2 smallint[13] default array[6,5,4,3,2,9,8,7,6,5,4,3,2];
    v_soma_dv2 smallint default 0;
    v_resto_dv2 double precision default 0;
    
begin
    
    if p_fg_permite_nulo and nullif(p_cnpj, '') is null then
        return true;
    end if;
    
    if (not (p_cnpj ~* '^([0-9]{14})$' or 
             p_cnpj ~* '^([0-9]{2}\.[0-9]{3}\.[0-9]{3}\/[0-9]{4}\-[0-9]{2})$')) or
        p_cnpj = any (v_cnpj_invalidos) or
        p_cnpj is null
    then
        return false;    
    end if;
    
    v_cnpj_quebrado := regexp_split_to_array(
      regexp_replace(p_cnpj, '[^0-9]', '', 'g'), '');
        
    -- Realiza o calculo do primeiro digito
    for t in 1..12 loop
        v_soma_dv1 := v_soma_dv1 + 
      (v_cnpj_quebrado[t] * v_arranjo_dv1[t]);
    end loop;
    v_resto_dv1 := ((10 * v_soma_dv1) % 11) % 10;
       
    if (v_resto_dv1 != v_cnpj_quebrado[13]) 
    then
        return false;
    end if;
    
    -- Realiza o calculo do segundo digito    
    for t in 1..13 loop
        v_soma_dv2 := v_soma_dv2 + 
      (v_cnpj_quebrado[t] * v_arranjo_dv2[t]);
    end loop;
    v_resto_dv2 := ((10 * v_soma_dv2) % 11) % 10;
    
    return (v_resto_dv2 = v_cnpj_quebrado[c_posicao_dv2]);    
    
end;
$_$;


--
-- Name: fc_valida_cpf(character varying, boolean); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.fc_valida_cpf(p_cpf character varying, p_valida_nulo boolean DEFAULT false) RETURNS boolean
    LANGUAGE plpgsql
    AS $_$
declare
    
    v_cpf_invalidos character varying[10] 
    default array['00000000000', '11111111111',
                  '22222222222', '33333333333',
                  '44444444444', '55555555555',
                  '66666666666', '77777777777',
                  '88888888888', '99999999999'];
                  
    v_cpf_quebrado smallint[];
    
    c_posicao_dv1 constant smallint default 10;    
    v_arranjo_dv1 smallint[9] default array[10,9,8,7,6,5,4,3,2];
    v_soma_dv1 smallint default 0;
    v_resto_dv1 double precision default 0;
    
    c_posicao_dv2 constant smallint default 11;
    v_arranjo_dv2 smallint[10] default array[11,10,9,8,7,6,5,4,3,2];
    v_soma_dv2 smallint default 0;
    v_resto_dv2 double precision default 0;
    
begin
    if p_valida_nulo and nullif(p_cpf, '') is null then
        return true;
    end if;
    if (not (p_cpf ~* '^([0-9]{11})$' or 
             p_cpf ~* '^([0-9]{3}\.[0-9]{3}\.[0-9]{3}\-[0-9]{2})$')
        ) or
        p_cpf = any (v_cpf_invalidos) or
        p_cpf is null
    then
        return false;    
    end if;
    
v_cpf_quebrado := regexp_split_to_array(
                    regexp_replace(p_cpf, '[^0-9]', '', 'g'), '');
    -------------------------------- Digito Verificador 1
    for t in 1..9 loop
        v_soma_dv1 := v_soma_dv1 + 
                     (v_cpf_quebrado[t] * v_arranjo_dv1[t]);
    end loop;
    v_resto_dv1 := ((10 * v_soma_dv1) % 11) % 10;
        
    if (v_resto_dv1 != v_cpf_quebrado[c_posicao_dv1]) 
    then
        return false;
    end if;
    
    -------------------------------- Digito Verificador 2
    for t in 1..10 loop
        v_soma_dv2 := v_soma_dv2 + 
                     (v_cpf_quebrado[t] * v_arranjo_dv2[t]);
    end loop;
    v_resto_dv2 := ((10 * v_soma_dv2) % 11) % 10;
    
    return (v_resto_dv2 = v_cpf_quebrado[c_posicao_dv2]);    
end;
$_$;


--
-- Name: fn_trigger_delete_pessoa(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.fn_trigger_delete_pessoa() RETURNS trigger
    LANGUAGE plpgsql
    AS $$BEGIN
   
	IF new.excluido and OLD.validado and new.excluido<>old.excluido THEN
        RAISE EXCEPTION 'Erro ao excluir. Registro já validado.';
    END IF;
   
   return NEW;
  
END;$$;


--
-- Name: func_aud_ano_financeiro(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.func_aud_ano_financeiro() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: ano
	IF operacao IN ('I', 'D') OR coalesce(antigo.ano::varchar, '') <> coalesce(novo.ano::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'ano', antigo.ano, novo.ano, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: ativo
	IF operacao IN ('I', 'D') OR coalesce(antigo.ativo::varchar, '') <> coalesce(novo.ativo::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'ativo', antigo.ativo, novo.ativo, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: corrente
	IF operacao IN ('I', 'D') OR coalesce(antigo.corrente::varchar, '') <> coalesce(novo.corrente::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'corrente', antigo.corrente, novo.corrente, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: path_fb
	IF operacao IN ('I', 'D') OR coalesce(antigo.path_fb::varchar, '') <> coalesce(novo.path_fb::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'path_fb', antigo.path_fb, novo.path_fb, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: api_gestor
	IF operacao IN ('I', 'D') OR coalesce(antigo.api_gestor::varchar, '') <> coalesce(novo.api_gestor::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'api_gestor', antigo.api_gestor, novo.api_gestor, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: porta
	IF operacao IN ('I', 'D') OR coalesce(antigo.porta::varchar, '') <> coalesce(novo.porta::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'porta', antigo.porta, novo.porta, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario::varchar, '') <> coalesce(novo.id_usuario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'id_usuario', antigo.id_usuario, novo.id_usuario, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR coalesce(antigo.excluido::varchar, '') <> coalesce(novo.excluido::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('ano_financeiro', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_endereco(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.func_aud_endereco() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: id_cidade
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_cidade::varchar, '') <> coalesce(novo.id_cidade::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'id_cidade', antigo.id_cidade, novo.id_cidade, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_bairro
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_bairro::varchar, '') <> coalesce(novo.id_bairro::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'id_bairro', antigo.id_bairro, novo.id_bairro, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: rua
	IF operacao IN ('I', 'D') OR coalesce(antigo.rua::varchar, '') <> coalesce(novo.rua::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'rua', antigo.rua, novo.rua, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: numero
	IF operacao IN ('I', 'D') OR coalesce(antigo.numero::varchar, '') <> coalesce(novo.numero::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'numero', antigo.numero, novo.numero, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: complemento
	IF operacao IN ('I', 'D') OR coalesce(antigo.complemento::varchar, '') <> coalesce(novo.complemento::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'complemento', antigo.complemento, novo.complemento, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: latitude
	IF operacao IN ('I', 'D') OR coalesce(antigo.latitude::varchar, '') <> coalesce(novo.latitude::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'latitude', antigo.latitude, novo.latitude, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: longitude
	IF operacao IN ('I', 'D') OR coalesce(antigo.longitude::varchar, '') <> coalesce(novo.longitude::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'longitude', antigo.longitude, novo.longitude, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: dados_google_maps
	IF operacao IN ('I', 'D') OR coalesce(antigo.dados_google_maps::TEXT::varchar, '') <> coalesce(novo.dados_google_maps::TEXT::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'dados_google_maps', antigo.dados_google_maps::TEXT, novo.dados_google_maps::TEXT, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario_auditoria
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario_auditoria::varchar, '') <> coalesce(novo.id_usuario_auditoria::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'id_usuario_auditoria', antigo.id_usuario_auditoria, novo.id_usuario_auditoria, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR coalesce(antigo.excluido::varchar, '') <> coalesce(novo.excluido::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_estado
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_estado::varchar, '') <> coalesce(novo.id_estado::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'id_estado', antigo.id_estado, novo.id_estado, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_distrito
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_distrito::varchar, '') <> coalesce(novo.id_distrito::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'id_distrito', antigo.id_distrito, novo.id_distrito, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: uid_origem
	IF operacao IN ('I', 'D') OR coalesce(antigo.uid_origem::varchar, '') <> coalesce(novo.uid_origem::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'uid_origem', antigo.uid_origem, novo.uid_origem, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: ponto_referencia
	IF operacao IN ('I', 'D') OR coalesce(antigo.ponto_referencia::varchar, '') <> coalesce(novo.ponto_referencia::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'ponto_referencia', antigo.ponto_referencia, novo.ponto_referencia, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: local_google_maps
	IF operacao IN ('I', 'D') OR coalesce(antigo.local_google_maps::varchar, '') <> coalesce(novo.local_google_maps::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'local_google_maps', antigo.local_google_maps, novo.local_google_maps, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: localidade_distrito
	IF operacao IN ('I', 'D') OR coalesce(antigo.localidade_distrito::varchar, '') <> coalesce(novo.localidade_distrito::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'localidade_distrito', antigo.localidade_distrito, novo.localidade_distrito, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: descricao
	IF operacao IN ('I', 'D') OR coalesce(antigo.descricao::varchar, '') <> coalesce(novo.descricao::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'descricao', antigo.descricao, novo.descricao, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: cep
	IF operacao IN ('I', 'D') OR coalesce(antigo.cep::varchar, '') <> coalesce(novo.cep::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'cep', antigo.cep, novo.cep, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: app
	IF operacao IN ('I', 'D') OR coalesce(antigo.app::varchar, '') <> coalesce(novo.app::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'app', antigo.app, novo.app, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_localidade
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_localidade::varchar, '') <> coalesce(novo.id_localidade::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'id_localidade', antigo.id_localidade, novo.id_localidade, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_comprovante_residencia
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_comprovante_residencia::varchar, '') <> coalesce(novo.id_comprovante_residencia::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('endereco', novo.id, 'id_comprovante_residencia', antigo.id_comprovante_residencia, novo.id_comprovante_residencia, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_pessoa(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.func_aud_pessoa() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: nome
	IF operacao IN ('I', 'D') OR coalesce(antigo.nome::varchar, '') <> coalesce(novo.nome::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'nome', antigo.nome, novo.nome, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: cpf_cnpj
	IF operacao IN ('I', 'D') OR coalesce(antigo.cpf_cnpj::varchar, '') <> coalesce(novo.cpf_cnpj::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'cpf_cnpj', antigo.cpf_cnpj, novo.cpf_cnpj, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: tipo
	IF operacao IN ('I', 'D') OR coalesce(antigo.tipo::varchar, '') <> coalesce(novo.tipo::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'tipo', antigo.tipo, novo.tipo, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: data_nascimento
	IF operacao IN ('I', 'D') OR coalesce(antigo.data_nascimento::varchar, '') <> coalesce(novo.data_nascimento::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'data_nascimento', antigo.data_nascimento, novo.data_nascimento, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: email
	IF operacao IN ('I', 'D') OR coalesce(antigo.email::varchar, '') <> coalesce(novo.email::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'email', antigo.email, novo.email, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: senha
	IF operacao IN ('I', 'D') OR coalesce(antigo.senha::varchar, '') <> coalesce(novo.senha::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'senha', antigo.senha, novo.senha, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario_auditoria
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario_auditoria::varchar, '') <> coalesce(novo.id_usuario_auditoria::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'id_usuario_auditoria', antigo.id_usuario_auditoria, novo.id_usuario_auditoria, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR coalesce(antigo.excluido::varchar, '') <> coalesce(novo.excluido::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: telefone_principal
	IF operacao IN ('I', 'D') OR coalesce(antigo.telefone_principal::varchar, '') <> coalesce(novo.telefone_principal::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'telefone_principal', antigo.telefone_principal, novo.telefone_principal, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: telefone_secundario
	IF operacao IN ('I', 'D') OR coalesce(antigo.telefone_secundario::varchar, '') <> coalesce(novo.telefone_secundario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'telefone_secundario', antigo.telefone_secundario, novo.telefone_secundario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: data_abertura
	IF operacao IN ('I', 'D') OR coalesce(antigo.data_abertura::varchar, '') <> coalesce(novo.data_abertura::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'data_abertura', antigo.data_abertura, novo.data_abertura, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: razao_social
	IF operacao IN ('I', 'D') OR coalesce(antigo.razao_social::varchar, '') <> coalesce(novo.razao_social::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'razao_social', antigo.razao_social, novo.razao_social, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: nome_fantasia
	IF operacao IN ('I', 'D') OR coalesce(antigo.nome_fantasia::varchar, '') <> coalesce(novo.nome_fantasia::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'nome_fantasia', antigo.nome_fantasia, novo.nome_fantasia, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: cnae_primario
	IF operacao IN ('I', 'D') OR coalesce(antigo.cnae_primario::varchar, '') <> coalesce(novo.cnae_primario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'cnae_primario', antigo.cnae_primario, novo.cnae_primario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: cnae_secundario
	IF operacao IN ('I', 'D') OR coalesce(antigo.cnae_secundario::varchar, '') <> coalesce(novo.cnae_secundario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'cnae_secundario', antigo.cnae_secundario, novo.cnae_secundario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: inscricao_municipal
	IF operacao IN ('I', 'D') OR coalesce(antigo.inscricao_municipal::varchar, '') <> coalesce(novo.inscricao_municipal::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'inscricao_municipal', antigo.inscricao_municipal, novo.inscricao_municipal, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: alvara_funcionamento
	IF operacao IN ('I', 'D') OR coalesce(antigo.alvara_funcionamento::varchar, '') <> coalesce(novo.alvara_funcionamento::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'alvara_funcionamento', antigo.alvara_funcionamento, novo.alvara_funcionamento, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: alvara_sanitario
	IF operacao IN ('I', 'D') OR coalesce(antigo.alvara_sanitario::varchar, '') <> coalesce(novo.alvara_sanitario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'alvara_sanitario', antigo.alvara_sanitario, novo.alvara_sanitario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: email_contato
	IF operacao IN ('I', 'D') OR coalesce(antigo.email_contato::varchar, '') <> coalesce(novo.email_contato::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'email_contato', antigo.email_contato, novo.email_contato, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_arquivo_foto
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_arquivo_foto::varchar, '') <> coalesce(novo.id_arquivo_foto::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'id_arquivo_foto', antigo.id_arquivo_foto, novo.id_arquivo_foto, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: validado
	IF operacao IN ('I', 'D') OR coalesce(antigo.validado::varchar, '') <> coalesce(novo.validado::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'validado', antigo.validado, novo.validado, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: uid
	IF operacao IN ('I', 'D') OR coalesce(antigo.uid::varchar, '') <> coalesce(novo.uid::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'uid', antigo.uid, novo.uid, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: app
	IF operacao IN ('I', 'D') OR coalesce(antigo.app::varchar, '') <> coalesce(novo.app::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'app', antigo.app, novo.app, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: created_at
	IF operacao IN ('I', 'D') OR coalesce(antigo.created_at::varchar, '') <> coalesce(novo.created_at::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'created_at', antigo.created_at, novo.created_at, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: rg
	IF operacao IN ('I', 'D') OR coalesce(antigo.rg::varchar, '') <> coalesce(novo.rg::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'rg', antigo.rg, novo.rg, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: cnh
	IF operacao IN ('I', 'D') OR coalesce(antigo.cnh::varchar, '') <> coalesce(novo.cnh::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('pessoa', novo.id, 'cnh', antigo.cnh, novo.cnh, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_secretarias_unidade_trabalho(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.func_aud_secretarias_unidade_trabalho() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: id_unidade_trabalho
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_unidade_trabalho::varchar, '') <> coalesce(novo.id_unidade_trabalho::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('secretarias_unidade_trabalho', novo.id, 'id_unidade_trabalho', antigo.id_unidade_trabalho, novo.id_unidade_trabalho, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_secretaria
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_secretaria::varchar, '') <> coalesce(novo.id_secretaria::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('secretarias_unidade_trabalho', novo.id, 'id_secretaria', antigo.id_secretaria, novo.id_secretaria, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR coalesce(antigo.excluido::varchar, '') <> coalesce(novo.excluido::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('secretarias_unidade_trabalho', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario::varchar, '') <> coalesce(novo.id_usuario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('secretarias_unidade_trabalho', novo.id, 'id_usuario', antigo.id_usuario, novo.id_usuario, NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_sistema_usuario(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.func_aud_sistema_usuario() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: id_sistema
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_sistema::varchar, '') <> coalesce(novo.id_sistema::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('sistema_usuario', novo.id, 'id_sistema', antigo.id_sistema, novo.id_sistema, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario::varchar, '') <> coalesce(novo.id_usuario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('sistema_usuario', novo.id, 'id_usuario', antigo.id_usuario, novo.id_usuario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_tipo_usuario
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_tipo_usuario::varchar, '') <> coalesce(novo.id_tipo_usuario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('sistema_usuario', novo.id, 'id_tipo_usuario', antigo.id_tipo_usuario, novo.id_tipo_usuario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR coalesce(antigo.excluido::varchar, '') <> coalesce(novo.excluido::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('sistema_usuario', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: ativo
	IF operacao IN ('I', 'D') OR coalesce(antigo.ativo::varchar, '') <> coalesce(novo.ativo::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('sistema_usuario', novo.id, 'ativo', antigo.ativo, novo.ativo, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario_auditoria
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario_auditoria::varchar, '') <> coalesce(novo.id_usuario_auditoria::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('sistema_usuario', novo.id, 'id_usuario_auditoria', antigo.id_usuario_auditoria, novo.id_usuario_auditoria, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_usuario(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.func_aud_usuario() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: nome
	IF operacao IN ('I', 'D') OR coalesce(antigo.nome::varchar, '') <> coalesce(novo.nome::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'nome', antigo.nome, novo.nome, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: email
	IF operacao IN ('I', 'D') OR coalesce(antigo.email::varchar, '') <> coalesce(novo.email::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'email', antigo.email, novo.email, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: senha
	IF operacao IN ('I', 'D') OR coalesce(antigo.senha::varchar, '') <> coalesce(novo.senha::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'senha', antigo.senha, novo.senha, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: cpf
	IF operacao IN ('I', 'D') OR coalesce(antigo.cpf::varchar, '') <> coalesce(novo.cpf::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'cpf', antigo.cpf, novo.cpf, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: data_criacao
	IF operacao IN ('I', 'D') OR coalesce(antigo.data_criacao::varchar, '') <> coalesce(novo.data_criacao::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'data_criacao', antigo.data_criacao, novo.data_criacao, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_unidade_trabalho
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_unidade_trabalho::varchar, '') <> coalesce(novo.id_unidade_trabalho::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'id_unidade_trabalho', antigo.id_unidade_trabalho, novo.id_unidade_trabalho, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: ativo
	IF operacao IN ('I', 'D') OR coalesce(antigo.ativo::varchar, '') <> coalesce(novo.ativo::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'ativo', antigo.ativo, novo.ativo, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR coalesce(antigo.excluido::varchar, '') <> coalesce(novo.excluido::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: cargo
	IF operacao IN ('I', 'D') OR coalesce(antigo.cargo::varchar, '') <> coalesce(novo.cargo::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'cargo', antigo.cargo, novo.cargo, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: primeira_senha
	IF operacao IN ('I', 'D') OR coalesce(antigo.primeira_senha::varchar, '') <> coalesce(novo.primeira_senha::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'primeira_senha', antigo.primeira_senha, novo.primeira_senha, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: siafi_id_usuario
	IF operacao IN ('I', 'D') OR coalesce(antigo.siafi_id_usuario::varchar, '') <> coalesce(novo.siafi_id_usuario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'siafi_id_usuario', antigo.siafi_id_usuario, novo.siafi_id_usuario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: siafi_nome
	IF operacao IN ('I', 'D') OR coalesce(antigo.siafi_nome::varchar, '') <> coalesce(novo.siafi_nome::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'siafi_nome', antigo.siafi_nome, novo.siafi_nome, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: siafi_senha
	IF operacao IN ('I', 'D') OR coalesce(antigo.siafi_senha::varchar, '') <> coalesce(novo.siafi_senha::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'siafi_senha', antigo.siafi_senha, novo.siafi_senha, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: siafi_id_unidade_trabalho
	IF operacao IN ('I', 'D') OR coalesce(antigo.siafi_id_unidade_trabalho::varchar, '') <> coalesce(novo.siafi_id_unidade_trabalho::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'siafi_id_unidade_trabalho', antigo.siafi_id_unidade_trabalho, novo.siafi_id_unidade_trabalho, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario_auditoria
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario_auditoria::varchar, '') <> coalesce(novo.id_usuario_auditoria::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'id_usuario_auditoria', antigo.id_usuario_auditoria, novo.id_usuario_auditoria, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: uid
	IF operacao IN ('I', 'D') OR coalesce(antigo.uid::varchar, '') <> coalesce(novo.uid::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'uid', antigo.uid, novo.uid, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: app
	IF operacao IN ('I', 'D') OR coalesce(antigo.app::varchar, '') <> coalesce(novo.app::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'app', antigo.app, novo.app, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: telefone
	IF operacao IN ('I', 'D') OR coalesce(antigo.telefone::varchar, '') <> coalesce(novo.telefone::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario', novo.id, 'telefone', antigo.telefone, novo.telefone, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: func_aud_usuario_grupo(); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.func_aud_usuario_grupo() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
 DECLARE
	operacao varchar(2);
	antigo record;
	novo record;
 BEGIN

	IF (TG_OP = 'INSERT') THEN
		operacao := 'I'; 
		antigo := new; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE' AND old.excluido <> new.excluido AND new.excluido = true) THEN
		operacao := 'LE'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'UPDATE') THEN
		operacao := 'U'; 
		antigo := old; 
		novo := new; 
	ELSEIF (TG_OP = 'DELETE') THEN
		operacao := 'D'; 
		antigo := old; 
		novo := old; 
	END IF;

	-- Campo: id_usuario
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario::varchar, '') <> coalesce(novo.id_usuario::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario_grupo', novo.id, 'id_usuario', antigo.id_usuario, novo.id_usuario, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_grupo
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_grupo::varchar, '') <> coalesce(novo.id_grupo::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario_grupo', novo.id, 'id_grupo', antigo.id_grupo, novo.id_grupo, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: ativo
	IF operacao IN ('I', 'D') OR coalesce(antigo.ativo::varchar, '') <> coalesce(novo.ativo::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario_grupo', novo.id, 'ativo', antigo.ativo, novo.ativo, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: excluido
	IF operacao IN ('I', 'D') OR coalesce(antigo.excluido::varchar, '') <> coalesce(novo.excluido::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario_grupo', novo.id, 'excluido', antigo.excluido, novo.excluido, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_unidade_trabalho
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_unidade_trabalho::varchar, '') <> coalesce(novo.id_unidade_trabalho::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario_grupo', novo.id, 'id_unidade_trabalho', antigo.id_unidade_trabalho, novo.id_unidade_trabalho, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: id_usuario_auditoria
	IF operacao IN ('I', 'D') OR coalesce(antigo.id_usuario_auditoria::varchar, '') <> coalesce(novo.id_usuario_auditoria::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario_grupo', novo.id, 'id_usuario_auditoria', antigo.id_usuario_auditoria, novo.id_usuario_auditoria, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;

	-- Campo: app
	IF operacao IN ('I', 'D') OR coalesce(antigo.app::varchar, '') <> coalesce(novo.app::varchar, '') THEN
		INSERT INTO utils.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ('usuario_grupo', novo.id, 'app', antigo.app, novo.app, NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());
	END IF;


 RETURN NEW;
END; 
$$;


--
-- Name: gera_fonte_auditoria(character varying, character varying, boolean); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.gera_fonte_auditoria(schema character varying, tabela character varying, executar boolean) RETURNS text
    LANGUAGE plpgsql
    AS $_$
DECLARE
    nome   VARCHAR(128);
    saida  text;
    coluna text;
    tuplas text;
BEGIN
    nome := 'aud_' || tabela;
    tuplas := '';

    FOR coluna in SELECT column_name
                  FROM information_schema.Columns
                  WHERE table_schema = schema
                    AND table_name = tabela
                    AND column_name != 'id'
        LOOP
            tuplas := tuplas || e'\n	-- Campo: ' || coluna;
            tuplas := tuplas || e'\n	IF operacao IN (''I'', ''D'') OR coalesce(antigo.' || coluna || '::varchar, '''') <> coalesce(novo.' || coluna || '::varchar, '''') THEN';
            tuplas := tuplas || e'\n		INSERT INTO ' || schema ||
                      '.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ';
            tuplas := tuplas || '(''' || tabela || ''', novo.id, ''' || coluna || ''', antigo.' || coluna ||
                      ', novo.' || coluna ||
                      ', NOW(), operacao, novo.id_usuario, inet_client_addr(), CURRENT_USER, pg_backend_pid());';
            tuplas := tuplas || e'\n	END IF;\n';
        END LOOP;

    saida := 'CREATE OR REPLACE FUNCTION ' || schema || '.func_' || nome || '()'
                 || e'\n RETURNS trigger AS $aud_trigger$'
                 || e'\n DECLARE'
                 || e'\n	operacao varchar(2);'
                 || e'\n	antigo record;'
                 || e'\n	novo record;'
                 || e'\n BEGIN'
                 || e'\n'
                 || e'\n	IF (TG_OP = ''INSERT'') THEN'
                 || e'\n		operacao := ''I''; '
                 || e'\n		antigo := new; '
                 || e'\n		novo := new; '
                 || e'\n	ELSEIF (TG_OP = ''UPDATE'' AND old.excluido <> new.excluido AND new.excluido = true) THEN'
                 || e'\n		operacao := ''LE''; '
                 || e'\n		antigo := old; '
                 || e'\n		novo := new; '
                 || e'\n	ELSEIF (TG_OP = ''UPDATE'') THEN'
                 || e'\n		operacao := ''U''; '
                 || e'\n		antigo := old; '
                 || e'\n		novo := new; '
                 || e'\n	ELSEIF (TG_OP = ''DELETE'') THEN'
                 || e'\n		operacao := ''D''; '
                 || e'\n		antigo := old; '
                 || e'\n		novo := old; '
                 || e'\n	END IF;'
                 || e'\n'
                 || tuplas
                 || e'\n'
                 || e'\n RETURN NEW;'
                 || e'\nEND; \n' || e'$aud_trigger$ LANGUAGE plpgsql;'
                 || e'\n\n'
                 || e'DROP TRIGGER IF EXISTS trigger_' || nome || ' ON ' || schema || '.' || tabela || ';'
                 || e'\nCREATE TRIGGER trigger_' || nome
                 || e'\nAFTER INSERT OR UPDATE OR DELETE ON ' || schema || '.' || tabela
                 || e'\nFOR EACH ROW'
                 || e'\nEXECUTE PROCEDURE ' || schema || '.func_' || nome || '();';

    raise info e'\n+-+-+-+-+-TRIGGER % -+-+-+-+-+\n\n%\n\n+-+-+-+-+-TRIGGER % -+-+-+-+-+', schema || '.' || nome, saida, schema || '.' || nome;

    IF (executar = TRUE) THEN
        EXECUTE saida;
    END IF;

    return saida;
END
$_$;


--
-- Name: gera_fonte_auditoria_acl(character varying, character varying, boolean); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.gera_fonte_auditoria_acl(schema character varying, tabela character varying, executar boolean) RETURNS text
    LANGUAGE plpgsql
    AS $_$
DECLARE
	nome VARCHAR(128);
	saida 				text;
	coluna 				text;
	tuplas		 		text;
	tipo_campo			text;
	campo_new_cast		text;
	campo_old_cast		text;
	retornoSelect		record;
BEGIN
	nome := 'aud_' || tabela;
	tuplas := '';
	campo_new_cast := '';
	campo_old_cast := '';

	FOR retornoSelect in SELECT column_name, data_type FROM information_schema.Columns WHERE table_schema = schema AND table_name = tabela AND column_name != 'id' LOOP
		coluna := retornoSelect.column_name;
		tipo_campo := retornoSelect.data_type;

		campo_new_cast := '';
		campo_old_cast := '';
		
		IF(tipo_campo = 'json') THEN
			campo_new_cast := '::TEXT';
			campo_old_cast := '::TEXT';
		END IF;
		
		tuplas := tuplas || e'\n	-- Campo: ' || coluna;
		tuplas := tuplas || e'\n	IF operacao IN (''I'', ''D'') OR coalesce(antigo.' || coluna || campo_new_cast || '::varchar, '''') <> coalesce(novo.' || coluna || campo_new_cast || '::varchar, '''') THEN';
		tuplas := tuplas || e'\n		INSERT INTO ' || schema || '.auditoria (tabela, id_tabela, campo, valor_antigo, valor_novo, data, operacao, id_usuario, ip, usuario_banco, pid_conexao) values ';
		tuplas := tuplas || '(''' || tabela || ''', novo.id, ''' || coluna || ''', antigo.' || coluna || campo_old_cast || ', novo.' || coluna || campo_new_cast || ', NOW(), operacao, novo.id_usuario_auditoria, inet_client_addr(), CURRENT_USER, pg_backend_pid());';
		tuplas := tuplas || e'\n	END IF;\n';
	END LOOP;

	saida 	:= 'CREATE OR REPLACE FUNCTION ' || schema || '.func_' || nome || '()'
		|| e'\n RETURNS trigger AS $aud_trigger$'
		|| e'\n DECLARE'
		|| e'\n	operacao varchar(2);'
		|| e'\n	antigo record;'
		|| e'\n	novo record;'
		|| e'\n BEGIN'
		|| e'\n'
		|| e'\n	IF (TG_OP = ''INSERT'') THEN'
		|| e'\n		operacao := ''I''; '
		|| e'\n		antigo := new; '
		|| e'\n		novo := new; '
		|| e'\n	ELSEIF (TG_OP = ''UPDATE'' AND old.excluido <> new.excluido AND new.excluido = true) THEN'
		|| e'\n		operacao := ''LE''; '
		|| e'\n		antigo := old; '
		|| e'\n		novo := new; '
		|| e'\n	ELSEIF (TG_OP = ''UPDATE'') THEN'
		|| e'\n		operacao := ''U''; '
		|| e'\n		antigo := old; '
		|| e'\n		novo := new; '
		|| e'\n	ELSEIF (TG_OP = ''DELETE'') THEN'
		|| e'\n		operacao := ''D''; '
		|| e'\n		antigo := old; '
		|| e'\n		novo := old; '
		|| e'\n	END IF;'
		|| e'\n'
		|| tuplas
		|| e'\n'
		|| e'\n RETURN NEW;'
 		|| e'\nEND; \n' || e'$aud_trigger$ LANGUAGE plpgsql;'
		|| e'\n\n'
		|| e'DROP TRIGGER IF EXISTS trigger_' || nome || ' ON ' || schema || '.' || tabela || ';'
		|| e'\nCREATE TRIGGER trigger_' || nome
		|| e'\nAFTER INSERT OR UPDATE OR DELETE ON ' || schema || '.' || tabela
		|| e'\nFOR EACH ROW'
		|| e'\nEXECUTE PROCEDURE ' || schema || '.func_' || nome || '();';

	raise info e'\n+-+-+-+-+-TRIGGER % -+-+-+-+-+\n\n%\n\n+-+-+-+-+-TRIGGER % -+-+-+-+-+', schema||'.'||nome, saida, schema||'.'||nome;

	IF(executar = TRUE) THEN
		EXECUTE saida;
	END IF;

	return saida;
END
$_$;


--
-- Name: verificar_usuario(character varying, character varying); Type: FUNCTION; Schema: utils; Owner: -
--

CREATE FUNCTION utils.verificar_usuario(email character varying, senha character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $_$
declare valido boolean;
begin
	select coalesce((us.senha = md5($2)), false) into valido
	from utils.usuario us
	where us.email = $1;
	
	return valido;
end
$_$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.audit_log (
    id bigint NOT NULL,
    tenant_id integer NOT NULL,
    id_usuario integer,
    acao character varying(80) NOT NULL,
    entidade character varying(60) NOT NULL,
    id_entidade bigint,
    payload jsonb,
    request_id character varying(64),
    ip character varying(64),
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY aprimora_py.audit_log FORCE ROW LEVEL SECURITY;


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.audit_log_id_seq OWNED BY aprimora_py.audit_log.id;


--
-- Name: job; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.job (
    id integer NOT NULL,
    tipo character varying(60) NOT NULL,
    descricao character varying(255),
    status character varying(20) DEFAULT 'pendente'::character varying NOT NULL,
    parametros jsonb,
    resultado_path character varying(500),
    erro text,
    id_usuario integer NOT NULL,
    celery_task_id character varying(64),
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    iniciado_em timestamp without time zone,
    concluido_em timestamp without time zone,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY aprimora_py.job FORCE ROW LEVEL SECURITY;


--
-- Name: job_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.job_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: job_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.job_id_seq OWNED BY aprimora_py.job.id;


--
-- Name: notificacao; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.notificacao (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_usuario integer,
    destinatario_email character varying(200),
    canal character varying(20) NOT NULL,
    tipo character varying(50) NOT NULL,
    titulo character varying(200) NOT NULL,
    mensagem text NOT NULL,
    link_url character varying(500),
    payload jsonb,
    prioridade character varying(10) DEFAULT 'normal'::character varying NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    lido_em timestamp without time zone,
    enviado_em timestamp without time zone,
    erro text,
    CONSTRAINT notificacao_destino_chk CHECK (((id_usuario IS NOT NULL) OR (destinatario_email IS NOT NULL)))
);

ALTER TABLE ONLY aprimora_py.notificacao FORCE ROW LEVEL SECURITY;


--
-- Name: notificacao_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.notificacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notificacao_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.notificacao_id_seq OWNED BY aprimora_py.notificacao.id;


--
-- Name: notificacao_preferencia; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.notificacao_preferencia (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_usuario integer NOT NULL,
    canal_in_app boolean DEFAULT true NOT NULL,
    canal_email boolean DEFAULT true NOT NULL,
    canal_whatsapp boolean DEFAULT false NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    atualizado_em timestamp without time zone
);

ALTER TABLE ONLY aprimora_py.notificacao_preferencia FORCE ROW LEVEL SECURITY;


--
-- Name: notificacao_preferencia_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.notificacao_preferencia_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notificacao_preferencia_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.notificacao_preferencia_id_seq OWNED BY aprimora_py.notificacao_preferencia.id;


--
-- Name: nup_sequencia; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.nup_sequencia (
    tenant_id integer NOT NULL,
    codigo_orgao character varying(5) NOT NULL,
    ano integer NOT NULL,
    ultimo_sequencial integer DEFAULT 0 NOT NULL,
    atualizado_em timestamp without time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY aprimora_py.nup_sequencia FORCE ROW LEVEL SECURITY;


--
-- Name: tenant; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.tenant (
    id integer NOT NULL,
    slug character varying(50) NOT NULL,
    nome character varying(150) NOT NULL,
    cnpj character varying(20),
    id_cidade integer,
    ativo boolean DEFAULT true NOT NULL,
    plano character varying(20) DEFAULT 'basico'::character varying NOT NULL,
    cor_primaria character varying(7),
    logo_url character varying(500),
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    atualizado_em timestamp without time zone,
    codigo_orgao_nup character varying(5),
    usar_nup_federal boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_tenant_codigo_orgao_nup_5_digitos CHECK (((codigo_orgao_nup IS NULL) OR ((codigo_orgao_nup)::text ~ '^[0-9]{5}$'::text)))
);


--
-- Name: tenant_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.tenant_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tenant_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.tenant_id_seq OWNED BY aprimora_py.tenant.id;


--
-- Name: tipo_processo_workflow; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.tipo_processo_workflow (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_tipo_processo integer NOT NULL,
    slug_workflow character varying(80) NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    atualizado_em timestamp without time zone
);

ALTER TABLE ONLY aprimora_py.tipo_processo_workflow FORCE ROW LEVEL SECURITY;


--
-- Name: tipo_processo_workflow_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.tipo_processo_workflow_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_processo_workflow_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.tipo_processo_workflow_id_seq OWNED BY aprimora_py.tipo_processo_workflow.id;


--
-- Name: workflow_definition; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.workflow_definition (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    slug character varying(80) NOT NULL,
    nome character varying(200) NOT NULL,
    descricao text,
    versao integer DEFAULT 1 NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    dsl jsonb NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    atualizado_em timestamp without time zone,
    id_usuario_criador integer
);

ALTER TABLE ONLY aprimora_py.workflow_definition FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_definition_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.workflow_definition_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workflow_definition_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.workflow_definition_id_seq OWNED BY aprimora_py.workflow_definition.id;


--
-- Name: workflow_instance; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.workflow_instance (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_workflow_definition integer NOT NULL,
    id_processo integer NOT NULL,
    estado_atual character varying(50) NOT NULL,
    ativa boolean DEFAULT true NOT NULL,
    iniciada_em timestamp without time zone DEFAULT now() NOT NULL,
    finalizada_em timestamp without time zone,
    id_usuario_inicio integer
);

ALTER TABLE ONLY aprimora_py.workflow_instance FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_instance_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.workflow_instance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workflow_instance_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.workflow_instance_id_seq OWNED BY aprimora_py.workflow_instance.id;


--
-- Name: workflow_sla_alerta; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.workflow_sla_alerta (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_workflow_instance integer NOT NULL,
    estado character varying(50) NOT NULL,
    sla_dias integer NOT NULL,
    dias_no_estado integer NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    resolvido_em timestamp without time zone,
    resolucao character varying(40),
    notificado_em timestamp without time zone
);

ALTER TABLE ONLY aprimora_py.workflow_sla_alerta FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_sla_alerta_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.workflow_sla_alerta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workflow_sla_alerta_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.workflow_sla_alerta_id_seq OWNED BY aprimora_py.workflow_sla_alerta.id;


--
-- Name: workflow_transicao_log; Type: TABLE; Schema: aprimora_py; Owner: -
--

CREATE TABLE aprimora_py.workflow_transicao_log (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_workflow_instance integer NOT NULL,
    estado_de character varying(50) NOT NULL,
    estado_para character varying(50) NOT NULL,
    transicao_label character varying(120) NOT NULL,
    id_usuario integer,
    contexto_snapshot jsonb,
    executada_em timestamp without time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY aprimora_py.workflow_transicao_log FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_transicao_log_id_seq; Type: SEQUENCE; Schema: aprimora_py; Owner: -
--

CREATE SEQUENCE aprimora_py.workflow_transicao_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workflow_transicao_log_id_seq; Type: SEQUENCE OWNED BY; Schema: aprimora_py; Owner: -
--

ALTER SEQUENCE aprimora_py.workflow_transicao_log_id_seq OWNED BY aprimora_py.workflow_transicao_log.id;


--
-- Name: acao; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.acao (
    id integer NOT NULL,
    flag character varying(100) NOT NULL,
    acao character varying(100) NOT NULL,
    status_acao character varying(60) NOT NULL,
    status_movimentacao character varying(60) NOT NULL,
    texto_acao character varying(255),
    exibe_unidade_destino boolean,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_acao_spu integer
);


--
-- Name: acao_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.acao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acao_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.acao_id_seq OWNED BY protocolos.acao.id;


--
-- Name: acoes_privadas_movimentacao; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.acoes_privadas_movimentacao (
    id integer NOT NULL,
    id_acao integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: acoes_privadas_movimentacao_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.acoes_privadas_movimentacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acoes_privadas_movimentacao_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.acoes_privadas_movimentacao_id_seq OWNED BY protocolos.acoes_privadas_movimentacao.id;


--
-- Name: alfresco_aux; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.alfresco_aux (
    id integer NOT NULL,
    id_string_value character varying,
    nome_arquivo character varying,
    data_de_upload timestamp without time zone,
    tamanho integer,
    node_id integer,
    long_value integer,
    string_value character varying,
    content_url character varying
);


--
-- Name: alfresco_aux_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.alfresco_aux_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alfresco_aux_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.alfresco_aux_id_seq OWNED BY protocolos.alfresco_aux.id;


--
-- Name: anexo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.anexo (
    id integer NOT NULL,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    id_tipo_anexo integer,
    publico boolean DEFAULT false NOT NULL,
    id_usuario integer,
    id_usuario_externo integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    e_doc character varying(25),
    descricao character varying(512),
    id_alfresco integer,
    qtd_paginas integer,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.anexo FORCE ROW LEVEL SECURITY;


--
-- Name: anexo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.anexo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: anexo_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.anexo_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: anexo_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.anexo_id_seq1 OWNED BY protocolos.anexo.id;


--
-- Name: anexo_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.anexo_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_anexo integer NOT NULL,
    id_movimentacao integer NOT NULL,
    id_usuario integer,
    id_usuario_externo integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    ordem integer,
    anexo_herdado boolean DEFAULT false NOT NULL,
    tenant_id integer NOT NULL,
    desentranhado_em timestamp without time zone,
    id_usuario_desentranhamento integer,
    motivo_desentranhamento character varying(1000),
    autoridade_desentranhamento character varying(300)
);

ALTER TABLE ONLY protocolos.anexo_processo FORCE ROW LEVEL SECURITY;


--
-- Name: anexo_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.anexo_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: anexo_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.anexo_processo_id_seq OWNED BY protocolos.anexo_processo.id;


--
-- Name: arquivamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.arquivamento (
    id integer NOT NULL,
    id_status_arquivamento integer NOT NULL,
    motivo character varying(255),
    local character varying(255),
    arquivo character varying(255),
    estante character varying(255),
    prateleira character varying(255),
    caixa character varying(255),
    pasta character varying(255),
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    movimentacao_id integer,
    permanente boolean DEFAULT false,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.arquivamento FORCE ROW LEVEL SECURITY;


--
-- Name: arquivamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.arquivamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: arquivamento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.arquivamento_id_seq OWNED BY protocolos.arquivamento.id;


--
-- Name: arquivo_temporario; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.arquivo_temporario (
    id integer NOT NULL,
    nome_do_arquivo character varying(255) NOT NULL,
    nome_real character varying(255) NOT NULL,
    data_de_upload timestamp without time zone DEFAULT now(),
    pasta character varying(255) NOT NULL,
    extensao character varying(5) NOT NULL,
    tamanho integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: arquivo_temporario_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.arquivo_temporario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: arquivo_temporario_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.arquivo_temporario_id_seq OWNED BY protocolos.arquivo_temporario.id;


--
-- Name: assinatura_anexo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.assinatura_anexo (
    id integer NOT NULL,
    id_usuario_assinatura integer NOT NULL,
    id_anexo integer NOT NULL,
    assinado boolean,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    dt_assinatura timestamp without time zone,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_processo integer,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.assinatura_anexo FORCE ROW LEVEL SECURITY;


--
-- Name: assinatura_anexo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.assinatura_anexo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assinatura_anexo_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.assinatura_anexo_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assinatura_anexo_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.assinatura_anexo_id_seq1 OWNED BY protocolos.assinatura_anexo.id;


--
-- Name: assinatura_avulsa; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.assinatura_avulsa (
    id integer NOT NULL,
    arquivo_deletado boolean DEFAULT false NOT NULL,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    data_hora_realizado timestamp without time zone DEFAULT now(),
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: assinatura_avulsa_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.assinatura_avulsa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assinatura_avulsa_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.assinatura_avulsa_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assinatura_avulsa_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.assinatura_avulsa_id_seq1 OWNED BY protocolos.assinatura_avulsa.id;


--
-- Name: assistente_assinatura; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.assistente_assinatura (
    id integer NOT NULL,
    id_assistente integer NOT NULL,
    id_gerente integer NOT NULL,
    id_unidade_trabalho integer NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: assistente_assinatura_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.assistente_assinatura_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assistente_assinatura_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.assistente_assinatura_id_seq OWNED BY protocolos.assistente_assinatura.id;


--
-- Name: assunto; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.assunto (
    id integer NOT NULL,
    assunto character varying(1000) NOT NULL,
    id_tipo_processo integer NOT NULL,
    exige_processo_pai boolean DEFAULT false NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    dados_liquidacao boolean DEFAULT false,
    fluxo_despesa boolean DEFAULT false,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.assunto FORCE ROW LEVEL SECURITY;


--
-- Name: assunto_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.assunto_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assunto_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.assunto_id_seq OWNED BY protocolos.assunto.id;


--
-- Name: assunto_tipo_processo_tipo_anexo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.assunto_tipo_processo_tipo_anexo (
    id integer NOT NULL,
    id_assunto integer,
    id_tipo_processo integer,
    id_tipo_anexo integer NOT NULL,
    obrigatorio boolean DEFAULT false,
    opcional boolean DEFAULT false,
    excluido boolean DEFAULT false,
    id_usuario integer,
    tenant_id integer NOT NULL,
    CONSTRAINT chk_ou_exclusivo CHECK ((((id_assunto IS NOT NULL) AND (id_tipo_processo IS NULL)) OR ((id_tipo_processo IS NOT NULL) AND (id_assunto IS NULL))))
);

ALTER TABLE ONLY protocolos.assunto_tipo_processo_tipo_anexo FORCE ROW LEVEL SECURITY;


--
-- Name: assunto_tipo_processo_tipo_anexo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.assunto_tipo_processo_tipo_anexo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assunto_tipo_processo_tipo_anexo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.assunto_tipo_processo_tipo_anexo_id_seq OWNED BY protocolos.assunto_tipo_processo_tipo_anexo.id;


--
-- Name: auditoria; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.auditoria (
    id integer NOT NULL,
    tabela character varying(128) NOT NULL,
    id_tabela integer NOT NULL,
    campo character varying(128) NOT NULL,
    valor_antigo character varying(512),
    valor_novo character varying(512),
    data timestamp without time zone NOT NULL,
    operacao character varying(2) NOT NULL,
    id_usuario integer NOT NULL,
    ip character varying(32) NOT NULL,
    usuario_banco character varying(64) NOT NULL,
    pid_conexao integer NOT NULL
);


--
-- Name: auditoria_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.auditoria_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auditoria_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.auditoria_id_seq OWNED BY protocolos.auditoria.id;


--
-- Name: avaliacao_anexo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.avaliacao_anexo (
    id integer NOT NULL,
    id_usuario_avaliacao_documento integer NOT NULL,
    id_anexo integer NOT NULL,
    aprovado boolean,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    data_hora_realizado timestamp without time zone,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: avaliacao_anexo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.avaliacao_anexo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: avaliacao_anexo_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.avaliacao_anexo_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: avaliacao_anexo_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.avaliacao_anexo_id_seq1 OWNED BY protocolos.avaliacao_anexo.id;


--
-- Name: bairros_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.bairros_spu (
    id integer NOT NULL,
    nome character varying(255),
    cidade_id bigint NOT NULL,
    id_bairro_utils bigint,
    id_distrito_utils bigint
);


--
-- Name: bairros_spu_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.bairros_spu_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bairros_spu_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.bairros_spu_id_seq OWNED BY protocolos.bairros_spu.id;


--
-- Name: caixa; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.caixa (
    id integer NOT NULL,
    flag character varying,
    caixa character varying,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: caixa_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.caixa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: caixa_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.caixa_id_seq OWNED BY protocolos.caixa.id;


--
-- Name: carimbamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.carimbamento (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_movimentacao integer NOT NULL,
    id_usuario integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_template_carimbo integer
);


--
-- Name: carimbamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.carimbamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: carimbamento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.carimbamento_id_seq OWNED BY protocolos.carimbamento.id;


--
-- Name: categoria; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.categoria (
    id integer NOT NULL,
    categoria character varying(100),
    tipo character varying(50),
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: categoria_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.categoria_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categoria_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.categoria_id_seq OWNED BY protocolos.categoria.id;


--
-- Name: ccd_classe; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.ccd_classe (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    codigo character varying(20) NOT NULL,
    nome character varying(200) NOT NULL,
    descricao character varying(1000),
    id_classe_pai integer,
    palavras_chave character varying(500),
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY protocolos.ccd_classe FORCE ROW LEVEL SECURITY;


--
-- Name: ccd_classe_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.ccd_classe_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ccd_classe_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.ccd_classe_id_seq OWNED BY protocolos.ccd_classe.id;


--
-- Name: cidades_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.cidades_spu (
    id integer NOT NULL,
    nome character varying(255),
    estado_id integer NOT NULL,
    id_cidade_utils integer
);


--
-- Name: cidades_spu_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.cidades_spu_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cidades_spu_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.cidades_spu_id_seq OWNED BY protocolos.cidades_spu.id;


--
-- Name: copia_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.copia_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_unidade_destino integer NOT NULL,
    id_movimentacao integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: copia_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.copia_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: copia_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.copia_processo_id_seq OWNED BY protocolos.copia_processo.id;


--
-- Name: dados_acesso; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.dados_acesso (
    id integer NOT NULL,
    ip character varying(45) NOT NULL,
    dispositivo character varying(45) NOT NULL
);


--
-- Name: dados_acesso_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.dados_acesso_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dados_acesso_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.dados_acesso_id_seq OWNED BY protocolos.dados_acesso.id;


--
-- Name: dados_manifestante_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.dados_manifestante_processo (
    id integer NOT NULL,
    responsavel character varying,
    organizacao character varying,
    telefone_residencial character varying(20),
    telefone_celular character varying(20),
    telefone_comercial character varying(20),
    email character varying(100),
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL,
    id_processo integer,
    id_usuario_externo integer
);


--
-- Name: dados_manifestante_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.dados_manifestante_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dados_manifestante_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.dados_manifestante_processo_id_seq OWNED BY protocolos.dados_manifestante_processo.id;


--
-- Name: desentranhamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.desentranhamento (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_ficha_anexo integer NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: desentranhamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.desentranhamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: desentranhamento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.desentranhamento_id_seq OWNED BY protocolos.desentranhamento.id;


--
-- Name: despacho; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.despacho (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    despacho text NOT NULL,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_movimentacao integer,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.despacho FORCE ROW LEVEL SECURITY;


--
-- Name: despacho_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.despacho_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: despacho_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.despacho_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: despacho_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.despacho_id_seq1 OWNED BY protocolos.despacho.id;


--
-- Name: diligencia; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.diligencia (
    id integer NOT NULL,
    diligencia character varying NOT NULL,
    resposta character varying,
    id_processo integer NOT NULL,
    respondida boolean DEFAULT false NOT NULL,
    dt_respondida timestamp without time zone,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: diligencia_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.diligencia_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: diligencia_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.diligencia_id_seq OWNED BY protocolos.diligencia.id;


--
-- Name: documento_carimbamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.documento_carimbamento (
    id integer NOT NULL,
    id_carimbamento integer NOT NULL,
    id_anexo integer NOT NULL,
    page_index integer NOT NULL,
    x double precision NOT NULL,
    y double precision NOT NULL,
    scroll_to_x double precision NOT NULL,
    scroll_to_y double precision NOT NULL,
    id_usuario integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: documento_carimbamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.documento_carimbamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documento_carimbamento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.documento_carimbamento_id_seq OWNED BY protocolos.documento_carimbamento.id;


--
-- Name: documentos_movimentacoes_aux; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.documentos_movimentacoes_aux (
    id integer NOT NULL,
    string_value character varying,
    nome_arquivo character varying,
    processo_id integer NOT NULL,
    movimentacao_id integer NOT NULL,
    lotacao_origem_id integer NOT NULL,
    created_at date,
    updated_at date
);


--
-- Name: documentos_movimentacoes_aux_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.documentos_movimentacoes_aux_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documentos_movimentacoes_aux_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.documentos_movimentacoes_aux_id_seq OWNED BY protocolos.documentos_movimentacoes_aux.id;


--
-- Name: empenho_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.empenho_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_empenho integer NOT NULL,
    ctrcod integer,
    liccod integer,
    data_criacao timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    excluido boolean DEFAULT false,
    id_usuario integer,
    herdado boolean DEFAULT false
);


--
-- Name: empenho_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.empenho_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: empenho_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.empenho_processo_id_seq OWNED BY protocolos.empenho_processo.id;


--
-- Name: encaminhamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.encaminhamento (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_unidade_origem integer,
    id_unidade_destino integer NOT NULL,
    id_prioridade integer NOT NULL,
    quantidade_folhas integer DEFAULT 0 NOT NULL,
    data_prazo date,
    externo boolean DEFAULT false NOT NULL,
    recebido boolean DEFAULT false NOT NULL,
    data_hora_recebimento timestamp without time zone,
    id_usuario_recebimento integer,
    cancelado boolean DEFAULT false NOT NULL,
    data_hora_cancelamento timestamp without time zone,
    id_usuario_cancelamento integer,
    envio_cancelado boolean DEFAULT false NOT NULL,
    data_hora_cancelamento_envio timestamp without time zone,
    id_usuario_cancelamento_envio integer,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_movimentacao integer,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.encaminhamento FORCE ROW LEVEL SECURITY;


--
-- Name: encaminhamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.encaminhamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: encaminhamento_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.encaminhamento_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: encaminhamento_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.encaminhamento_id_seq1 OWNED BY protocolos.encaminhamento.id;


--
-- Name: endereco_manifestante_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.endereco_manifestante_spu (
    id integer NOT NULL,
    id_manifestante integer NOT NULL,
    id_estado integer,
    id_cidade integer,
    id_bairro integer,
    rua character varying(255),
    cep character varying(30),
    numero character varying(255),
    complemento character varying(255),
    app character varying(100) NOT NULL
);


--
-- Name: endereco_manifestante_spu_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.endereco_manifestante_spu_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: endereco_manifestante_spu_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.endereco_manifestante_spu_id_seq OWNED BY protocolos.endereco_manifestante_spu.id;


--
-- Name: especie_documental; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.especie_documental (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    flag character varying(40) NOT NULL,
    nome character varying(120) NOT NULL,
    descricao character varying(500),
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY protocolos.especie_documental FORCE ROW LEVEL SECURITY;


--
-- Name: especie_documental_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.especie_documental_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: especie_documental_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.especie_documental_id_seq OWNED BY protocolos.especie_documental.id;


--
-- Name: estados_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.estados_spu (
    id integer NOT NULL,
    sigla character varying(10),
    nome character varying(255),
    id_estado_utils integer
);


--
-- Name: estados_spu_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.estados_spu_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: estados_spu_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.estados_spu_id_seq OWNED BY protocolos.estados_spu.id;


--
-- Name: exclusao_anexo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.exclusao_anexo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_anexo integer NOT NULL,
    id_movimentacao integer NOT NULL,
    id_usuario integer,
    id_usuario_externo integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false
);


--
-- Name: exclusao_anexo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.exclusao_anexo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: exclusao_anexo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.exclusao_anexo_id_seq OWNED BY protocolos.exclusao_anexo.id;


--
-- Name: gerar_processo_completo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.gerar_processo_completo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    data_solicitacao timestamp without time zone DEFAULT now() NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    uid_geracao uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    data_ini_geracao timestamp without time zone,
    data_fim_geracao timestamp without time zone,
    tempo_total_geracao character varying(255),
    id_usuario integer NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    id_anexo integer
);


--
-- Name: gerar_processo_completo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.gerar_processo_completo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gerar_processo_completo_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.gerar_processo_completo_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gerar_processo_completo_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.gerar_processo_completo_id_seq1 OWNED BY protocolos.gerar_processo_completo.id;


--
-- Name: gerar_processos_envolvido; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.gerar_processos_envolvido (
    id integer NOT NULL,
    id_usuario integer NOT NULL,
    data_solicitacao timestamp without time zone DEFAULT now() NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    data_inicio_geracao timestamp without time zone,
    data_fim_geracao timestamp without time zone,
    excluido boolean DEFAULT false NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    uid_geracao uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tempo_total_geracao character varying(500),
    id_secretaria integer,
    descricao character varying,
    erro text,
    tipo character varying
);


--
-- Name: gerar_processos_envolvido_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.gerar_processos_envolvido_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gerar_processos_envolvido_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.gerar_processos_envolvido_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gerar_processos_envolvido_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.gerar_processos_envolvido_id_seq1 OWNED BY protocolos.gerar_processos_envolvido.id;


--
-- Name: hierarquia_assunto_tipo_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.hierarquia_assunto_tipo_processo (
    id integer NOT NULL,
    id_assunto integer,
    id_tipo_processo integer,
    id_assunto_pai integer,
    id_tipo_processo_pai integer,
    id_usuario integer,
    excluido boolean DEFAULT false
);


--
-- Name: hierarquia_assunto_tipo_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.hierarquia_assunto_tipo_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hierarquia_assunto_tipo_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.hierarquia_assunto_tipo_processo_id_seq OWNED BY protocolos.hierarquia_assunto_tipo_processo.id;


--
-- Name: incorporacao; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.incorporacao (
    id integer NOT NULL,
    id_movimentacao integer NOT NULL,
    id_incorporador integer NOT NULL,
    id_incorporado integer NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: incorporacao_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.incorporacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incorporacao_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.incorporacao_id_seq OWNED BY protocolos.incorporacao.id;


--
-- Name: incorporacao_status; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.incorporacao_status (
    id integer NOT NULL,
    incorporacao_status character varying NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: incorporacao_status_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.incorporacao_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incorporacao_status_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.incorporacao_status_id_seq OWNED BY protocolos.incorporacao_status.id;


--
-- Name: liquidacao_despesas_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.liquidacao_despesas_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_feempliq integer NOT NULL,
    data_criacao timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    excluido boolean DEFAULT false,
    id_usuario integer
);


--
-- Name: liquidacao_despesas_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.liquidacao_despesas_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: liquidacao_despesas_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.liquidacao_despesas_processo_id_seq OWNED BY protocolos.liquidacao_despesas_processo.id;


--
-- Name: liquidacao_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.liquidacao_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    liqcod integer NOT NULL,
    ano_liquidacao smallint NOT NULL,
    excluido boolean DEFAULT false,
    rp boolean DEFAULT false,
    rp_processado boolean DEFAULT false
);


--
-- Name: liquidacao_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.liquidacao_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: liquidacao_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.liquidacao_processo_id_seq OWNED BY protocolos.liquidacao_processo.id;


--
-- Name: log; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.log (
    id integer NOT NULL,
    flag character varying,
    dados_enviados text,
    erro text,
    id_usuario integer,
    id_usuario_externo integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: log_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.log_id_seq OWNED BY protocolos.log.id;


--
-- Name: login; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.login (
    id integer NOT NULL,
    id_usuario integer NOT NULL,
    data_de_login timestamp without time zone NOT NULL,
    data_ultimo_acesso timestamp without time zone NOT NULL,
    id_dados_acesso integer NOT NULL
);


--
-- Name: login_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.login_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: login_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.login_id_seq OWNED BY protocolos.login.id;


--
-- Name: login_usuario_externo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.login_usuario_externo (
    id integer NOT NULL,
    id_usuario integer NOT NULL,
    data_de_login timestamp without time zone NOT NULL,
    data_ultimo_acesso timestamp without time zone NOT NULL,
    id_dados_acesso integer NOT NULL
);


--
-- Name: login_usuario_externo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.login_usuario_externo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: login_usuario_externo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.login_usuario_externo_id_seq OWNED BY protocolos.login_usuario_externo.id;


--
-- Name: lotacao; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.lotacao (
    id integer NOT NULL,
    id_unidade_trabalho integer NOT NULL,
    is_protocolo boolean DEFAULT false NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    principal boolean DEFAULT false NOT NULL,
    protocolo_central boolean DEFAULT false NOT NULL,
    coordenadoria boolean DEFAULT false,
    restrita boolean DEFAULT false,
    enviar_externo boolean DEFAULT false
);


--
-- Name: lotacao_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.lotacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lotacao_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.lotacao_id_seq OWNED BY protocolos.lotacao.id;


--
-- Name: lotacoes_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.lotacoes_spu (
    id integer NOT NULL,
    sigla character varying(255),
    nome text,
    protocolo boolean,
    lotacao_id integer,
    ativo boolean,
    tree character varying(255),
    tramitar integer,
    receber integer,
    id_unidade_trabalho_utils integer
);


--
-- Name: lotacoes_spu_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.lotacoes_spu_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lotacoes_spu_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.lotacoes_spu_id_seq OWNED BY protocolos.lotacoes_spu.id;


--
-- Name: manifestante; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.manifestante (
    id integer NOT NULL,
    id_tipo_manifestante integer NOT NULL,
    cpf_cnpj character varying(14),
    nome character varying(255),
    id_sexo integer,
    responsavel character varying(255),
    organizacao character varying(255),
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    telefone_residencial character varying(100),
    telefone_celular character varying(100),
    telefone_comercial character varying(100),
    email character varying(255),
    observacao text,
    id_usuario integer,
    id_usuario_externo integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    data_nascimento date,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.manifestante FORCE ROW LEVEL SECURITY;


--
-- Name: manifestante_aux; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.manifestante_aux (
    id integer NOT NULL,
    id_tipo_manifestante integer NOT NULL,
    cpf_cnpj character varying(14),
    nome character varying(255),
    id_sexo integer,
    responsavel character varying(255),
    organizacao character varying(255),
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    telefone_residencial character varying(100),
    telefone_celular character varying(100),
    telefone_comercial character varying(100),
    email character varying(255),
    observacao text,
    data_nascimento date,
    id_usuario integer,
    id_usuario_externo integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: manifestante_aux_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.manifestante_aux_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manifestante_aux_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.manifestante_aux_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manifestante_aux_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.manifestante_aux_id_seq1 OWNED BY protocolos.manifestante_aux.id;


--
-- Name: manifestante_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.manifestante_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manifestante_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.manifestante_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manifestante_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.manifestante_id_seq1 OWNED BY protocolos.manifestante.id;


--
-- Name: movimentacao; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.movimentacao (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_unidade_responsavel integer NOT NULL,
    id_acao integer NOT NULL,
    id_despacho integer,
    id_encaminhamento integer,
    id_arquivamento integer,
    id_usuario integer,
    id_usuario_externo integer,
    data_hora_movimentacao timestamp without time zone DEFAULT now() NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_solicitacao_assinatura integer,
    id_diligencia integer,
    id_solicitacao_avaliacao_documento integer,
    id_desentranhamento integer,
    id_usuario_assinatura integer,
    usuario_migrado character varying,
    id_usuario_spu smallint,
    id_carimbamento integer,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.movimentacao FORCE ROW LEVEL SECURITY;


--
-- Name: movimentacao_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.movimentacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: movimentacao_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.movimentacao_id_seq OWNED BY protocolos.movimentacao.id;


--
-- Name: movimentacao_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.movimentacao_spu (
    id integer NOT NULL,
    processo_id bigint,
    despacho character varying,
    data_prazo date,
    quantidade_folhas integer DEFAULT 0 NOT NULL,
    data_movimentacao timestamp without time zone,
    caixas_movimentacao_id integer,
    status_movimentacao_id integer,
    lotacao_origem_id integer,
    lotacao_destino_id integer,
    usuario_id integer,
    prioridades_movimentacao_id integer
);


--
-- Name: numero_processo; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.numero_processo
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oficio_circular; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.oficio_circular (
    id integer NOT NULL,
    id_processo_pai integer NOT NULL,
    id_processo_filho integer NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: oficio_circular_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.oficio_circular_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oficio_circular_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.oficio_circular_id_seq OWNED BY protocolos.oficio_circular.id;


--
-- Name: ordem_desentranhamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.ordem_desentranhamento (
    id integer NOT NULL,
    id_desentranhamento integer NOT NULL,
    id_processo integer NOT NULL,
    id_anexo integer NOT NULL,
    ordem integer NOT NULL,
    antigo boolean DEFAULT false NOT NULL,
    removido boolean DEFAULT false NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: ordem_desentranhamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.ordem_desentranhamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ordem_desentranhamento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.ordem_desentranhamento_id_seq OWNED BY protocolos.ordem_desentranhamento.id;


--
-- Name: perfis_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.perfis_spu (
    id integer NOT NULL,
    nome character varying,
    email_opcional character varying,
    telefone character varying,
    celular character varying,
    endereco character varying,
    cargo character varying,
    nascimento date,
    usuario_id integer
);


--
-- Name: perfis_spu_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.perfis_spu_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perfis_spu_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.perfis_spu_id_seq OWNED BY protocolos.perfis_spu.id;


--
-- Name: prioridade; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.prioridade (
    id integer NOT NULL,
    prioridade character varying(100) NOT NULL,
    fator integer NOT NULL,
    cor character varying(10) NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: prioridade_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.prioridade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prioridade_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.prioridade_id_seq OWNED BY protocolos.prioridade.id;


--
-- Name: processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.processo (
    id integer NOT NULL,
    id_assunto integer NOT NULL,
    virtual boolean DEFAULT true NOT NULL,
    data_hora_abertura timestamp without time zone DEFAULT now() NOT NULL,
    numero_origem text,
    numero_processo character varying(255) DEFAULT protocolos.gerar_numero_processo_string() NOT NULL,
    observacao text,
    id_unidade_proprietaria integer NOT NULL,
    corpo text,
    id_manifestante integer NOT NULL,
    id_incorporacao_status integer,
    id_processo_pai integer,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    publico boolean DEFAULT true NOT NULL,
    migrado boolean DEFAULT false NOT NULL,
    externo boolean DEFAULT false NOT NULL,
    id_local_atual integer,
    id_ultima_movimentacao integer,
    id_usuario integer,
    id_usuario_externo integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_usuario_externo_abertura integer,
    tenant_id integer NOT NULL,
    id_especie_documental integer,
    canal_entrada character varying(20),
    data_recepcao timestamp without time zone,
    id_ccd_classe integer,
    nup character varying(25),
    numero_sequencial_orgao integer
);

ALTER TABLE ONLY protocolos.processo FORCE ROW LEVEL SECURITY;


--
-- Name: processo_apensamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.processo_apensamento (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_processo_apensado integer NOT NULL,
    id_processo_principal integer NOT NULL,
    id_usuario integer NOT NULL,
    motivo character varying(1000) NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    desapensado_em timestamp without time zone,
    id_usuario_desapensamento integer,
    motivo_desapensamento character varying(1000),
    CONSTRAINT ck_apensamento_distintos CHECK ((id_processo_apensado <> id_processo_principal))
);

ALTER TABLE ONLY protocolos.processo_apensamento FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN processo_apensamento.id_processo_apensado; Type: COMMENT; Schema: protocolos; Owner: -
--

COMMENT ON COLUMN protocolos.processo_apensamento.id_processo_apensado IS 'Processo filho (que está sendo apensado a outro)';


--
-- Name: COLUMN processo_apensamento.id_processo_principal; Type: COMMENT; Schema: protocolos; Owner: -
--

COMMENT ON COLUMN protocolos.processo_apensamento.id_processo_principal IS 'Processo pai (recebe o apensamento)';


--
-- Name: processo_apensamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.processo_apensamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: processo_apensamento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.processo_apensamento_id_seq OWNED BY protocolos.processo_apensamento.id;


--
-- Name: processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: processo_id_seq1; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.processo_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: processo_id_seq1; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.processo_id_seq1 OWNED BY protocolos.processo.id;


--
-- Name: processo_vinculado; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.processo_vinculado (
    id integer NOT NULL,
    id_processo integer,
    id_processo_vinculado integer,
    id_movimentacao integer,
    excluido boolean DEFAULT false,
    id_usuario integer
);


--
-- Name: processo_vinculado_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.processo_vinculado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: processo_vinculado_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.processo_vinculado_id_seq OWNED BY protocolos.processo_vinculado.id;


--
-- Name: processo_volume; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.processo_volume (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_processo integer NOT NULL,
    numero integer NOT NULL,
    pagina_inicial integer,
    pagina_final integer,
    observacao character varying(500),
    id_usuario integer NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_volume_numero_positivo CHECK ((numero >= 1)),
    CONSTRAINT ck_volume_paginas_validas CHECK ((((pagina_inicial IS NULL) OR (pagina_inicial >= 1)) AND ((pagina_final IS NULL) OR (pagina_final >= pagina_inicial))))
);

ALTER TABLE ONLY protocolos.processo_volume FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN processo_volume.numero; Type: COMMENT; Schema: protocolos; Owner: -
--

COMMENT ON COLUMN protocolos.processo_volume.numero IS 'Volume N (1, 2, 3…)';


--
-- Name: processo_volume_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.processo_volume_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: processo_volume_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.processo_volume_id_seq OWNED BY protocolos.processo_volume.id;


--
-- Name: publicidade_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.publicidade_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_despacho integer NOT NULL,
    publico boolean NOT NULL,
    id_usuario integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: publicidade_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.publicidade_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: publicidade_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.publicidade_processo_id_seq OWNED BY protocolos.publicidade_processo.id;


--
-- Name: redefinicao_senha; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.redefinicao_senha (
    id integer NOT NULL,
    token character varying(255) NOT NULL,
    id_usuario integer,
    data_solicitacao timestamp without time zone DEFAULT now() NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    email character varying,
    created_at timestamp without time zone,
    id_usuario_externo integer
);


--
-- Name: redefinicao_senha_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.redefinicao_senha_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: redefinicao_senha_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.redefinicao_senha_id_seq OWNED BY protocolos.redefinicao_senha.id;


--
-- Name: responsavel_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.responsavel_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_lotacao integer NOT NULL,
    id_responsavel integer NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_movimentacao integer,
    movimentacao_id integer
);


--
-- Name: responsavel_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.responsavel_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: responsavel_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.responsavel_processo_id_seq OWNED BY protocolos.responsavel_processo.id;


--
-- Name: solicitacao_assinatura; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.solicitacao_assinatura (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_solicitante integer NOT NULL,
    realizada boolean DEFAULT false NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_unidade_solicitante integer,
    dt_inicio timestamp without time zone DEFAULT now() NOT NULL,
    dt_fim timestamp without time zone,
    cancelada boolean DEFAULT false NOT NULL,
    retomada boolean DEFAULT false NOT NULL,
    dt_retomada timestamp without time zone,
    id_usuario_retomada integer,
    id_unidade_encaminhamento integer,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.solicitacao_assinatura FORCE ROW LEVEL SECURITY;


--
-- Name: solicitacao_assinatura_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.solicitacao_assinatura_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacao_assinatura_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.solicitacao_assinatura_id_seq OWNED BY protocolos.solicitacao_assinatura.id;


--
-- Name: solicitacao_avaliacao_documento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.solicitacao_avaliacao_documento (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_solicitante integer NOT NULL,
    realizada boolean DEFAULT false NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: solicitacao_avaliacao_documento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.solicitacao_avaliacao_documento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacao_avaliacao_documento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.solicitacao_avaliacao_documento_id_seq OWNED BY protocolos.solicitacao_avaliacao_documento.id;


--
-- Name: solicitacao_pagamento_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.solicitacao_pagamento_processo (
    id integer NOT NULL,
    id_processo integer NOT NULL,
    id_solicitacao_pagamento integer NOT NULL,
    data_criacao timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    excluido boolean DEFAULT false,
    id_usuario integer,
    tipo_pagamento character varying(2)
);


--
-- Name: solicitacao_pagamento_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.solicitacao_pagamento_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacao_pagamento_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.solicitacao_pagamento_processo_id_seq OWNED BY protocolos.solicitacao_pagamento_processo.id;


--
-- Name: status_arquivamento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.status_arquivamento (
    id integer NOT NULL,
    status_arquivamento character varying(40) NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: status_arquivamento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.status_arquivamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: status_arquivamento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.status_arquivamento_id_seq OWNED BY protocolos.status_arquivamento.id;


--
-- Name: status_arquivamentos; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.status_arquivamentos (
    id integer NOT NULL,
    status_arquivamento character varying(40) NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: status_arquivamentos_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.status_arquivamentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: status_arquivamentos_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.status_arquivamentos_id_seq OWNED BY protocolos.status_arquivamentos.id;


--
-- Name: template_carimbo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.template_carimbo (
    id integer NOT NULL,
    flag character varying,
    template_html character varying NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: template_carimbo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.template_carimbo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: template_carimbo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.template_carimbo_id_seq OWNED BY protocolos.template_carimbo.id;


--
-- Name: template_carimbo_secretaria; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.template_carimbo_secretaria (
    id integer NOT NULL,
    id_template_carimbo integer NOT NULL,
    id_secretaria integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: template_carimbo_secretaria_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.template_carimbo_secretaria_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: template_carimbo_secretaria_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.template_carimbo_secretaria_id_seq OWNED BY protocolos.template_carimbo_secretaria.id;


--
-- Name: template_token; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.template_token (
    id integer NOT NULL,
    flag character varying,
    template_html character varying NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: template_token_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.template_token_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: template_token_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.template_token_id_seq OWNED BY protocolos.template_token.id;


--
-- Name: template_type_field; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.template_type_field (
    id integer NOT NULL,
    flag character varying,
    template_html character varying NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: template_type_field_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.template_type_field_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: template_type_field_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.template_type_field_id_seq OWNED BY protocolos.template_type_field.id;


--
-- Name: tipo_anexo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.tipo_anexo (
    id integer NOT NULL,
    tipo_anexo character varying(150),
    excluido boolean DEFAULT false,
    id_usuario integer,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.tipo_anexo FORCE ROW LEVEL SECURITY;


--
-- Name: tipo_anexo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.tipo_anexo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_anexo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.tipo_anexo_id_seq OWNED BY protocolos.tipo_anexo.id;


--
-- Name: tipo_assinatura; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.tipo_assinatura (
    id integer NOT NULL,
    tipo_assinatura character varying(40) NOT NULL,
    flag character varying(40),
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    assinar_documentos boolean DEFAULT false NOT NULL,
    desentranhar boolean DEFAULT false NOT NULL,
    responder_solicitacao_assinatura boolean DEFAULT false NOT NULL,
    externa boolean DEFAULT false NOT NULL
);


--
-- Name: tipo_assinatura_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.tipo_assinatura_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_assinatura_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.tipo_assinatura_id_seq OWNED BY protocolos.tipo_assinatura.id;


--
-- Name: tipo_manifestante; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.tipo_manifestante (
    id integer NOT NULL,
    tipo_manifestante character varying(150),
    id_categoria integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.tipo_manifestante FORCE ROW LEVEL SECURITY;


--
-- Name: tipo_manifestante_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.tipo_manifestante_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_manifestante_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.tipo_manifestante_id_seq OWNED BY protocolos.tipo_manifestante.id;


--
-- Name: tipo_processo; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.tipo_processo (
    id integer NOT NULL,
    tipo_processo character varying(200),
    exige_processo_pai boolean DEFAULT false NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.tipo_processo FORCE ROW LEVEL SECURITY;


--
-- Name: tipo_processo_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.tipo_processo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_processo_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.tipo_processo_id_seq OWNED BY protocolos.tipo_processo.id;


--
-- Name: ttd_regra; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.ttd_regra (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    id_ccd_classe integer NOT NULL,
    id_especie_documental integer,
    anos_corrente integer DEFAULT 0 NOT NULL,
    anos_intermediario integer DEFAULT 0 NOT NULL,
    destino_final character varying(30) NOT NULL,
    observacao character varying(1000),
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_ttd_destino_final CHECK (((destino_final)::text = ANY ((ARRAY['ELIMINACAO'::character varying, 'GUARDA_PERMANENTE'::character varying])::text[])))
);

ALTER TABLE ONLY protocolos.ttd_regra FORCE ROW LEVEL SECURITY;


--
-- Name: ttd_regra_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.ttd_regra_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ttd_regra_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.ttd_regra_id_seq OWNED BY protocolos.ttd_regra.id;


--
-- Name: unidade_padrao_liq_pag; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.unidade_padrao_liq_pag (
    id integer NOT NULL,
    id_unidade_trabalho integer NOT NULL,
    incluir_filhas boolean DEFAULT false,
    id_unidade_trabalho_destino integer NOT NULL,
    excluido boolean DEFAULT false,
    id_usuario integer,
    liquidacao boolean DEFAULT false,
    pagamento boolean DEFAULT false,
    empenho boolean DEFAULT false
);


--
-- Name: unidade_padrao_liq_pag_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.unidade_padrao_liq_pag_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unidade_padrao_liq_pag_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.unidade_padrao_liq_pag_id_seq OWNED BY protocolos.unidade_padrao_liq_pag.id;


--
-- Name: usuario_assinatura; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.usuario_assinatura (
    id integer NOT NULL,
    id_solicitacao_assinatura integer,
    id_assinante integer NOT NULL,
    id_tipo_assinatura integer,
    id_unidade_trabalho integer NOT NULL,
    realizada boolean DEFAULT false NOT NULL,
    ordem integer NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    aprovacao_pendente boolean DEFAULT false NOT NULL,
    aprovado boolean,
    id_usuario_aprovacao integer,
    negada boolean DEFAULT false NOT NULL,
    nota character varying(255),
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY protocolos.usuario_assinatura FORCE ROW LEVEL SECURITY;


--
-- Name: usuario_assinatura_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.usuario_assinatura_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_assinatura_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.usuario_assinatura_id_seq OWNED BY protocolos.usuario_assinatura.id;


--
-- Name: usuario_avaliacao_documento; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.usuario_avaliacao_documento (
    id integer NOT NULL,
    id_solicitacao_avaliacao_documento integer NOT NULL,
    id_avaliador integer NOT NULL,
    id_unidade_trabalho integer NOT NULL,
    realizada boolean DEFAULT false NOT NULL,
    ordem integer NOT NULL,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    nota text,
    id_movimentacao integer
);


--
-- Name: usuario_avaliacao_documento_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.usuario_avaliacao_documento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_avaliacao_documento_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.usuario_avaliacao_documento_id_seq OWNED BY protocolos.usuario_avaliacao_documento.id;


--
-- Name: usuarios_spu; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.usuarios_spu (
    id bigint NOT NULL,
    username character varying(255) NOT NULL,
    email character varying(255),
    grupos_usuario_id integer,
    ativo boolean DEFAULT true NOT NULL,
    id_usuario_utils integer
);


--
-- Name: vinculo_gerarprocesso_anexos; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.vinculo_gerarprocesso_anexos (
    id integer NOT NULL,
    id_geracao_processo integer NOT NULL,
    id_anexo integer NOT NULL,
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: vinculo_gerarprocesso_anexos_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.vinculo_gerarprocesso_anexos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vinculo_gerarprocesso_anexos_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.vinculo_gerarprocesso_anexos_id_seq OWNED BY protocolos.vinculo_gerarprocesso_anexos.id;


--
-- Name: volume; Type: TABLE; Schema: protocolos; Owner: -
--

CREATE TABLE protocolos.volume (
    id integer NOT NULL,
    volume character varying(255) NOT NULL,
    inicio integer,
    fim integer,
    descricao character varying(255),
    id_movimentacao integer,
    id_usuario integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: volume_id_seq; Type: SEQUENCE; Schema: protocolos; Owner: -
--

CREATE SEQUENCE protocolos.volume_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: volume_id_seq; Type: SEQUENCE OWNED BY; Schema: protocolos; Owner: -
--

ALTER SEQUENCE protocolos.volume_id_seq OWNED BY protocolos.volume.id;


--
-- Name: access_token; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.access_token (
    id integer NOT NULL,
    access_token text NOT NULL,
    id_usuario integer NOT NULL,
    data_expiracao timestamp without time zone NOT NULL,
    ativo boolean DEFAULT true,
    excluido boolean DEFAULT false
);


--
-- Name: access_token_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.access_token_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: access_token_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.access_token_id_seq OWNED BY utils.access_token.id;


--
-- Name: ano_financeiro; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.ano_financeiro (
    id integer NOT NULL,
    ano smallint,
    ativo boolean DEFAULT false,
    corrente boolean DEFAULT false,
    path_fb character varying(200),
    api_gestor character varying(200),
    porta integer,
    id_usuario integer,
    excluido boolean DEFAULT false
);


--
-- Name: ano_financeiro_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.ano_financeiro_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ano_financeiro_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.ano_financeiro_id_seq OWNED BY utils.ano_financeiro.id;


--
-- Name: arquivo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.arquivo (
    id integer NOT NULL,
    nome_do_arquivo character varying(255) NOT NULL,
    nome_real character varying(255) NOT NULL,
    data_de_upload timestamp without time zone DEFAULT now(),
    pasta character varying(255) NOT NULL,
    extensao character varying(5) NOT NULL,
    tamanho bigint,
    excluido boolean DEFAULT false NOT NULL,
    uid_origem uuid,
    app character varying(30),
    categoria character varying(20),
    uid_migracao character varying(500),
    excluido_fisicamente boolean
);


--
-- Name: arquivo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.arquivo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: arquivo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.arquivo_id_seq OWNED BY utils.arquivo.id;


--
-- Name: auditoria; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.auditoria (
    id integer NOT NULL,
    tabela character varying(128) NOT NULL,
    id_tabela integer NOT NULL,
    campo character varying(128) NOT NULL,
    valor_antigo text,
    valor_novo text,
    data timestamp without time zone NOT NULL,
    operacao character varying(2) NOT NULL,
    id_usuario integer,
    ip character varying(32),
    usuario_banco character varying(64) NOT NULL,
    pid_conexao integer NOT NULL,
    app character varying(30)
);


--
-- Name: auditoria_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.auditoria_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auditoria_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.auditoria_id_seq OWNED BY utils.auditoria.id;


--
-- Name: bairro; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.bairro (
    id bigint NOT NULL,
    id_cidade integer,
    bairro character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    ativo boolean DEFAULT true NOT NULL
);


--
-- Name: bairro_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.bairro_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bairro_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.bairro_id_seq OWNED BY utils.bairro.id;


--
-- Name: banco; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.banco (
    id integer NOT NULL,
    codigo character varying(5) NOT NULL,
    banco character varying(500) NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: banco_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.banco_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: banco_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.banco_id_seq OWNED BY utils.banco.id;


--
-- Name: calendario; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.calendario (
    mes integer NOT NULL,
    descricao character varying(100)
);


--
-- Name: cbo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.cbo (
    id integer NOT NULL,
    descricao character varying(150),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    excluido boolean DEFAULT false
);


--
-- Name: cbo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.cbo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cbo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.cbo_id_seq OWNED BY utils.cbo.id;


--
-- Name: cidade; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.cidade (
    id integer NOT NULL,
    cidade character varying(255) NOT NULL,
    id_estado integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: cidade_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.cidade_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cidade_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.cidade_id_seq OWNED BY utils.cidade.id;


--
-- Name: classificacao_zona_cnae_subgrupo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.classificacao_zona_cnae_subgrupo (
    id integer NOT NULL,
    id_zona integer NOT NULL,
    id_subgrupo integer NOT NULL,
    id_situacao integer NOT NULL,
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: classificacao_zona_cnae_subgrupo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.classificacao_zona_cnae_subgrupo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: classificacao_zona_cnae_subgrupo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.classificacao_zona_cnae_subgrupo_id_seq OWNED BY utils.classificacao_zona_cnae_subgrupo.id;


--
-- Name: cnae; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.cnae (
    id integer NOT NULL,
    subclasse character varying(100) NOT NULL,
    denominacao character varying(255) NOT NULL,
    status boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    excluido boolean DEFAULT false,
    id_subgrupo integer
);


--
-- Name: cnae_grupo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.cnae_grupo (
    id integer NOT NULL,
    grupo character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: cnae_grupo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.cnae_grupo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cnae_grupo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.cnae_grupo_id_seq OWNED BY utils.cnae_grupo.id;


--
-- Name: cnae_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.cnae_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cnae_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.cnae_id_seq OWNED BY utils.cnae.id;


--
-- Name: cnae_risco_tipos_risco_classificacoes; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.cnae_risco_tipos_risco_classificacoes (
    id integer NOT NULL,
    id_cnae integer,
    id_risco_tipos integer,
    id_risco_classificacoes integer
);


--
-- Name: cnae_risco_tipos_risco_classificacoes_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.cnae_risco_tipos_risco_classificacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cnae_risco_tipos_risco_classificacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.cnae_risco_tipos_risco_classificacoes_id_seq OWNED BY utils.cnae_risco_tipos_risco_classificacoes.id;


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ (
    id integer NOT NULL,
    id_cnae_risco_tipos_risco_classificacoes integer,
    id_perguntas_atividades_economicas integer,
    id_risco_classificacoes_nao integer,
    id_risco_classificacoes_sim integer
);


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividad_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividad_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividad_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividad_id_seq OWNED BY utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ.id;


--
-- Name: cnae_subgrupo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.cnae_subgrupo (
    id integer NOT NULL,
    id_grupo integer NOT NULL,
    subgrupo character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_cnae_subgrupo_empresasimples integer
);


--
-- Name: cnae_subgrupo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.cnae_subgrupo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cnae_subgrupo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.cnae_subgrupo_id_seq OWNED BY utils.cnae_subgrupo.id;


--
-- Name: codigo_internacional_doencas; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.codigo_internacional_doencas (
    id integer NOT NULL,
    versao character varying(8),
    codigo character varying(6),
    excluido boolean DEFAULT false,
    id_usuario integer
);


--
-- Name: codigo_internacional_doencas_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.codigo_internacional_doencas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: codigo_internacional_doencas_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.codigo_internacional_doencas_id_seq OWNED BY utils.codigo_internacional_doencas.id;


--
-- Name: comentario; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.comentario (
    id integer NOT NULL,
    comentario text NOT NULL,
    app character varying(50),
    sessao character varying(255),
    data timestamp without time zone DEFAULT now() NOT NULL,
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL,
    sistema boolean DEFAULT false NOT NULL,
    siafi_id_usuario integer,
    siafi_sessao character varying(255),
    id_empenho integer
);


--
-- Name: comentario_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.comentario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comentario_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.comentario_id_seq OWNED BY utils.comentario.id;


--
-- Name: dados_acesso; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.dados_acesso (
    id integer NOT NULL,
    ip character varying(45) NOT NULL,
    dispositivo character varying(45) NOT NULL,
    user_agent text,
    geoip json,
    excluido boolean DEFAULT false
);


--
-- Name: dados_acesso_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.dados_acesso_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dados_acesso_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.dados_acesso_id_seq OWNED BY utils.dados_acesso.id;


--
-- Name: distrito; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.distrito (
    id integer NOT NULL,
    distrito character varying(255) NOT NULL,
    id_cidade integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: distrito_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.distrito_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: distrito_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.distrito_id_seq OWNED BY utils.distrito.id;


--
-- Name: email; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.email (
    id integer NOT NULL,
    sistema character varying(30),
    email text,
    assunto character varying(400),
    mensagem text,
    result text,
    excluido boolean DEFAULT false,
    datetime timestamp without time zone DEFAULT now(),
    anexo text,
    status integer DEFAULT 1,
    data_hora_envio timestamp without time zone,
    data_hora_erro timestamp without time zone,
    enviado_por character varying(255),
    informado boolean DEFAULT false NOT NULL,
    fg_modelo boolean DEFAULT true
);


--
-- Name: COLUMN email.status; Type: COMMENT; Schema: utils; Owner: -
--

COMMENT ON COLUMN utils.email.status IS '1=CADASTRADO/2=ENVIADO COM SUCESSO/3=ERRO/4=IMPOSSIVEL_ENVIAR/5=ERRO_NOVO';


--
-- Name: email_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.email_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.email_id_seq OWNED BY utils.email.id;


--
-- Name: email_mensagem_erro; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.email_mensagem_erro (
    id integer NOT NULL,
    mensagem character varying(255) NOT NULL,
    pode_ser_enviada_novamente boolean NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    codigo character varying(255) NOT NULL,
    id_status integer
);


--
-- Name: email_mensagem_erro_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.email_mensagem_erro_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_mensagem_erro_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.email_mensagem_erro_id_seq OWNED BY utils.email_mensagem_erro.id;


--
-- Name: email_sistema; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.email_sistema (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    senha character varying(255) NOT NULL,
    app character varying(100),
    excluido boolean DEFAULT false NOT NULL,
    hierarquia integer,
    interessados json DEFAULT '{"email": ["iagofrota@sobral.ce.gov.br"]}'::json NOT NULL,
    ultimo_envio timestamp without time zone DEFAULT now() NOT NULL,
    data_hora_proximo_envio timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: email_sistema_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.email_sistema_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_sistema_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.email_sistema_id_seq OWNED BY utils.email_sistema.id;


--
-- Name: endereco; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.endereco (
    id integer NOT NULL,
    id_cidade integer,
    id_bairro bigint,
    rua character varying(255),
    numero character varying(255),
    complemento text,
    latitude numeric(11,8),
    longitude numeric(11,8),
    dados_google_maps json,
    id_usuario_auditoria integer,
    excluido boolean DEFAULT false,
    id_estado integer,
    id_distrito integer,
    uid_origem uuid,
    ponto_referencia character varying,
    local_google_maps character varying,
    localidade_distrito character varying,
    descricao character varying,
    cep character varying,
    app character varying,
    id_localidade integer,
    id_comprovante_residencia integer,
    id_pais integer,
    bairro_texto text,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.endereco FORCE ROW LEVEL SECURITY;


--
-- Name: endereco_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.endereco_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: endereco_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.endereco_id_seq OWNED BY utils.endereco.id;


--
-- Name: escolaridade; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.escolaridade (
    id integer NOT NULL,
    escolaridade character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    grauinstrucao integer
);


--
-- Name: escolaridade_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.escolaridade_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: escolaridade_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.escolaridade_id_seq OWNED BY utils.escolaridade.id;


--
-- Name: estado; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.estado (
    id integer NOT NULL,
    estado character varying(50) NOT NULL,
    uf character(2) NOT NULL,
    id_regiao integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: estado_civil; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.estado_civil (
    id integer NOT NULL,
    estado_civil character varying(255),
    excluido boolean DEFAULT false NOT NULL,
    estcod integer
);


--
-- Name: estado_civil_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.estado_civil_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: estado_civil_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.estado_civil_id_seq OWNED BY utils.estado_civil.id;


--
-- Name: estado_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.estado_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: estado_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.estado_id_seq OWNED BY utils.estado.id;


--
-- Name: fila_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.fila_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fila; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.fila (
    id integer DEFAULT nextval('utils.fila_id_seq'::regclass) NOT NULL,
    app character varying(100),
    inicio timestamp without time zone,
    fim timestamp without time zone,
    updated_at timestamp without time zone DEFAULT now(),
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: genero; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.genero (
    id integer NOT NULL,
    descricao character varying,
    excluido boolean DEFAULT false,
    tipo character varying(50)
);


--
-- Name: genero_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.genero_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: genero_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.genero_id_seq OWNED BY utils.genero.id;


--
-- Name: geolocalizacao; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.geolocalizacao (
    id integer NOT NULL,
    place_id character varying(255),
    osm_id character varying(255),
    lat_min double precision,
    lon_min double precision,
    lat_max double precision,
    lon_max double precision,
    road character varying(255),
    suburb character varying(255),
    city character varying(255),
    municipality character varying(255),
    state_district character varying(255),
    state character varying(255),
    region character varying(255),
    postcode character varying(10),
    country character varying(255),
    country_code character varying(10),
    api character varying(100) DEFAULT 'OpenStreetMap Nominatim'::character varying,
    id_usuario integer,
    excluido boolean DEFAULT false
);


--
-- Name: geolocalizacao_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.geolocalizacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: geolocalizacao_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.geolocalizacao_id_seq OWNED BY utils.geolocalizacao.id;


--
-- Name: grupo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.grupo (
    id integer NOT NULL,
    id_nivel integer NOT NULL,
    id_sistema integer NOT NULL,
    grupo character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.grupo FORCE ROW LEVEL SECURITY;


--
-- Name: grupo_externo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.grupo_externo (
    id integer NOT NULL,
    id_sistema integer,
    grupo character varying(50)
);


--
-- Name: grupo_externo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.grupo_externo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grupo_externo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.grupo_externo_id_seq OWNED BY utils.grupo_externo.id;


--
-- Name: grupo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.grupo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grupo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.grupo_id_seq OWNED BY utils.grupo.id;


--
-- Name: grupo_transacao; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.grupo_transacao (
    id integer NOT NULL,
    id_grupo integer NOT NULL,
    id_transacao integer NOT NULL,
    inserir boolean NOT NULL,
    atualizar boolean NOT NULL,
    excluir boolean NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.grupo_transacao FORCE ROW LEVEL SECURITY;


--
-- Name: grupo_transacao_externa; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.grupo_transacao_externa (
    id integer NOT NULL,
    id_grupo integer,
    id_transacao_externa integer
);


--
-- Name: grupo_transacao_externa_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.grupo_transacao_externa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grupo_transacao_externa_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.grupo_transacao_externa_id_seq OWNED BY utils.grupo_transacao_externa.id;


--
-- Name: grupo_transacao_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.grupo_transacao_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grupo_transacao_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.grupo_transacao_id_seq OWNED BY utils.grupo_transacao.id;


--
-- Name: grupo_usuario_externo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.grupo_usuario_externo (
    id integer NOT NULL,
    id_grupo integer,
    id_usuario_externo integer
);


--
-- Name: grupo_usuario_externo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.grupo_usuario_externo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grupo_usuario_externo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.grupo_usuario_externo_id_seq OWNED BY utils.grupo_usuario_externo.id;


--
-- Name: icone; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.icone (
    id integer NOT NULL,
    icone character varying NOT NULL,
    icone_url character varying NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: icone_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.icone_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: icone_id_seq1; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.icone_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: icone_id_seq1; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.icone_id_seq1 OWNED BY utils.icone.id;


--
-- Name: localidade; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.localidade (
    id integer NOT NULL,
    id_cidade integer NOT NULL,
    id_distrito integer,
    localidade character varying(255) NOT NULL,
    excluido boolean DEFAULT false
);


--
-- Name: localidade_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.localidade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: localidade_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.localidade_id_seq OWNED BY utils.localidade.id;


--
-- Name: log_api_gestor; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.log_api_gestor (
    id integer NOT NULL,
    data timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    app character varying(30),
    url character varying(200),
    porta smallint,
    metodo character varying(10),
    dados text,
    resposta text,
    sucesso boolean,
    duplicado boolean DEFAULT false
);


--
-- Name: log_api_gestor_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.log_api_gestor_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_api_gestor_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.log_api_gestor_id_seq OWNED BY utils.log_api_gestor.id;


--
-- Name: login; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.login (
    id integer NOT NULL,
    id_usuario integer NOT NULL,
    data_de_login timestamp without time zone NOT NULL,
    data_ultimo_acesso timestamp without time zone NOT NULL,
    id_dados_acesso integer NOT NULL
);


--
-- Name: login_externo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.login_externo (
    id integer NOT NULL,
    id_usuario integer NOT NULL,
    data_de_login timestamp without time zone NOT NULL,
    data_ultimo_acesso timestamp without time zone NOT NULL,
    id_dados_acesso integer NOT NULL
);


--
-- Name: login_externo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.login_externo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: login_externo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.login_externo_id_seq OWNED BY utils.login_externo.id;


--
-- Name: login_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.login_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: login_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.login_id_seq OWNED BY utils.login.id;


--
-- Name: marca_veiculo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.marca_veiculo (
    id integer NOT NULL,
    marca_veiculo character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: marca_veiculo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.marca_veiculo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: marca_veiculo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.marca_veiculo_id_seq OWNED BY utils.marca_veiculo.id;


--
-- Name: metricas; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.metricas (
    id integer NOT NULL,
    id_sistema integer,
    descricao character varying(255),
    valor character varying(30)
);


--
-- Name: metricas_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.metricas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metricas_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.metricas_id_seq OWNED BY utils.metricas.id;


--
-- Name: nivel; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.nivel (
    id integer NOT NULL,
    nivel character varying(255) NOT NULL,
    valor integer NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: nivel_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.nivel_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nivel_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.nivel_id_seq OWNED BY utils.nivel.id;


--
-- Name: pais; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.pais (
    id integer NOT NULL,
    pais character varying NOT NULL,
    excluido boolean DEFAULT false
);


--
-- Name: pais_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.pais_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pais_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.pais_id_seq OWNED BY utils.pais.id;


--
-- Name: perguntas_atividades_economicas; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.perguntas_atividades_economicas (
    id integer NOT NULL,
    numero_pergunta integer NOT NULL,
    pergunta text NOT NULL,
    id_unidade_trabalho integer,
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: perguntas_atividades_economicas_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.perguntas_atividades_economicas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perguntas_atividades_economicas_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.perguntas_atividades_economicas_id_seq OWNED BY utils.perguntas_atividades_economicas.id;


--
-- Name: perguntas_atividades_economicas_resposta; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.perguntas_atividades_economicas_resposta (
    id integer NOT NULL,
    id_perguntas_atividades_economicas integer,
    id_cnae integer,
    id_risco_tipos integer,
    numero_viabilidade character varying(30),
    resposta boolean,
    id_risco_classificacoes integer
);


--
-- Name: perguntas_atividades_economicas_resposta_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.perguntas_atividades_economicas_resposta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perguntas_atividades_economicas_resposta_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.perguntas_atividades_economicas_resposta_id_seq OWNED BY utils.perguntas_atividades_economicas_resposta.id;


--
-- Name: pessoa; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.pessoa (
    id integer NOT NULL,
    nome character varying(255) NOT NULL,
    cpf_cnpj character varying(14),
    tipo utils.tipo_pessoa NOT NULL,
    data_nascimento date,
    email character varying(255),
    senha character varying(32),
    id_usuario_auditoria integer,
    excluido boolean DEFAULT false NOT NULL,
    telefone_principal character varying(20),
    telefone_secundario character varying(20),
    data_abertura date,
    razao_social character varying(255),
    nome_fantasia character varying(255),
    cnae_primario character varying(7),
    cnae_secundario character varying(7),
    inscricao_municipal character varying(11),
    alvara_funcionamento character varying(20),
    alvara_sanitario character varying(20),
    email_contato character varying(255),
    id_arquivo_foto integer,
    validado boolean DEFAULT false,
    uid uuid DEFAULT public.uuid_generate_v4(),
    app character varying(30),
    created_at timestamp without time zone DEFAULT now(),
    rg character varying(20),
    cnh character varying(11)
);


--
-- Name: pessoa_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.pessoa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pessoa_id_seq1; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.pessoa_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pessoa_id_seq1; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.pessoa_id_seq1 OWNED BY utils.pessoa.id;


--
-- Name: raca_cor; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.raca_cor (
    id integer NOT NULL,
    raca_cor character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    funraca integer
);


--
-- Name: COLUMN raca_cor.funraca; Type: COMMENT; Schema: utils; Owner: -
--

COMMENT ON COLUMN utils.raca_cor.funraca IS 'ID do Firebird';


--
-- Name: raca_cor_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.raca_cor_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: raca_cor_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.raca_cor_id_seq OWNED BY utils.raca_cor.id;


--
-- Name: redefinicao_senha; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.redefinicao_senha (
    id integer NOT NULL,
    token character varying(255) NOT NULL,
    id_usuario integer,
    data_solicitacao timestamp without time zone DEFAULT now() NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    email character varying,
    created_at timestamp without time zone,
    id_pessoa integer
);


--
-- Name: redefinicao_senha_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.redefinicao_senha_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: redefinicao_senha_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.redefinicao_senha_id_seq OWNED BY utils.redefinicao_senha.id;


--
-- Name: regiao; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.regiao (
    id integer NOT NULL,
    regiao character varying(50) NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: regiao_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.regiao_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: regiao_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.regiao_id_seq OWNED BY utils.regiao.id;


--
-- Name: risco_classificacoes; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.risco_classificacoes (
    id integer NOT NULL,
    classificacao character varying(30) NOT NULL,
    codigo character varying(30) NOT NULL,
    cor character varying(30) NOT NULL,
    peso integer,
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: risco_classificacoes_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.risco_classificacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risco_classificacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.risco_classificacoes_id_seq OWNED BY utils.risco_classificacoes.id;


--
-- Name: risco_tipos; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.risco_tipos (
    id integer NOT NULL,
    tipo character varying(30) NOT NULL,
    codigo character varying(30) NOT NULL,
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: risco_tipos_enquadramentos; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.risco_tipos_enquadramentos (
    id integer NOT NULL,
    id_risco_tipos integer,
    descricao character varying(100),
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL,
    id_tipo_processo integer,
    id_fluxo_funcionamento integer,
    codigo character varying(100)
);


--
-- Name: risco_tipos_enquadramentos_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.risco_tipos_enquadramentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risco_tipos_enquadramentos_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.risco_tipos_enquadramentos_id_seq OWNED BY utils.risco_tipos_enquadramentos.id;


--
-- Name: risco_tipos_enquadramentos_regras; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.risco_tipos_enquadramentos_regras (
    id integer NOT NULL,
    id_risco_tipos_enquadramentos integer,
    min_baixo integer DEFAULT 0,
    max_baixo integer,
    min_medio integer DEFAULT 0,
    max_medio integer,
    min_alto integer DEFAULT 0,
    max_alto integer,
    min_dependente integer DEFAULT 0,
    max_dependente integer
);


--
-- Name: risco_tipos_enquadramentos_regras_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.risco_tipos_enquadramentos_regras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risco_tipos_enquadramentos_regras_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.risco_tipos_enquadramentos_regras_id_seq OWNED BY utils.risco_tipos_enquadramentos_regras.id;


--
-- Name: risco_tipos_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.risco_tipos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risco_tipos_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.risco_tipos_id_seq OWNED BY utils.risco_tipos.id;


--
-- Name: secretarias_terceirizados_frequencia; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.secretarias_terceirizados_frequencia (
    id integer NOT NULL,
    id_terc integer NOT NULL,
    id_freq integer NOT NULL
);


--
-- Name: secretarias_terceirizados_frequencia_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.secretarias_terceirizados_frequencia_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: secretarias_terceirizados_frequencia_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.secretarias_terceirizados_frequencia_id_seq OWNED BY utils.secretarias_terceirizados_frequencia.id;


--
-- Name: secretarias_unidade_trabalho; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.secretarias_unidade_trabalho (
    id integer NOT NULL,
    id_unidade_trabalho integer,
    id_secretaria integer,
    excluido boolean DEFAULT false NOT NULL,
    id_usuario integer
);


--
-- Name: secretarias_unidade_trabalho_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.secretarias_unidade_trabalho_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: secretarias_unidade_trabalho_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.secretarias_unidade_trabalho_id_seq OWNED BY utils.secretarias_unidade_trabalho.id;


--
-- Name: servico_app; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.servico_app (
    id integer NOT NULL,
    servico_app character varying(255) NOT NULL,
    icone character varying(500) NOT NULL,
    url character varying(500) NOT NULL,
    excluido boolean DEFAULT false,
    ordem integer,
    id_servico_principal integer,
    send_id boolean DEFAULT false
);


--
-- Name: servico_app_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.servico_app_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: servico_app_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.servico_app_id_seq OWNED BY utils.servico_app.id;


--
-- Name: servico_origem_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.servico_origem_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: servico_origem; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.servico_origem (
    id integer DEFAULT nextval('utils.servico_origem_id_seq'::regclass) NOT NULL,
    id_servico integer NOT NULL,
    origem utils.origem NOT NULL,
    id_icone integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: servico_unidade_trabalho_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.servico_unidade_trabalho_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 2147483647
    CACHE 1;


--
-- Name: servico_unidade_trabalho; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.servico_unidade_trabalho (
    id integer DEFAULT nextval('utils.servico_unidade_trabalho_id_seq'::regclass) NOT NULL,
    id_servico_origem integer NOT NULL,
    id_unidade_trabalho integer NOT NULL,
    id_tipo_servico integer,
    posicao integer,
    posicaogrupo integer,
    excluido boolean DEFAULT false
);


--
-- Name: servicos_extras_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.servicos_extras_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: servicos_extras; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.servicos_extras (
    id integer DEFAULT nextval('utils.servicos_extras_id_seq'::regclass) NOT NULL,
    url character varying NOT NULL,
    label character varying NOT NULL,
    nome character varying NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: sistema; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.sistema (
    id integer NOT NULL,
    sistema character varying(255) NOT NULL,
    app character varying(255) NOT NULL,
    url character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    icone character varying(100),
    descricao character varying(255),
    flg_publico boolean,
    login_geral boolean DEFAULT false,
    id_unidade_trabalho integer,
    link_ios character varying,
    link_android character varying,
    tipo character varying,
    flg_android boolean DEFAULT false,
    flg_ios boolean DEFAULT false,
    arquivo_manual character varying(255),
    id_gerente_sistema integer,
    data_implantacao date,
    url_hmg character varying(255),
    path_hmg character varying(255),
    path_pdc character varying(255),
    controle_acl boolean DEFAULT false,
    id_desenv_sistema integer,
    path_git character varying(255),
    callback_govbr character varying,
    callback_govbr_assinatura character varying,
    diretorio_arquivos character varying(200),
    redirect_login_usuario_externo character varying,
    callback_assinatura_assineja character varying(200),
    diretorio_arquivos_assinados character varying(200),
    em_manutencao boolean DEFAULT false,
    previsao_fim_manutencao timestamp without time zone,
    mensagem_manutencao text,
    bloquear_envio_email boolean DEFAULT false,
    contato_gerente character varying(20)
);


--
-- Name: sistema_constante; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.sistema_constante (
    id integer NOT NULL,
    id_sistema integer,
    constante character varying(255) NOT NULL,
    valor_padrao text,
    valor_producao text,
    valor_homologacao text,
    valor_desenvolvimento text,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: sistema_constante_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.sistema_constante_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sistema_constante_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.sistema_constante_id_seq OWNED BY utils.sistema_constante.id;


--
-- Name: sistema_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.sistema_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sistema_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.sistema_id_seq OWNED BY utils.sistema.id;


--
-- Name: sistema_tipo_servico_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.sistema_tipo_servico_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sistema_transacao; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.sistema_transacao (
    id integer NOT NULL,
    id_sistema integer NOT NULL,
    id_transacao integer NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: sistema_transacao_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.sistema_transacao_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sistema_transacao_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.sistema_transacao_id_seq OWNED BY utils.sistema_transacao.id;


--
-- Name: sistema_usuario; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.sistema_usuario (
    id integer NOT NULL,
    id_sistema integer NOT NULL,
    id_usuario integer NOT NULL,
    id_tipo_usuario integer NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    id_usuario_auditoria integer
);


--
-- Name: sistema_usuario_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.sistema_usuario_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sistema_usuario_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.sistema_usuario_id_seq OWNED BY utils.sistema_usuario.id;


--
-- Name: situacoes; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.situacoes (
    id integer NOT NULL,
    situacao character varying(60),
    sigla character varying(2),
    porte_minimo numeric(10,2),
    porte_maximo numeric(10,2)
);


--
-- Name: situacoes_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.situacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: situacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.situacoes_id_seq OWNED BY utils.situacoes.id;


--
-- Name: telefone; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.telefone (
    id integer NOT NULL,
    telefone character varying(20),
    descricao text,
    id_usuario integer,
    excluido boolean DEFAULT false,
    uid_origem uuid
);


--
-- Name: telefone_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.telefone_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: telefone_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.telefone_id_seq OWNED BY utils.telefone.id;


--
-- Name: tipo_de_entrada_no_pais; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tipo_de_entrada_no_pais (
    id integer NOT NULL,
    tipo_de_entrada_no_pais character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    cod_firebird integer
);


--
-- Name: tipo_de_entrada_no_pais_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tipo_de_entrada_no_pais_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_de_entrada_no_pais_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.tipo_de_entrada_no_pais_id_seq OWNED BY utils.tipo_de_entrada_no_pais.id;


--
-- Name: tipo_deficiencia; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tipo_deficiencia (
    id integer NOT NULL,
    tipo_deficiencia character varying(255) NOT NULL,
    codigo character varying(255) NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: tipo_deficiencia_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tipo_deficiencia_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_deficiencia_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.tipo_deficiencia_id_seq OWNED BY utils.tipo_deficiencia.id;


--
-- Name: tipo_logradouro_intersol; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tipo_logradouro_intersol (
    id integer NOT NULL,
    codigo character varying(3),
    tipo character varying(30),
    excluido boolean DEFAULT false
);


--
-- Name: tipo_logradouro_intersol_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tipo_logradouro_intersol_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_logradouro_intersol_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.tipo_logradouro_intersol_id_seq OWNED BY utils.tipo_logradouro_intersol.id;


--
-- Name: tipo_sanguineo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tipo_sanguineo (
    id integer NOT NULL,
    descricao character varying,
    excluido boolean DEFAULT false
);


--
-- Name: tipo_sanguineo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tipo_sanguineo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_sanguineo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.tipo_sanguineo_id_seq OWNED BY utils.tipo_sanguineo.id;


--
-- Name: tipo_servico_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tipo_servico_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_servico; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tipo_servico (
    id integer DEFAULT nextval('utils.tipo_servico_id_seq'::regclass) NOT NULL,
    tipo_servico character varying(100) NOT NULL,
    excluido boolean DEFAULT false
);


--
-- Name: tipo_unidade_trabalho; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tipo_unidade_trabalho (
    id integer NOT NULL,
    tipo_unidade_trabalho character varying NOT NULL,
    codigo character varying,
    excluido boolean DEFAULT false NOT NULL,
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.tipo_unidade_trabalho FORCE ROW LEVEL SECURITY;


--
-- Name: tipo_unidade_trabalho_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tipo_unidade_trabalho_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_unidade_trabalho_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.tipo_unidade_trabalho_id_seq OWNED BY utils.tipo_unidade_trabalho.id;


--
-- Name: tipo_usuario; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tipo_usuario (
    id integer NOT NULL,
    tipo_usuario character varying(255) NOT NULL,
    codigo character varying(40) NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: tipo_usuario_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tipo_usuario_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_usuario_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.tipo_usuario_id_seq OWNED BY utils.tipo_usuario.id;


--
-- Name: tokens_gestorws; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.tokens_gestorws (
    id integer NOT NULL,
    token character varying(60) NOT NULL,
    data_criado timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reservado boolean DEFAULT false,
    usado boolean DEFAULT false
);


--
-- Name: tokens_gestorws_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.tokens_gestorws_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tokens_gestorws_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.tokens_gestorws_id_seq OWNED BY utils.tokens_gestorws.id;


--
-- Name: transacao; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.transacao (
    id integer NOT NULL,
    transacao character varying(255) NOT NULL,
    codigo character varying(50) NOT NULL,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: transacao_externa; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.transacao_externa (
    id integer NOT NULL,
    id_sistema integer,
    codigo character varying(30),
    descricao character varying(200)
);


--
-- Name: transacao_externa_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.transacao_externa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transacao_externa_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.transacao_externa_id_seq OWNED BY utils.transacao_externa.id;


--
-- Name: transacao_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.transacao_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transacao_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.transacao_id_seq OWNED BY utils.transacao.id;


--
-- Name: unidade_trabalho; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.unidade_trabalho (
    id integer NOT NULL,
    unidade_trabalho character varying NOT NULL,
    sigla character varying,
    id_unidade_pai integer,
    id_tipo_unidade_trabalho integer,
    excluido boolean DEFAULT false NOT NULL,
    id_frequencia integer,
    cnes character varying(15),
    cep character varying(10),
    logradouro character varying(500),
    numero character varying(20),
    bairro character varying(200),
    complemento character varying(200),
    municipio integer,
    uf integer,
    telefone character varying(20),
    cnpj character varying(14),
    latitude real,
    longitude real,
    key uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    convenio_consignado boolean DEFAULT false,
    logo character varying(30),
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.unidade_trabalho FORCE ROW LEVEL SECURITY;


--
-- Name: unidade_trabalho_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.unidade_trabalho_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unidade_trabalho_id_seq1; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.unidade_trabalho_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unidade_trabalho_id_seq1; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.unidade_trabalho_id_seq1 OWNED BY utils.unidade_trabalho.id;


--
-- Name: unidade_trabalho_orgao; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.unidade_trabalho_orgao (
    id integer NOT NULL,
    id_unidade_trabalho integer NOT NULL,
    orgcod character(2) NOT NULL,
    ano numeric(4,0) NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    undunificado character varying(4)
);


--
-- Name: unidade_trabalho_orgao2_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.unidade_trabalho_orgao2_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unidade_trabalho_orgao2_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.unidade_trabalho_orgao2_id_seq OWNED BY utils.unidade_trabalho_orgao.id;


--
-- Name: usuario; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.usuario (
    id integer NOT NULL,
    nome character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    senha character varying(255) NOT NULL,
    cpf character varying(11) NOT NULL,
    data_criacao timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    id_unidade_trabalho integer,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    cargo character varying(255),
    primeira_senha boolean,
    siafi_id_usuario integer,
    siafi_nome character varying(255),
    siafi_senha character varying(255),
    siafi_id_unidade_trabalho character varying(4),
    id_usuario_auditoria integer,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    app character varying(30),
    telefone character varying,
    id_vinculo_usuario_ipe integer,
    token_usuario_google_calendar text,
    token_acesso_gmail text,
    otrs_sincronizado boolean DEFAULT false,
    flg_whatsapp boolean DEFAULT false,
    bloquear_envio_email boolean DEFAULT false,
    senha_bcrypt character varying(255),
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.usuario FORCE ROW LEVEL SECURITY;


--
-- Name: usuario_externo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.usuario_externo (
    id integer NOT NULL,
    nome character varying(100),
    senha character varying(150),
    cpf_cnpj character varying(14),
    email character varying(100),
    login_govbr boolean DEFAULT false,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    uid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    data_criacao timestamp without time zone DEFAULT now() NOT NULL,
    data_limite_ativacao timestamp without time zone,
    app character varying,
    telefone character varying(20),
    telefone_whatsapp boolean DEFAULT false,
    senha_bcrypt character varying(255),
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.usuario_externo FORCE ROW LEVEL SECURITY;


--
-- Name: usuario_externo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.usuario_externo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_externo_id_seq1; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.usuario_externo_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_externo_id_seq1; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.usuario_externo_id_seq1 OWNED BY utils.usuario_externo.id;


--
-- Name: usuario_grupo; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.usuario_grupo (
    id integer NOT NULL,
    id_usuario integer NOT NULL,
    id_grupo integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_unidade_trabalho integer,
    id_usuario_auditoria integer,
    app character varying(30),
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.usuario_grupo FORCE ROW LEVEL SECURITY;


--
-- Name: usuario_grupo_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.usuario_grupo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_grupo_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.usuario_grupo_id_seq OWNED BY utils.usuario_grupo.id;


--
-- Name: usuario_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.usuario_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_id_seq1; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.usuario_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_id_seq1; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.usuario_id_seq1 OWNED BY utils.usuario.id;


--
-- Name: usuario_unidade_trabalho; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.usuario_unidade_trabalho (
    id integer NOT NULL,
    id_usuario integer,
    id_unidade_trabalho integer,
    data timestamp without time zone DEFAULT now() NOT NULL,
    excluido boolean DEFAULT false NOT NULL,
    id_usuario_auditoria integer,
    app character varying(30),
    tenant_id integer NOT NULL
);

ALTER TABLE ONLY utils.usuario_unidade_trabalho FORCE ROW LEVEL SECURITY;


--
-- Name: usuario_unidade_trabalho_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.usuario_unidade_trabalho_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_unidade_trabalho_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.usuario_unidade_trabalho_id_seq OWNED BY utils.usuario_unidade_trabalho.id;


--
-- Name: vinculo_trabalhista; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.vinculo_trabalhista (
    id integer NOT NULL,
    vinculo_trabalhista character varying(255) NOT NULL,
    id_usuario_auditoria integer NOT NULL,
    excluido boolean DEFAULT false,
    app character varying(30)
);


--
-- Name: vinculo_trabalhista_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.vinculo_trabalhista_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vinculo_trabalhista_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.vinculo_trabalhista_id_seq OWNED BY utils.vinculo_trabalhista.id;


--
-- Name: votacao; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.votacao (
    id integer NOT NULL,
    uuid uuid DEFAULT public.uuid_generate_v4(),
    id_pergunta integer,
    nota integer,
    ip character varying(20),
    datetime timestamp without time zone DEFAULT now(),
    sessao uuid
);


--
-- Name: votacao_comentario; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.votacao_comentario (
    id integer NOT NULL,
    uuid uuid,
    comentario text,
    excluido boolean DEFAULT false,
    id_usuario integer,
    datetime timestamp without time zone DEFAULT now()
);


--
-- Name: votacao_comentario_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.votacao_comentario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: votacao_comentario_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.votacao_comentario_id_seq OWNED BY utils.votacao_comentario.id;


--
-- Name: votacao_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.votacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: votacao_id_seq1; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.votacao_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: votacao_id_seq1; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.votacao_id_seq1 OWNED BY utils.votacao.id;


--
-- Name: votacao_pergunta; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.votacao_pergunta (
    id integer NOT NULL,
    descricao character varying(200),
    app character varying,
    categoria character varying
);


--
-- Name: votacao_pergunta_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.votacao_pergunta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: votacao_pergunta_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.votacao_pergunta_id_seq OWNED BY utils.votacao_pergunta.id;


--
-- Name: vw_tokens; Type: VIEW; Schema: utils; Owner: -
--

CREATE VIEW utils.vw_tokens AS
 SELECT access_token.id,
    access_token.access_token,
    access_token.id_usuario,
    access_token.data_expiracao,
    access_token.ativo,
    access_token.excluido
   FROM utils.access_token;


--
-- Name: zona; Type: TABLE; Schema: utils; Owner: -
--

CREATE TABLE utils.zona (
    id integer NOT NULL,
    zona character varying(100),
    id_usuario integer,
    excluido boolean DEFAULT false NOT NULL
);


--
-- Name: zona_id_seq; Type: SEQUENCE; Schema: utils; Owner: -
--

CREATE SEQUENCE utils.zona_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zona_id_seq; Type: SEQUENCE OWNED BY; Schema: utils; Owner: -
--

ALTER SEQUENCE utils.zona_id_seq OWNED BY utils.zona.id;


--
-- Name: audit_log id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.audit_log ALTER COLUMN id SET DEFAULT nextval('aprimora_py.audit_log_id_seq'::regclass);


--
-- Name: job id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.job ALTER COLUMN id SET DEFAULT nextval('aprimora_py.job_id_seq'::regclass);


--
-- Name: notificacao id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao ALTER COLUMN id SET DEFAULT nextval('aprimora_py.notificacao_id_seq'::regclass);


--
-- Name: notificacao_preferencia id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao_preferencia ALTER COLUMN id SET DEFAULT nextval('aprimora_py.notificacao_preferencia_id_seq'::regclass);


--
-- Name: tenant id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tenant ALTER COLUMN id SET DEFAULT nextval('aprimora_py.tenant_id_seq'::regclass);


--
-- Name: tipo_processo_workflow id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tipo_processo_workflow ALTER COLUMN id SET DEFAULT nextval('aprimora_py.tipo_processo_workflow_id_seq'::regclass);


--
-- Name: workflow_definition id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_definition ALTER COLUMN id SET DEFAULT nextval('aprimora_py.workflow_definition_id_seq'::regclass);


--
-- Name: workflow_instance id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_instance ALTER COLUMN id SET DEFAULT nextval('aprimora_py.workflow_instance_id_seq'::regclass);


--
-- Name: workflow_sla_alerta id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_sla_alerta ALTER COLUMN id SET DEFAULT nextval('aprimora_py.workflow_sla_alerta_id_seq'::regclass);


--
-- Name: workflow_transicao_log id; Type: DEFAULT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_transicao_log ALTER COLUMN id SET DEFAULT nextval('aprimora_py.workflow_transicao_log_id_seq'::regclass);


--
-- Name: acao id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.acao ALTER COLUMN id SET DEFAULT nextval('protocolos.acao_id_seq'::regclass);


--
-- Name: acoes_privadas_movimentacao id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.acoes_privadas_movimentacao ALTER COLUMN id SET DEFAULT nextval('protocolos.acoes_privadas_movimentacao_id_seq'::regclass);


--
-- Name: alfresco_aux id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.alfresco_aux ALTER COLUMN id SET DEFAULT nextval('protocolos.alfresco_aux_id_seq'::regclass);


--
-- Name: anexo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo ALTER COLUMN id SET DEFAULT nextval('protocolos.anexo_id_seq1'::regclass);


--
-- Name: anexo_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.anexo_processo_id_seq'::regclass);


--
-- Name: arquivamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.arquivamento ALTER COLUMN id SET DEFAULT nextval('protocolos.arquivamento_id_seq'::regclass);


--
-- Name: arquivo_temporario id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.arquivo_temporario ALTER COLUMN id SET DEFAULT nextval('protocolos.arquivo_temporario_id_seq'::regclass);


--
-- Name: assinatura_anexo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assinatura_anexo ALTER COLUMN id SET DEFAULT nextval('protocolos.assinatura_anexo_id_seq1'::regclass);


--
-- Name: assinatura_avulsa id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assinatura_avulsa ALTER COLUMN id SET DEFAULT nextval('protocolos.assinatura_avulsa_id_seq1'::regclass);


--
-- Name: assistente_assinatura id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assistente_assinatura ALTER COLUMN id SET DEFAULT nextval('protocolos.assistente_assinatura_id_seq'::regclass);


--
-- Name: assunto id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto ALTER COLUMN id SET DEFAULT nextval('protocolos.assunto_id_seq'::regclass);


--
-- Name: assunto_tipo_processo_tipo_anexo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto_tipo_processo_tipo_anexo ALTER COLUMN id SET DEFAULT nextval('protocolos.assunto_tipo_processo_tipo_anexo_id_seq'::regclass);


--
-- Name: auditoria id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.auditoria ALTER COLUMN id SET DEFAULT nextval('protocolos.auditoria_id_seq'::regclass);


--
-- Name: avaliacao_anexo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.avaliacao_anexo ALTER COLUMN id SET DEFAULT nextval('protocolos.avaliacao_anexo_id_seq1'::regclass);


--
-- Name: bairros_spu id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.bairros_spu ALTER COLUMN id SET DEFAULT nextval('protocolos.bairros_spu_id_seq'::regclass);


--
-- Name: caixa id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.caixa ALTER COLUMN id SET DEFAULT nextval('protocolos.caixa_id_seq'::regclass);


--
-- Name: carimbamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.carimbamento ALTER COLUMN id SET DEFAULT nextval('protocolos.carimbamento_id_seq'::regclass);


--
-- Name: categoria id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.categoria ALTER COLUMN id SET DEFAULT nextval('protocolos.categoria_id_seq'::regclass);


--
-- Name: ccd_classe id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ccd_classe ALTER COLUMN id SET DEFAULT nextval('protocolos.ccd_classe_id_seq'::regclass);


--
-- Name: cidades_spu id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.cidades_spu ALTER COLUMN id SET DEFAULT nextval('protocolos.cidades_spu_id_seq'::regclass);


--
-- Name: copia_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.copia_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.copia_processo_id_seq'::regclass);


--
-- Name: dados_acesso id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.dados_acesso ALTER COLUMN id SET DEFAULT nextval('protocolos.dados_acesso_id_seq'::regclass);


--
-- Name: dados_manifestante_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.dados_manifestante_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.dados_manifestante_processo_id_seq'::regclass);


--
-- Name: desentranhamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.desentranhamento ALTER COLUMN id SET DEFAULT nextval('protocolos.desentranhamento_id_seq'::regclass);


--
-- Name: despacho id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.despacho ALTER COLUMN id SET DEFAULT nextval('protocolos.despacho_id_seq1'::regclass);


--
-- Name: diligencia id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.diligencia ALTER COLUMN id SET DEFAULT nextval('protocolos.diligencia_id_seq'::regclass);


--
-- Name: documento_carimbamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.documento_carimbamento ALTER COLUMN id SET DEFAULT nextval('protocolos.documento_carimbamento_id_seq'::regclass);


--
-- Name: documentos_movimentacoes_aux id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.documentos_movimentacoes_aux ALTER COLUMN id SET DEFAULT nextval('protocolos.documentos_movimentacoes_aux_id_seq'::regclass);


--
-- Name: empenho_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.empenho_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.empenho_processo_id_seq'::regclass);


--
-- Name: encaminhamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.encaminhamento ALTER COLUMN id SET DEFAULT nextval('protocolos.encaminhamento_id_seq1'::regclass);


--
-- Name: endereco_manifestante_spu id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.endereco_manifestante_spu ALTER COLUMN id SET DEFAULT nextval('protocolos.endereco_manifestante_spu_id_seq'::regclass);


--
-- Name: especie_documental id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.especie_documental ALTER COLUMN id SET DEFAULT nextval('protocolos.especie_documental_id_seq'::regclass);


--
-- Name: estados_spu id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.estados_spu ALTER COLUMN id SET DEFAULT nextval('protocolos.estados_spu_id_seq'::regclass);


--
-- Name: exclusao_anexo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.exclusao_anexo ALTER COLUMN id SET DEFAULT nextval('protocolos.exclusao_anexo_id_seq'::regclass);


--
-- Name: gerar_processo_completo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processo_completo ALTER COLUMN id SET DEFAULT nextval('protocolos.gerar_processo_completo_id_seq1'::regclass);


--
-- Name: gerar_processos_envolvido id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processos_envolvido ALTER COLUMN id SET DEFAULT nextval('protocolos.gerar_processos_envolvido_id_seq1'::regclass);


--
-- Name: hierarquia_assunto_tipo_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.hierarquia_assunto_tipo_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.hierarquia_assunto_tipo_processo_id_seq'::regclass);


--
-- Name: incorporacao id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.incorporacao ALTER COLUMN id SET DEFAULT nextval('protocolos.incorporacao_id_seq'::regclass);


--
-- Name: incorporacao_status id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.incorporacao_status ALTER COLUMN id SET DEFAULT nextval('protocolos.incorporacao_status_id_seq'::regclass);


--
-- Name: liquidacao_despesas_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.liquidacao_despesas_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.liquidacao_despesas_processo_id_seq'::regclass);


--
-- Name: liquidacao_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.liquidacao_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.liquidacao_processo_id_seq'::regclass);


--
-- Name: log id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.log ALTER COLUMN id SET DEFAULT nextval('protocolos.log_id_seq'::regclass);


--
-- Name: login id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.login ALTER COLUMN id SET DEFAULT nextval('protocolos.login_id_seq'::regclass);


--
-- Name: login_usuario_externo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.login_usuario_externo ALTER COLUMN id SET DEFAULT nextval('protocolos.login_usuario_externo_id_seq'::regclass);


--
-- Name: lotacao id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.lotacao ALTER COLUMN id SET DEFAULT nextval('protocolos.lotacao_id_seq'::regclass);


--
-- Name: lotacoes_spu id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.lotacoes_spu ALTER COLUMN id SET DEFAULT nextval('protocolos.lotacoes_spu_id_seq'::regclass);


--
-- Name: manifestante id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.manifestante ALTER COLUMN id SET DEFAULT nextval('protocolos.manifestante_id_seq1'::regclass);


--
-- Name: manifestante_aux id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.manifestante_aux ALTER COLUMN id SET DEFAULT nextval('protocolos.manifestante_aux_id_seq1'::regclass);


--
-- Name: movimentacao id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao ALTER COLUMN id SET DEFAULT nextval('protocolos.movimentacao_id_seq'::regclass);


--
-- Name: oficio_circular id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.oficio_circular ALTER COLUMN id SET DEFAULT nextval('protocolos.oficio_circular_id_seq'::regclass);


--
-- Name: ordem_desentranhamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ordem_desentranhamento ALTER COLUMN id SET DEFAULT nextval('protocolos.ordem_desentranhamento_id_seq'::regclass);


--
-- Name: perfis_spu id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.perfis_spu ALTER COLUMN id SET DEFAULT nextval('protocolos.perfis_spu_id_seq'::regclass);


--
-- Name: prioridade id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.prioridade ALTER COLUMN id SET DEFAULT nextval('protocolos.prioridade_id_seq'::regclass);


--
-- Name: processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo ALTER COLUMN id SET DEFAULT nextval('protocolos.processo_id_seq1'::regclass);


--
-- Name: processo_apensamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_apensamento ALTER COLUMN id SET DEFAULT nextval('protocolos.processo_apensamento_id_seq'::regclass);


--
-- Name: processo_vinculado id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_vinculado ALTER COLUMN id SET DEFAULT nextval('protocolos.processo_vinculado_id_seq'::regclass);


--
-- Name: processo_volume id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_volume ALTER COLUMN id SET DEFAULT nextval('protocolos.processo_volume_id_seq'::regclass);


--
-- Name: publicidade_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.publicidade_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.publicidade_processo_id_seq'::regclass);


--
-- Name: redefinicao_senha id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.redefinicao_senha ALTER COLUMN id SET DEFAULT nextval('protocolos.redefinicao_senha_id_seq'::regclass);


--
-- Name: responsavel_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.responsavel_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.responsavel_processo_id_seq'::regclass);


--
-- Name: solicitacao_assinatura id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.solicitacao_assinatura ALTER COLUMN id SET DEFAULT nextval('protocolos.solicitacao_assinatura_id_seq'::regclass);


--
-- Name: solicitacao_avaliacao_documento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.solicitacao_avaliacao_documento ALTER COLUMN id SET DEFAULT nextval('protocolos.solicitacao_avaliacao_documento_id_seq'::regclass);


--
-- Name: solicitacao_pagamento_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.solicitacao_pagamento_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.solicitacao_pagamento_processo_id_seq'::regclass);


--
-- Name: status_arquivamento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.status_arquivamento ALTER COLUMN id SET DEFAULT nextval('protocolos.status_arquivamento_id_seq'::regclass);


--
-- Name: status_arquivamentos id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.status_arquivamentos ALTER COLUMN id SET DEFAULT nextval('protocolos.status_arquivamentos_id_seq'::regclass);


--
-- Name: template_carimbo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_carimbo ALTER COLUMN id SET DEFAULT nextval('protocolos.template_carimbo_id_seq'::regclass);


--
-- Name: template_carimbo_secretaria id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_carimbo_secretaria ALTER COLUMN id SET DEFAULT nextval('protocolos.template_carimbo_secretaria_id_seq'::regclass);


--
-- Name: template_token id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_token ALTER COLUMN id SET DEFAULT nextval('protocolos.template_token_id_seq'::regclass);


--
-- Name: template_type_field id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_type_field ALTER COLUMN id SET DEFAULT nextval('protocolos.template_type_field_id_seq'::regclass);


--
-- Name: tipo_anexo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_anexo ALTER COLUMN id SET DEFAULT nextval('protocolos.tipo_anexo_id_seq'::regclass);


--
-- Name: tipo_assinatura id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_assinatura ALTER COLUMN id SET DEFAULT nextval('protocolos.tipo_assinatura_id_seq'::regclass);


--
-- Name: tipo_manifestante id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_manifestante ALTER COLUMN id SET DEFAULT nextval('protocolos.tipo_manifestante_id_seq'::regclass);


--
-- Name: tipo_processo id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_processo ALTER COLUMN id SET DEFAULT nextval('protocolos.tipo_processo_id_seq'::regclass);


--
-- Name: ttd_regra id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ttd_regra ALTER COLUMN id SET DEFAULT nextval('protocolos.ttd_regra_id_seq'::regclass);


--
-- Name: unidade_padrao_liq_pag id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.unidade_padrao_liq_pag ALTER COLUMN id SET DEFAULT nextval('protocolos.unidade_padrao_liq_pag_id_seq'::regclass);


--
-- Name: usuario_assinatura id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuario_assinatura ALTER COLUMN id SET DEFAULT nextval('protocolos.usuario_assinatura_id_seq'::regclass);


--
-- Name: usuario_avaliacao_documento id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuario_avaliacao_documento ALTER COLUMN id SET DEFAULT nextval('protocolos.usuario_avaliacao_documento_id_seq'::regclass);


--
-- Name: vinculo_gerarprocesso_anexos id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.vinculo_gerarprocesso_anexos ALTER COLUMN id SET DEFAULT nextval('protocolos.vinculo_gerarprocesso_anexos_id_seq'::regclass);


--
-- Name: volume id; Type: DEFAULT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.volume ALTER COLUMN id SET DEFAULT nextval('protocolos.volume_id_seq'::regclass);


--
-- Name: access_token id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.access_token ALTER COLUMN id SET DEFAULT nextval('utils.access_token_id_seq'::regclass);


--
-- Name: ano_financeiro id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.ano_financeiro ALTER COLUMN id SET DEFAULT nextval('utils.ano_financeiro_id_seq'::regclass);


--
-- Name: arquivo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.arquivo ALTER COLUMN id SET DEFAULT nextval('utils.arquivo_id_seq'::regclass);


--
-- Name: auditoria id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.auditoria ALTER COLUMN id SET DEFAULT nextval('utils.auditoria_id_seq'::regclass);


--
-- Name: bairro id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.bairro ALTER COLUMN id SET DEFAULT nextval('utils.bairro_id_seq'::regclass);


--
-- Name: banco id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.banco ALTER COLUMN id SET DEFAULT nextval('utils.banco_id_seq'::regclass);


--
-- Name: cbo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cbo ALTER COLUMN id SET DEFAULT nextval('utils.cbo_id_seq'::regclass);


--
-- Name: cidade id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cidade ALTER COLUMN id SET DEFAULT nextval('utils.cidade_id_seq'::regclass);


--
-- Name: classificacao_zona_cnae_subgrupo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.classificacao_zona_cnae_subgrupo ALTER COLUMN id SET DEFAULT nextval('utils.classificacao_zona_cnae_subgrupo_id_seq'::regclass);


--
-- Name: cnae id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae ALTER COLUMN id SET DEFAULT nextval('utils.cnae_id_seq'::regclass);


--
-- Name: cnae_grupo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_grupo ALTER COLUMN id SET DEFAULT nextval('utils.cnae_grupo_id_seq'::regclass);


--
-- Name: cnae_risco_tipos_risco_classificacoes id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes ALTER COLUMN id SET DEFAULT nextval('utils.cnae_risco_tipos_risco_classificacoes_id_seq'::regclass);


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ ALTER COLUMN id SET DEFAULT nextval('utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividad_id_seq'::regclass);


--
-- Name: cnae_subgrupo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_subgrupo ALTER COLUMN id SET DEFAULT nextval('utils.cnae_subgrupo_id_seq'::regclass);


--
-- Name: codigo_internacional_doencas id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.codigo_internacional_doencas ALTER COLUMN id SET DEFAULT nextval('utils.codigo_internacional_doencas_id_seq'::regclass);


--
-- Name: comentario id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.comentario ALTER COLUMN id SET DEFAULT nextval('utils.comentario_id_seq'::regclass);


--
-- Name: dados_acesso id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.dados_acesso ALTER COLUMN id SET DEFAULT nextval('utils.dados_acesso_id_seq'::regclass);


--
-- Name: distrito id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.distrito ALTER COLUMN id SET DEFAULT nextval('utils.distrito_id_seq'::regclass);


--
-- Name: email id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.email ALTER COLUMN id SET DEFAULT nextval('utils.email_id_seq'::regclass);


--
-- Name: email_mensagem_erro id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.email_mensagem_erro ALTER COLUMN id SET DEFAULT nextval('utils.email_mensagem_erro_id_seq'::regclass);


--
-- Name: email_sistema id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.email_sistema ALTER COLUMN id SET DEFAULT nextval('utils.email_sistema_id_seq'::regclass);


--
-- Name: endereco id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco ALTER COLUMN id SET DEFAULT nextval('utils.endereco_id_seq'::regclass);


--
-- Name: escolaridade id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.escolaridade ALTER COLUMN id SET DEFAULT nextval('utils.escolaridade_id_seq'::regclass);


--
-- Name: estado id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.estado ALTER COLUMN id SET DEFAULT nextval('utils.estado_id_seq'::regclass);


--
-- Name: estado_civil id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.estado_civil ALTER COLUMN id SET DEFAULT nextval('utils.estado_civil_id_seq'::regclass);


--
-- Name: genero id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.genero ALTER COLUMN id SET DEFAULT nextval('utils.genero_id_seq'::regclass);


--
-- Name: geolocalizacao id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.geolocalizacao ALTER COLUMN id SET DEFAULT nextval('utils.geolocalizacao_id_seq'::regclass);


--
-- Name: grupo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo ALTER COLUMN id SET DEFAULT nextval('utils.grupo_id_seq'::regclass);


--
-- Name: grupo_externo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_externo ALTER COLUMN id SET DEFAULT nextval('utils.grupo_externo_id_seq'::regclass);


--
-- Name: grupo_transacao id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao ALTER COLUMN id SET DEFAULT nextval('utils.grupo_transacao_id_seq'::regclass);


--
-- Name: grupo_transacao_externa id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao_externa ALTER COLUMN id SET DEFAULT nextval('utils.grupo_transacao_externa_id_seq'::regclass);


--
-- Name: grupo_usuario_externo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_usuario_externo ALTER COLUMN id SET DEFAULT nextval('utils.grupo_usuario_externo_id_seq'::regclass);


--
-- Name: icone id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.icone ALTER COLUMN id SET DEFAULT nextval('utils.icone_id_seq1'::regclass);


--
-- Name: localidade id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.localidade ALTER COLUMN id SET DEFAULT nextval('utils.localidade_id_seq'::regclass);


--
-- Name: log_api_gestor id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.log_api_gestor ALTER COLUMN id SET DEFAULT nextval('utils.log_api_gestor_id_seq'::regclass);


--
-- Name: login id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.login ALTER COLUMN id SET DEFAULT nextval('utils.login_id_seq'::regclass);


--
-- Name: login_externo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.login_externo ALTER COLUMN id SET DEFAULT nextval('utils.login_externo_id_seq'::regclass);


--
-- Name: marca_veiculo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.marca_veiculo ALTER COLUMN id SET DEFAULT nextval('utils.marca_veiculo_id_seq'::regclass);


--
-- Name: metricas id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.metricas ALTER COLUMN id SET DEFAULT nextval('utils.metricas_id_seq'::regclass);


--
-- Name: nivel id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.nivel ALTER COLUMN id SET DEFAULT nextval('utils.nivel_id_seq'::regclass);


--
-- Name: pais id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.pais ALTER COLUMN id SET DEFAULT nextval('utils.pais_id_seq'::regclass);


--
-- Name: perguntas_atividades_economicas id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas ALTER COLUMN id SET DEFAULT nextval('utils.perguntas_atividades_economicas_id_seq'::regclass);


--
-- Name: perguntas_atividades_economicas_resposta id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas_resposta ALTER COLUMN id SET DEFAULT nextval('utils.perguntas_atividades_economicas_resposta_id_seq'::regclass);


--
-- Name: pessoa id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.pessoa ALTER COLUMN id SET DEFAULT nextval('utils.pessoa_id_seq1'::regclass);


--
-- Name: raca_cor id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.raca_cor ALTER COLUMN id SET DEFAULT nextval('utils.raca_cor_id_seq'::regclass);


--
-- Name: redefinicao_senha id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.redefinicao_senha ALTER COLUMN id SET DEFAULT nextval('utils.redefinicao_senha_id_seq'::regclass);


--
-- Name: regiao id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.regiao ALTER COLUMN id SET DEFAULT nextval('utils.regiao_id_seq'::regclass);


--
-- Name: risco_classificacoes id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_classificacoes ALTER COLUMN id SET DEFAULT nextval('utils.risco_classificacoes_id_seq'::regclass);


--
-- Name: risco_tipos id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos ALTER COLUMN id SET DEFAULT nextval('utils.risco_tipos_id_seq'::regclass);


--
-- Name: risco_tipos_enquadramentos id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos_enquadramentos ALTER COLUMN id SET DEFAULT nextval('utils.risco_tipos_enquadramentos_id_seq'::regclass);


--
-- Name: risco_tipos_enquadramentos_regras id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos_enquadramentos_regras ALTER COLUMN id SET DEFAULT nextval('utils.risco_tipos_enquadramentos_regras_id_seq'::regclass);


--
-- Name: secretarias_terceirizados_frequencia id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.secretarias_terceirizados_frequencia ALTER COLUMN id SET DEFAULT nextval('utils.secretarias_terceirizados_frequencia_id_seq'::regclass);


--
-- Name: secretarias_unidade_trabalho id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.secretarias_unidade_trabalho ALTER COLUMN id SET DEFAULT nextval('utils.secretarias_unidade_trabalho_id_seq'::regclass);


--
-- Name: servico_app id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servico_app ALTER COLUMN id SET DEFAULT nextval('utils.servico_app_id_seq'::regclass);


--
-- Name: sistema id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema ALTER COLUMN id SET DEFAULT nextval('utils.sistema_id_seq'::regclass);


--
-- Name: sistema_constante id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_constante ALTER COLUMN id SET DEFAULT nextval('utils.sistema_constante_id_seq'::regclass);


--
-- Name: sistema_transacao id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_transacao ALTER COLUMN id SET DEFAULT nextval('utils.sistema_transacao_id_seq'::regclass);


--
-- Name: sistema_usuario id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_usuario ALTER COLUMN id SET DEFAULT nextval('utils.sistema_usuario_id_seq'::regclass);


--
-- Name: situacoes id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.situacoes ALTER COLUMN id SET DEFAULT nextval('utils.situacoes_id_seq'::regclass);


--
-- Name: telefone id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.telefone ALTER COLUMN id SET DEFAULT nextval('utils.telefone_id_seq'::regclass);


--
-- Name: tipo_de_entrada_no_pais id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_de_entrada_no_pais ALTER COLUMN id SET DEFAULT nextval('utils.tipo_de_entrada_no_pais_id_seq'::regclass);


--
-- Name: tipo_deficiencia id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_deficiencia ALTER COLUMN id SET DEFAULT nextval('utils.tipo_deficiencia_id_seq'::regclass);


--
-- Name: tipo_logradouro_intersol id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_logradouro_intersol ALTER COLUMN id SET DEFAULT nextval('utils.tipo_logradouro_intersol_id_seq'::regclass);


--
-- Name: tipo_sanguineo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_sanguineo ALTER COLUMN id SET DEFAULT nextval('utils.tipo_sanguineo_id_seq'::regclass);


--
-- Name: tipo_unidade_trabalho id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_unidade_trabalho ALTER COLUMN id SET DEFAULT nextval('utils.tipo_unidade_trabalho_id_seq'::regclass);


--
-- Name: tipo_usuario id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_usuario ALTER COLUMN id SET DEFAULT nextval('utils.tipo_usuario_id_seq'::regclass);


--
-- Name: tokens_gestorws id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tokens_gestorws ALTER COLUMN id SET DEFAULT nextval('utils.tokens_gestorws_id_seq'::regclass);


--
-- Name: transacao id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.transacao ALTER COLUMN id SET DEFAULT nextval('utils.transacao_id_seq'::regclass);


--
-- Name: transacao_externa id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.transacao_externa ALTER COLUMN id SET DEFAULT nextval('utils.transacao_externa_id_seq'::regclass);


--
-- Name: unidade_trabalho id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.unidade_trabalho ALTER COLUMN id SET DEFAULT nextval('utils.unidade_trabalho_id_seq1'::regclass);


--
-- Name: unidade_trabalho_orgao id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.unidade_trabalho_orgao ALTER COLUMN id SET DEFAULT nextval('utils.unidade_trabalho_orgao2_id_seq'::regclass);


--
-- Name: usuario id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario ALTER COLUMN id SET DEFAULT nextval('utils.usuario_id_seq1'::regclass);


--
-- Name: usuario_externo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_externo ALTER COLUMN id SET DEFAULT nextval('utils.usuario_externo_id_seq1'::regclass);


--
-- Name: usuario_grupo id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_grupo ALTER COLUMN id SET DEFAULT nextval('utils.usuario_grupo_id_seq'::regclass);


--
-- Name: usuario_unidade_trabalho id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_unidade_trabalho ALTER COLUMN id SET DEFAULT nextval('utils.usuario_unidade_trabalho_id_seq'::regclass);


--
-- Name: vinculo_trabalhista id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.vinculo_trabalhista ALTER COLUMN id SET DEFAULT nextval('utils.vinculo_trabalhista_id_seq'::regclass);


--
-- Name: votacao id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.votacao ALTER COLUMN id SET DEFAULT nextval('utils.votacao_id_seq1'::regclass);


--
-- Name: votacao_comentario id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.votacao_comentario ALTER COLUMN id SET DEFAULT nextval('utils.votacao_comentario_id_seq'::regclass);


--
-- Name: votacao_pergunta id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.votacao_pergunta ALTER COLUMN id SET DEFAULT nextval('utils.votacao_pergunta_id_seq'::regclass);


--
-- Name: zona id; Type: DEFAULT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.zona ALTER COLUMN id SET DEFAULT nextval('utils.zona_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: job job_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.job
    ADD CONSTRAINT job_pkey PRIMARY KEY (id);


--
-- Name: notificacao notificacao_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao
    ADD CONSTRAINT notificacao_pkey PRIMARY KEY (id);


--
-- Name: notificacao_preferencia notificacao_preferencia_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao_preferencia
    ADD CONSTRAINT notificacao_preferencia_pkey PRIMARY KEY (id);


--
-- Name: nup_sequencia pk_nup_sequencia; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.nup_sequencia
    ADD CONSTRAINT pk_nup_sequencia PRIMARY KEY (tenant_id, codigo_orgao, ano);


--
-- Name: tenant tenant_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tenant
    ADD CONSTRAINT tenant_pkey PRIMARY KEY (id);


--
-- Name: tipo_processo_workflow tipo_processo_workflow_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tipo_processo_workflow
    ADD CONSTRAINT tipo_processo_workflow_pkey PRIMARY KEY (id);


--
-- Name: tenant uq_tenant_slug; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tenant
    ADD CONSTRAINT uq_tenant_slug UNIQUE (slug);


--
-- Name: workflow_definition workflow_definition_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_definition
    ADD CONSTRAINT workflow_definition_pkey PRIMARY KEY (id);


--
-- Name: workflow_instance workflow_instance_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_instance
    ADD CONSTRAINT workflow_instance_pkey PRIMARY KEY (id);


--
-- Name: workflow_sla_alerta workflow_sla_alerta_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_sla_alerta
    ADD CONSTRAINT workflow_sla_alerta_pkey PRIMARY KEY (id);


--
-- Name: workflow_transicao_log workflow_transicao_log_pkey; Type: CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_transicao_log
    ADD CONSTRAINT workflow_transicao_log_pkey PRIMARY KEY (id);


--
-- Name: acao acao_flag_key; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.acao
    ADD CONSTRAINT acao_flag_key UNIQUE (flag);


--
-- Name: acao acao_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.acao
    ADD CONSTRAINT acao_pkey PRIMARY KEY (id);


--
-- Name: acoes_privadas_movimentacao acoes_privadas_movimentacao_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.acoes_privadas_movimentacao
    ADD CONSTRAINT acoes_privadas_movimentacao_pkey PRIMARY KEY (id);


--
-- Name: alfresco_aux alfresco_aux_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.alfresco_aux
    ADD CONSTRAINT alfresco_aux_pkey PRIMARY KEY (id);


--
-- Name: anexo anexo_e_doc_key; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo
    ADD CONSTRAINT anexo_e_doc_key UNIQUE (e_doc);


--
-- Name: anexo anexo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo
    ADD CONSTRAINT anexo_pkey PRIMARY KEY (id);


--
-- Name: anexo_processo anexo_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo_processo
    ADD CONSTRAINT anexo_processo_pkey PRIMARY KEY (id);


--
-- Name: arquivamento arquivamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.arquivamento
    ADD CONSTRAINT arquivamento_pkey PRIMARY KEY (id);


--
-- Name: assinatura_anexo assinatura_anexo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assinatura_anexo
    ADD CONSTRAINT assinatura_anexo_pkey PRIMARY KEY (id);


--
-- Name: assinatura_avulsa assinatura_avulsa_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assinatura_avulsa
    ADD CONSTRAINT assinatura_avulsa_pkey PRIMARY KEY (id);


--
-- Name: assistente_assinatura assistente_assinatura_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assistente_assinatura
    ADD CONSTRAINT assistente_assinatura_pkey PRIMARY KEY (id);


--
-- Name: assunto assunto_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto
    ADD CONSTRAINT assunto_pkey PRIMARY KEY (id);


--
-- Name: assunto_tipo_processo_tipo_anexo assunto_tipo_processo_tipo_anexo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto_tipo_processo_tipo_anexo
    ADD CONSTRAINT assunto_tipo_processo_tipo_anexo_pkey PRIMARY KEY (id);


--
-- Name: auditoria auditoria_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.auditoria
    ADD CONSTRAINT auditoria_pkey PRIMARY KEY (id);


--
-- Name: avaliacao_anexo avaliacao_anexo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.avaliacao_anexo
    ADD CONSTRAINT avaliacao_anexo_pkey PRIMARY KEY (id);


--
-- Name: bairros_spu bairros_spu_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.bairros_spu
    ADD CONSTRAINT bairros_spu_pkey PRIMARY KEY (id);


--
-- Name: caixa caixa_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.caixa
    ADD CONSTRAINT caixa_pkey PRIMARY KEY (id);


--
-- Name: carimbamento carimbamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.carimbamento
    ADD CONSTRAINT carimbamento_pkey PRIMARY KEY (id);


--
-- Name: categoria categoria_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.categoria
    ADD CONSTRAINT categoria_pkey PRIMARY KEY (id);


--
-- Name: ccd_classe ccd_classe_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ccd_classe
    ADD CONSTRAINT ccd_classe_pkey PRIMARY KEY (id);


--
-- Name: cidades_spu cidades_spu_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.cidades_spu
    ADD CONSTRAINT cidades_spu_pkey PRIMARY KEY (id);


--
-- Name: copia_processo copia_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.copia_processo
    ADD CONSTRAINT copia_processo_pkey PRIMARY KEY (id);


--
-- Name: dados_acesso dados_acesso_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.dados_acesso
    ADD CONSTRAINT dados_acesso_pkey PRIMARY KEY (id);


--
-- Name: dados_manifestante_processo dados_manifestante_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.dados_manifestante_processo
    ADD CONSTRAINT dados_manifestante_processo_pkey PRIMARY KEY (id);


--
-- Name: desentranhamento desentranhamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.desentranhamento
    ADD CONSTRAINT desentranhamento_pkey PRIMARY KEY (id);


--
-- Name: despacho despacho_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.despacho
    ADD CONSTRAINT despacho_pkey PRIMARY KEY (id);


--
-- Name: diligencia diligencia_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.diligencia
    ADD CONSTRAINT diligencia_pkey PRIMARY KEY (id);


--
-- Name: documento_carimbamento documento_carimbamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.documento_carimbamento
    ADD CONSTRAINT documento_carimbamento_pkey PRIMARY KEY (id);


--
-- Name: documentos_movimentacoes_aux documentos_movimentacoes_aux_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.documentos_movimentacoes_aux
    ADD CONSTRAINT documentos_movimentacoes_aux_pkey PRIMARY KEY (id);


--
-- Name: empenho_processo empenho_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.empenho_processo
    ADD CONSTRAINT empenho_processo_pkey PRIMARY KEY (id);


--
-- Name: encaminhamento encaminhamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.encaminhamento
    ADD CONSTRAINT encaminhamento_pkey PRIMARY KEY (id);


--
-- Name: endereco_manifestante_spu endereco_manifestante_spu_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.endereco_manifestante_spu
    ADD CONSTRAINT endereco_manifestante_spu_pkey PRIMARY KEY (id);


--
-- Name: especie_documental especie_documental_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.especie_documental
    ADD CONSTRAINT especie_documental_pkey PRIMARY KEY (id);


--
-- Name: estados_spu estados_spu_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.estados_spu
    ADD CONSTRAINT estados_spu_pkey PRIMARY KEY (id);


--
-- Name: exclusao_anexo exclusao_anexo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.exclusao_anexo
    ADD CONSTRAINT exclusao_anexo_pkey PRIMARY KEY (id);


--
-- Name: gerar_processo_completo gerar_processo_completo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processo_completo
    ADD CONSTRAINT gerar_processo_completo_pkey PRIMARY KEY (id);


--
-- Name: gerar_processos_envolvido gerar_processos_envolvido_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processos_envolvido
    ADD CONSTRAINT gerar_processos_envolvido_pkey PRIMARY KEY (id);


--
-- Name: hierarquia_assunto_tipo_processo hierarquia_assunto_tipo_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.hierarquia_assunto_tipo_processo
    ADD CONSTRAINT hierarquia_assunto_tipo_processo_pkey PRIMARY KEY (id);


--
-- Name: incorporacao incorporacao_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.incorporacao
    ADD CONSTRAINT incorporacao_pkey PRIMARY KEY (id);


--
-- Name: incorporacao_status incorporacao_status_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.incorporacao_status
    ADD CONSTRAINT incorporacao_status_pkey PRIMARY KEY (id);


--
-- Name: liquidacao_despesas_processo liquidacao_despesas_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.liquidacao_despesas_processo
    ADD CONSTRAINT liquidacao_despesas_processo_pkey PRIMARY KEY (id);


--
-- Name: liquidacao_processo liquidacao_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.liquidacao_processo
    ADD CONSTRAINT liquidacao_processo_pkey PRIMARY KEY (id);


--
-- Name: log log_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.log
    ADD CONSTRAINT log_pkey PRIMARY KEY (id);


--
-- Name: login login_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.login
    ADD CONSTRAINT login_pkey PRIMARY KEY (id);


--
-- Name: lotacao lotacao_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.lotacao
    ADD CONSTRAINT lotacao_pkey PRIMARY KEY (id);


--
-- Name: lotacoes_spu lotacoes_spu_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.lotacoes_spu
    ADD CONSTRAINT lotacoes_spu_pkey PRIMARY KEY (id);


--
-- Name: manifestante_aux manifestante_aux_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.manifestante_aux
    ADD CONSTRAINT manifestante_aux_pkey PRIMARY KEY (id);


--
-- Name: manifestante manifestante_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.manifestante
    ADD CONSTRAINT manifestante_pkey PRIMARY KEY (id);


--
-- Name: movimentacao movimentacao_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT movimentacao_pkey PRIMARY KEY (id);


--
-- Name: movimentacao_spu movimentacao_spu_id_key; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao_spu
    ADD CONSTRAINT movimentacao_spu_id_key UNIQUE (id);


--
-- Name: oficio_circular oficio_circular_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.oficio_circular
    ADD CONSTRAINT oficio_circular_pkey PRIMARY KEY (id);


--
-- Name: ordem_desentranhamento ordem_desentranhamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ordem_desentranhamento
    ADD CONSTRAINT ordem_desentranhamento_pkey PRIMARY KEY (id);


--
-- Name: perfis_spu perfis_spu_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.perfis_spu
    ADD CONSTRAINT perfis_spu_pkey PRIMARY KEY (id);


--
-- Name: arquivo_temporario pk_arquivo; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.arquivo_temporario
    ADD CONSTRAINT pk_arquivo PRIMARY KEY (id);


--
-- Name: login_usuario_externo pk_login_usuario_externo; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.login_usuario_externo
    ADD CONSTRAINT pk_login_usuario_externo PRIMARY KEY (id);


--
-- Name: prioridade prioridade_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.prioridade
    ADD CONSTRAINT prioridade_pkey PRIMARY KEY (id);


--
-- Name: processo_apensamento processo_apensamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_apensamento
    ADD CONSTRAINT processo_apensamento_pkey PRIMARY KEY (id);


--
-- Name: processo processo_numero_processo_key; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_numero_processo_key UNIQUE (numero_processo);


--
-- Name: processo processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_pkey PRIMARY KEY (id);


--
-- Name: processo_vinculado processo_vinculado_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_vinculado
    ADD CONSTRAINT processo_vinculado_pkey PRIMARY KEY (id);


--
-- Name: processo_volume processo_volume_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_volume
    ADD CONSTRAINT processo_volume_pkey PRIMARY KEY (id);


--
-- Name: publicidade_processo publicidade_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.publicidade_processo
    ADD CONSTRAINT publicidade_processo_pkey PRIMARY KEY (id);


--
-- Name: redefinicao_senha redefinicao_senha_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.redefinicao_senha
    ADD CONSTRAINT redefinicao_senha_pkey PRIMARY KEY (id);


--
-- Name: responsavel_processo responsavel_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.responsavel_processo
    ADD CONSTRAINT responsavel_processo_pkey PRIMARY KEY (id);


--
-- Name: solicitacao_assinatura solicitacao_assinatura_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.solicitacao_assinatura
    ADD CONSTRAINT solicitacao_assinatura_pkey PRIMARY KEY (id);


--
-- Name: solicitacao_avaliacao_documento solicitacao_avaliacao_documento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.solicitacao_avaliacao_documento
    ADD CONSTRAINT solicitacao_avaliacao_documento_pkey PRIMARY KEY (id);


--
-- Name: solicitacao_pagamento_processo solicitacao_pagamento_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.solicitacao_pagamento_processo
    ADD CONSTRAINT solicitacao_pagamento_processo_pkey PRIMARY KEY (id);


--
-- Name: status_arquivamento status_arquivamento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.status_arquivamento
    ADD CONSTRAINT status_arquivamento_pkey PRIMARY KEY (id);


--
-- Name: status_arquivamentos status_arquivamentos_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.status_arquivamentos
    ADD CONSTRAINT status_arquivamentos_pkey PRIMARY KEY (id);


--
-- Name: template_carimbo template_carimbo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_carimbo
    ADD CONSTRAINT template_carimbo_pkey PRIMARY KEY (id);


--
-- Name: template_carimbo_secretaria template_carimbo_secretaria_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_carimbo_secretaria
    ADD CONSTRAINT template_carimbo_secretaria_pkey PRIMARY KEY (id);


--
-- Name: template_token template_token_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_token
    ADD CONSTRAINT template_token_pkey PRIMARY KEY (id);


--
-- Name: template_type_field template_type_field_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_type_field
    ADD CONSTRAINT template_type_field_pkey PRIMARY KEY (id);


--
-- Name: tipo_anexo tipo_anexo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_anexo
    ADD CONSTRAINT tipo_anexo_pkey PRIMARY KEY (id);


--
-- Name: tipo_assinatura tipo_assinatura_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_assinatura
    ADD CONSTRAINT tipo_assinatura_pkey PRIMARY KEY (id);


--
-- Name: tipo_manifestante tipo_manifestante_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_manifestante
    ADD CONSTRAINT tipo_manifestante_pkey PRIMARY KEY (id);


--
-- Name: tipo_processo tipo_processo_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_processo
    ADD CONSTRAINT tipo_processo_pkey PRIMARY KEY (id);


--
-- Name: ttd_regra ttd_regra_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ttd_regra
    ADD CONSTRAINT ttd_regra_pkey PRIMARY KEY (id);


--
-- Name: arquivo_temporario uk_nome_real; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.arquivo_temporario
    ADD CONSTRAINT uk_nome_real UNIQUE (nome_real);


--
-- Name: unidade_padrao_liq_pag unidade_padrao_liq_pag_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.unidade_padrao_liq_pag
    ADD CONSTRAINT unidade_padrao_liq_pag_pkey PRIMARY KEY (id);


--
-- Name: ccd_classe uq_ccd_classe_tenant_codigo; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ccd_classe
    ADD CONSTRAINT uq_ccd_classe_tenant_codigo UNIQUE (tenant_id, codigo);


--
-- Name: especie_documental uq_especie_documental_tenant_flag; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.especie_documental
    ADD CONSTRAINT uq_especie_documental_tenant_flag UNIQUE (tenant_id, flag);


--
-- Name: processo_volume uq_volume_processo_numero; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_volume
    ADD CONSTRAINT uq_volume_processo_numero UNIQUE (tenant_id, id_processo, numero);


--
-- Name: usuario_assinatura usuario_assinatura_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuario_assinatura
    ADD CONSTRAINT usuario_assinatura_pkey PRIMARY KEY (id);


--
-- Name: usuario_avaliacao_documento usuario_avaliacao_documento_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuario_avaliacao_documento
    ADD CONSTRAINT usuario_avaliacao_documento_pkey PRIMARY KEY (id);


--
-- Name: usuarios_spu usuarios_spu_id_key; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuarios_spu
    ADD CONSTRAINT usuarios_spu_id_key UNIQUE (id);


--
-- Name: vinculo_gerarprocesso_anexos vinculo_gerarprocesso_anexos_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.vinculo_gerarprocesso_anexos
    ADD CONSTRAINT vinculo_gerarprocesso_anexos_pkey PRIMARY KEY (id);


--
-- Name: volume volume_pkey; Type: CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.volume
    ADD CONSTRAINT volume_pkey PRIMARY KEY (id);


--
-- Name: access_token access_token_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.access_token
    ADD CONSTRAINT access_token_pkey PRIMARY KEY (id);


--
-- Name: ano_financeiro ano_financeiro_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.ano_financeiro
    ADD CONSTRAINT ano_financeiro_pkey PRIMARY KEY (id);


--
-- Name: bairro bairro_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.bairro
    ADD CONSTRAINT bairro_pkey PRIMARY KEY (id);


--
-- Name: calendario calendario_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.calendario
    ADD CONSTRAINT calendario_pkey PRIMARY KEY (mes);


--
-- Name: cbo cbo_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cbo
    ADD CONSTRAINT cbo_pk PRIMARY KEY (id);


--
-- Name: cidade cidade_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cidade
    ADD CONSTRAINT cidade_pkey PRIMARY KEY (id);


--
-- Name: classificacao_zona_cnae_subgrupo classificacao_zona_cnae_subgrupo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.classificacao_zona_cnae_subgrupo
    ADD CONSTRAINT classificacao_zona_cnae_subgrupo_pkey PRIMARY KEY (id);


--
-- Name: cnae_grupo cnae_grupo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_grupo
    ADD CONSTRAINT cnae_grupo_pkey PRIMARY KEY (id);


--
-- Name: cnae cnae_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae
    ADD CONSTRAINT cnae_pkey PRIMARY KEY (id);


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ cnae_risco_tipos_risco_classificacoes_perguntas_atividades_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ
    ADD CONSTRAINT cnae_risco_tipos_risco_classificacoes_perguntas_atividades_pkey PRIMARY KEY (id);


--
-- Name: cnae_risco_tipos_risco_classificacoes cnae_risco_tipos_risco_classificacoes_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes
    ADD CONSTRAINT cnae_risco_tipos_risco_classificacoes_pkey PRIMARY KEY (id);


--
-- Name: cnae_subgrupo cnae_subgrupo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_subgrupo
    ADD CONSTRAINT cnae_subgrupo_pkey PRIMARY KEY (id);


--
-- Name: codigo_internacional_doencas codigo_internacional_doencas_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.codigo_internacional_doencas
    ADD CONSTRAINT codigo_internacional_doencas_pkey PRIMARY KEY (id);


--
-- Name: distrito distrito_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.distrito
    ADD CONSTRAINT distrito_pkey PRIMARY KEY (id);


--
-- Name: email_mensagem_erro email_mensagem_erro_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.email_mensagem_erro
    ADD CONSTRAINT email_mensagem_erro_pk PRIMARY KEY (id);


--
-- Name: email email_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.email
    ADD CONSTRAINT email_pkey PRIMARY KEY (id);


--
-- Name: email_sistema email_sistema_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.email_sistema
    ADD CONSTRAINT email_sistema_pk PRIMARY KEY (id);


--
-- Name: endereco endereco_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_pkey PRIMARY KEY (id);


--
-- Name: escolaridade escolaridade_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.escolaridade
    ADD CONSTRAINT escolaridade_pkey PRIMARY KEY (id);


--
-- Name: estado_civil estado_civil_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.estado_civil
    ADD CONSTRAINT estado_civil_pkey PRIMARY KEY (id);


--
-- Name: estado estado_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.estado
    ADD CONSTRAINT estado_pkey PRIMARY KEY (id);


--
-- Name: fila fila_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.fila
    ADD CONSTRAINT fila_pk PRIMARY KEY (id);


--
-- Name: genero genero_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.genero
    ADD CONSTRAINT genero_pkey PRIMARY KEY (id);


--
-- Name: geolocalizacao geolocalizacao_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.geolocalizacao
    ADD CONSTRAINT geolocalizacao_pkey PRIMARY KEY (id);


--
-- Name: grupo_externo grupo_externo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_externo
    ADD CONSTRAINT grupo_externo_pkey PRIMARY KEY (id);


--
-- Name: grupo_transacao_externa grupo_transacao_externa_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao_externa
    ADD CONSTRAINT grupo_transacao_externa_pkey PRIMARY KEY (id);


--
-- Name: grupo_usuario_externo grupo_usuario_externo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_usuario_externo
    ADD CONSTRAINT grupo_usuario_externo_pkey PRIMARY KEY (id);


--
-- Name: icone icone_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.icone
    ADD CONSTRAINT icone_pkey PRIMARY KEY (id);


--
-- Name: usuario id_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario
    ADD CONSTRAINT id_pk PRIMARY KEY (id);


--
-- Name: unidade_trabalho_orgao id_unidade_trabalho_orgao_pkey2; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.unidade_trabalho_orgao
    ADD CONSTRAINT id_unidade_trabalho_orgao_pkey2 PRIMARY KEY (id);


--
-- Name: localidade localidade_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.localidade
    ADD CONSTRAINT localidade_pkey PRIMARY KEY (id);


--
-- Name: log_api_gestor log_api_gestor_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.log_api_gestor
    ADD CONSTRAINT log_api_gestor_pkey PRIMARY KEY (id);


--
-- Name: login_externo login_externo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.login_externo
    ADD CONSTRAINT login_externo_pkey PRIMARY KEY (id);


--
-- Name: marca_veiculo marca_veiculo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.marca_veiculo
    ADD CONSTRAINT marca_veiculo_pkey PRIMARY KEY (id);


--
-- Name: metricas metricas_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.metricas
    ADD CONSTRAINT metricas_pkey PRIMARY KEY (id);


--
-- Name: pais pais_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.pais
    ADD CONSTRAINT pais_pkey PRIMARY KEY (id);


--
-- Name: perguntas_atividades_economicas perguntas_atividades_economicas_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas
    ADD CONSTRAINT perguntas_atividades_economicas_pkey PRIMARY KEY (id);


--
-- Name: perguntas_atividades_economicas_resposta perguntas_atividades_economicas_resposta_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas_resposta
    ADD CONSTRAINT perguntas_atividades_economicas_resposta_pkey PRIMARY KEY (id);


--
-- Name: perguntas_atividades_economicas_resposta perguntas_cnae_viabilidade_unique; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas_resposta
    ADD CONSTRAINT perguntas_cnae_viabilidade_unique UNIQUE (id_perguntas_atividades_economicas, id_cnae, id_risco_tipos, numero_viabilidade);


--
-- Name: pessoa pessoa_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.pessoa
    ADD CONSTRAINT pessoa_pkey PRIMARY KEY (id);


--
-- Name: arquivo pk_arquivo; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.arquivo
    ADD CONSTRAINT pk_arquivo PRIMARY KEY (id);


--
-- Name: auditoria pk_auditoria; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.auditoria
    ADD CONSTRAINT pk_auditoria PRIMARY KEY (id);


--
-- Name: banco pk_banco; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.banco
    ADD CONSTRAINT pk_banco PRIMARY KEY (id);


--
-- Name: comentario pk_comentario; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.comentario
    ADD CONSTRAINT pk_comentario PRIMARY KEY (id);


--
-- Name: dados_acesso pk_dados_acesso; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.dados_acesso
    ADD CONSTRAINT pk_dados_acesso PRIMARY KEY (id);


--
-- Name: grupo pk_grupo; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo
    ADD CONSTRAINT pk_grupo PRIMARY KEY (id);


--
-- Name: grupo_transacao pk_grupo_transacao; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao
    ADD CONSTRAINT pk_grupo_transacao PRIMARY KEY (id);


--
-- Name: servico_unidade_trabalho pk_id_servico_unidadetb; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servico_unidade_trabalho
    ADD CONSTRAINT pk_id_servico_unidadetb PRIMARY KEY (id);


--
-- Name: login pk_login; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.login
    ADD CONSTRAINT pk_login PRIMARY KEY (id);


--
-- Name: nivel pk_nivel; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.nivel
    ADD CONSTRAINT pk_nivel PRIMARY KEY (id);


--
-- Name: servico_app pk_servico_app; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servico_app
    ADD CONSTRAINT pk_servico_app PRIMARY KEY (id);


--
-- Name: sistema pk_sistema; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema
    ADD CONSTRAINT pk_sistema PRIMARY KEY (id);


--
-- Name: sistema_constante pk_sistema_constante; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_constante
    ADD CONSTRAINT pk_sistema_constante PRIMARY KEY (id);


--
-- Name: sistema_transacao pk_sistema_transacao; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_transacao
    ADD CONSTRAINT pk_sistema_transacao PRIMARY KEY (id);


--
-- Name: sistema_usuario pk_sistema_usuario; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_usuario
    ADD CONSTRAINT pk_sistema_usuario PRIMARY KEY (id);


--
-- Name: transacao pk_transacao; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.transacao
    ADD CONSTRAINT pk_transacao PRIMARY KEY (id);


--
-- Name: usuario_grupo pk_usuario_grupo; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_grupo
    ADD CONSTRAINT pk_usuario_grupo PRIMARY KEY (id);


--
-- Name: raca_cor raca_cor_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.raca_cor
    ADD CONSTRAINT raca_cor_pk PRIMARY KEY (id);


--
-- Name: redefinicao_senha redefinicao_senha_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.redefinicao_senha
    ADD CONSTRAINT redefinicao_senha_pkey PRIMARY KEY (id);


--
-- Name: regiao regiao_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.regiao
    ADD CONSTRAINT regiao_pkey PRIMARY KEY (id);


--
-- Name: risco_classificacoes risco_classificacoes_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_classificacoes
    ADD CONSTRAINT risco_classificacoes_pkey PRIMARY KEY (id);


--
-- Name: risco_tipos_enquadramentos risco_tipos_enquadramentos_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos_enquadramentos
    ADD CONSTRAINT risco_tipos_enquadramentos_pkey PRIMARY KEY (id);


--
-- Name: risco_tipos_enquadramentos_regras risco_tipos_enquadramentos_regras_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos_enquadramentos_regras
    ADD CONSTRAINT risco_tipos_enquadramentos_regras_pkey PRIMARY KEY (id);


--
-- Name: risco_tipos risco_tipos_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos
    ADD CONSTRAINT risco_tipos_pkey PRIMARY KEY (id);


--
-- Name: secretarias_terceirizados_frequencia secretarias_terceirizados_frequencia_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.secretarias_terceirizados_frequencia
    ADD CONSTRAINT secretarias_terceirizados_frequencia_pkey PRIMARY KEY (id);


--
-- Name: secretarias_unidade_trabalho secretarias_unidade_trabalho_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.secretarias_unidade_trabalho
    ADD CONSTRAINT secretarias_unidade_trabalho_pkey PRIMARY KEY (id);


--
-- Name: servico_origem servico_origem_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servico_origem
    ADD CONSTRAINT servico_origem_pkey PRIMARY KEY (id);


--
-- Name: servicos_extras servicos_extras_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servicos_extras
    ADD CONSTRAINT servicos_extras_pkey PRIMARY KEY (id);


--
-- Name: telefone telefone_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.telefone
    ADD CONSTRAINT telefone_pkey PRIMARY KEY (id);


--
-- Name: tipo_deficiencia tipo_deficiencia_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_deficiencia
    ADD CONSTRAINT tipo_deficiencia_pk PRIMARY KEY (id);


--
-- Name: tipo_logradouro_intersol tipo_logradouro_intersol_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_logradouro_intersol
    ADD CONSTRAINT tipo_logradouro_intersol_pkey PRIMARY KEY (id);


--
-- Name: tipo_servico tipo_servico_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_servico
    ADD CONSTRAINT tipo_servico_pkey PRIMARY KEY (id);


--
-- Name: tipo_sanguineo tipo_snaguineo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_sanguineo
    ADD CONSTRAINT tipo_snaguineo_pkey PRIMARY KEY (id);


--
-- Name: tipo_unidade_trabalho tipo_unidade_trabalho_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_unidade_trabalho
    ADD CONSTRAINT tipo_unidade_trabalho_pkey PRIMARY KEY (id);


--
-- Name: tipo_usuario tipo_usuario_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_usuario
    ADD CONSTRAINT tipo_usuario_pk PRIMARY KEY (id);


--
-- Name: tokens_gestorws tokens_gestorws_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tokens_gestorws
    ADD CONSTRAINT tokens_gestorws_pkey PRIMARY KEY (id);


--
-- Name: tokens_gestorws tokens_gestorws_token_key; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tokens_gestorws
    ADD CONSTRAINT tokens_gestorws_token_key UNIQUE (token);


--
-- Name: transacao_externa transacao_externa_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.transacao_externa
    ADD CONSTRAINT transacao_externa_pkey PRIMARY KEY (id);


--
-- Name: tipo_usuario uk_codigo; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_usuario
    ADD CONSTRAINT uk_codigo UNIQUE (codigo);


--
-- Name: grupo_transacao uk_grupo_transacao; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao
    ADD CONSTRAINT uk_grupo_transacao UNIQUE (id_grupo, id_transacao);


--
-- Name: arquivo uk_nome_real; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.arquivo
    ADD CONSTRAINT uk_nome_real UNIQUE (nome_real);


--
-- Name: sistema_constante uk_sistema_constante; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_constante
    ADD CONSTRAINT uk_sistema_constante UNIQUE (id_sistema, constante);


--
-- Name: sistema_transacao uk_sistema_transacao; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_transacao
    ADD CONSTRAINT uk_sistema_transacao UNIQUE (id_sistema, id_transacao);


--
-- Name: transacao uk_transacao_codigo; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.transacao
    ADD CONSTRAINT uk_transacao_codigo UNIQUE (codigo);


--
-- Name: unidade_trabalho unidade_trabalho_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.unidade_trabalho
    ADD CONSTRAINT unidade_trabalho_pkey PRIMARY KEY (id);


--
-- Name: usuario_externo usuario_externo_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_externo
    ADD CONSTRAINT usuario_externo_pkey PRIMARY KEY (id);


--
-- Name: usuario_unidade_trabalho usuario_unidade_trabalho_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_unidade_trabalho
    ADD CONSTRAINT usuario_unidade_trabalho_pk PRIMARY KEY (id);


--
-- Name: situacoes utils_situacoes_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.situacoes
    ADD CONSTRAINT utils_situacoes_pkey PRIMARY KEY (id);


--
-- Name: vinculo_trabalhista vinculo_trabalhista_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.vinculo_trabalhista
    ADD CONSTRAINT vinculo_trabalhista_pkey PRIMARY KEY (id);


--
-- Name: votacao_comentario votacao_comentario_pk; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.votacao_comentario
    ADD CONSTRAINT votacao_comentario_pk PRIMARY KEY (id);


--
-- Name: votacao_pergunta votacao_pergunta_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.votacao_pergunta
    ADD CONSTRAINT votacao_pergunta_pkey PRIMARY KEY (id);


--
-- Name: votacao votacao_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.votacao
    ADD CONSTRAINT votacao_pkey PRIMARY KEY (id);


--
-- Name: zona zona_pkey; Type: CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.zona
    ADD CONSTRAINT zona_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_log_entidade; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_audit_log_entidade ON aprimora_py.audit_log USING btree (tenant_id, entidade, id_entidade, criado_em);


--
-- Name: ix_audit_log_tenant_criado; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_audit_log_tenant_criado ON aprimora_py.audit_log USING btree (tenant_id, criado_em);


--
-- Name: ix_audit_log_usuario; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_audit_log_usuario ON aprimora_py.audit_log USING btree (tenant_id, id_usuario, criado_em);


--
-- Name: ix_job_criado_em; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_job_criado_em ON aprimora_py.job USING btree (criado_em DESC);


--
-- Name: ix_job_usuario_status; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_job_usuario_status ON aprimora_py.job USING btree (id_usuario, status);


--
-- Name: ix_notificacao_tipo_criado; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_notificacao_tipo_criado ON aprimora_py.notificacao USING btree (tenant_id, tipo, criado_em);


--
-- Name: ix_notificacao_usuario_canal_lido; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_notificacao_usuario_canal_lido ON aprimora_py.notificacao USING btree (tenant_id, id_usuario, canal, lido_em);


--
-- Name: ix_tipo_processo_workflow_tenant_tipo; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE UNIQUE INDEX ix_tipo_processo_workflow_tenant_tipo ON aprimora_py.tipo_processo_workflow USING btree (tenant_id, id_tipo_processo);


--
-- Name: ix_wf_log_instance; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_wf_log_instance ON aprimora_py.workflow_transicao_log USING btree (id_workflow_instance, executada_em);


--
-- Name: ix_workflow_definition_tenant_ativo; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_workflow_definition_tenant_ativo ON aprimora_py.workflow_definition USING btree (tenant_id, ativo);


--
-- Name: ix_workflow_definition_tenant_slug_versao; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE UNIQUE INDEX ix_workflow_definition_tenant_slug_versao ON aprimora_py.workflow_definition USING btree (tenant_id, slug, versao);


--
-- Name: ix_workflow_instance_processo_ativa; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE UNIQUE INDEX ix_workflow_instance_processo_ativa ON aprimora_py.workflow_instance USING btree (id_processo) WHERE (ativa IS TRUE);


--
-- Name: ix_workflow_instance_tenant_processo; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_workflow_instance_tenant_processo ON aprimora_py.workflow_instance USING btree (tenant_id, id_processo);


--
-- Name: ix_workflow_sla_alerta_tenant_resolvido; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE INDEX ix_workflow_sla_alerta_tenant_resolvido ON aprimora_py.workflow_sla_alerta USING btree (tenant_id, resolvido_em);


--
-- Name: uq_notificacao_preferencia_tenant_usuario; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE UNIQUE INDEX uq_notificacao_preferencia_tenant_usuario ON aprimora_py.notificacao_preferencia USING btree (tenant_id, id_usuario);


--
-- Name: uq_workflow_sla_alerta_instance_estado_ativo; Type: INDEX; Schema: aprimora_py; Owner: -
--

CREATE UNIQUE INDEX uq_workflow_sla_alerta_instance_estado_ativo ON aprimora_py.workflow_sla_alerta USING btree (id_workflow_instance, estado) WHERE (resolvido_em IS NULL);


--
-- Name: acao_acao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX acao_acao_idx ON protocolos.acao USING btree (acao);


--
-- Name: acao_exibe_unidade_destino_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX acao_exibe_unidade_destino_idx ON protocolos.acao USING btree (exibe_unidade_destino);


--
-- Name: acao_id_acao_spu_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX acao_id_acao_spu_idx ON protocolos.acao USING btree (id_acao_spu);


--
-- Name: acao_status_acao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX acao_status_acao_idx ON protocolos.acao USING btree (status_acao);


--
-- Name: acao_status_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX acao_status_movimentacao_idx ON protocolos.acao USING btree (status_movimentacao);


--
-- Name: anexo_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_ativo_idx ON protocolos.anexo USING btree (ativo);


--
-- Name: anexo_excluido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_excluido_idx ON protocolos.anexo USING btree (excluido);


--
-- Name: anexo_id_tipo_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_id_tipo_anexo_idx ON protocolos.anexo USING btree (id_tipo_anexo);


--
-- Name: anexo_id_usuario_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_id_usuario_externo_idx ON protocolos.anexo USING btree (id_usuario_externo);


--
-- Name: anexo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_id_usuario_idx ON protocolos.anexo USING btree (id_usuario);


--
-- Name: anexo_processo_anexo_herdado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_anexo_herdado_idx ON protocolos.anexo_processo USING btree (anexo_herdado);


--
-- Name: anexo_processo_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_ativo_idx ON protocolos.anexo_processo USING btree (ativo);


--
-- Name: anexo_processo_excluido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_excluido_idx ON protocolos.anexo_processo USING btree (excluido);


--
-- Name: anexo_processo_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_id_anexo_idx ON protocolos.anexo_processo USING btree (id_anexo);


--
-- Name: anexo_processo_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_id_movimentacao_idx ON protocolos.anexo_processo USING btree (id_movimentacao);


--
-- Name: anexo_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_id_processo_idx ON protocolos.anexo_processo USING btree (id_processo);


--
-- Name: anexo_processo_id_usuario_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_id_usuario_externo_idx ON protocolos.anexo_processo USING btree (id_usuario_externo);


--
-- Name: anexo_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_id_usuario_idx ON protocolos.anexo_processo USING btree (id_usuario);


--
-- Name: anexo_processo_ordem_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_processo_ordem_idx ON protocolos.anexo_processo USING btree (ordem);


--
-- Name: anexo_publico_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_publico_idx ON protocolos.anexo USING btree (publico);


--
-- Name: anexo_qtd_paginas_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX anexo_qtd_paginas_idx ON protocolos.anexo USING btree (qtd_paginas);


--
-- Name: arquivamento_id_status_arquivamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX arquivamento_id_status_arquivamento_idx ON protocolos.arquivamento USING btree (id_status_arquivamento);


--
-- Name: arquivamento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX arquivamento_id_usuario_idx ON protocolos.arquivamento USING btree (id_usuario);


--
-- Name: arquivamento_movimentacao_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX arquivamento_movimentacao_id_idx ON protocolos.arquivamento USING btree (movimentacao_id);


--
-- Name: arquivo_temporario_data_de_upload_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX arquivo_temporario_data_de_upload_idx ON protocolos.arquivo_temporario USING btree (data_de_upload);


--
-- Name: arquivo_temporario_excluido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX arquivo_temporario_excluido_idx ON protocolos.arquivo_temporario USING btree (excluido);


--
-- Name: arquivo_temporario_extensao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX arquivo_temporario_extensao_idx ON protocolos.arquivo_temporario USING btree (extensao);


--
-- Name: arquivo_temporario_nome_do_arquivo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX arquivo_temporario_nome_do_arquivo_idx ON protocolos.arquivo_temporario USING btree (nome_do_arquivo);


--
-- Name: assinatura_anexo_assinado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assinatura_anexo_assinado_idx ON protocolos.assinatura_anexo USING btree (assinado);


--
-- Name: assinatura_anexo_dt_assinatura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assinatura_anexo_dt_assinatura_idx ON protocolos.assinatura_anexo USING btree (dt_assinatura);


--
-- Name: assinatura_anexo_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assinatura_anexo_id_anexo_idx ON protocolos.assinatura_anexo USING btree (id_anexo);


--
-- Name: assinatura_anexo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assinatura_anexo_id_processo_idx ON protocolos.assinatura_anexo USING btree (id_processo);


--
-- Name: assinatura_anexo_id_usuario_assinatura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assinatura_anexo_id_usuario_assinatura_idx ON protocolos.assinatura_anexo USING btree (id_usuario_assinatura);


--
-- Name: assinatura_anexo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assinatura_anexo_id_usuario_idx ON protocolos.assinatura_anexo USING btree (id_usuario);


--
-- Name: assistente_assinatura_id_assistente_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assistente_assinatura_id_assistente_idx ON protocolos.assistente_assinatura USING btree (id_assistente);


--
-- Name: assistente_assinatura_id_gerente_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assistente_assinatura_id_gerente_idx ON protocolos.assistente_assinatura USING btree (id_gerente);


--
-- Name: assistente_assinatura_id_unidade_trabalho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assistente_assinatura_id_unidade_trabalho_idx ON protocolos.assistente_assinatura USING btree (id_unidade_trabalho);


--
-- Name: assistente_assinatura_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assistente_assinatura_id_usuario_idx ON protocolos.assistente_assinatura USING btree (id_usuario);


--
-- Name: assunto_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_ativo_idx ON protocolos.assunto USING btree (ativo);


--
-- Name: assunto_dados_liquidacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_dados_liquidacao_idx ON protocolos.assunto USING btree (dados_liquidacao);


--
-- Name: assunto_exige_processo_pai_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_exige_processo_pai_idx ON protocolos.assunto USING btree (exige_processo_pai);


--
-- Name: assunto_fluxo_despesa_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_fluxo_despesa_idx ON protocolos.assunto USING btree (fluxo_despesa);


--
-- Name: assunto_id_tipo_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_id_tipo_processo_idx ON protocolos.assunto USING btree (id_tipo_processo);


--
-- Name: assunto_tipo_processo_tipo_anexo_id_assunto_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_tipo_processo_tipo_anexo_id_assunto_idx ON protocolos.assunto_tipo_processo_tipo_anexo USING btree (id_assunto);


--
-- Name: assunto_tipo_processo_tipo_anexo_id_tipo_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_tipo_processo_tipo_anexo_id_tipo_anexo_idx ON protocolos.assunto_tipo_processo_tipo_anexo USING btree (id_tipo_anexo);


--
-- Name: assunto_tipo_processo_tipo_anexo_id_tipo_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_tipo_processo_tipo_anexo_id_tipo_processo_idx ON protocolos.assunto_tipo_processo_tipo_anexo USING btree (id_tipo_processo);


--
-- Name: assunto_tipo_processo_tipo_anexo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_tipo_processo_tipo_anexo_id_usuario_idx ON protocolos.assunto_tipo_processo_tipo_anexo USING btree (id_usuario);


--
-- Name: assunto_tipo_processo_tipo_anexo_obrigatorio_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX assunto_tipo_processo_tipo_anexo_obrigatorio_idx ON protocolos.assunto_tipo_processo_tipo_anexo USING btree (obrigatorio);


--
-- Name: auditoria_data_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_data_idx ON protocolos.auditoria USING btree (data);


--
-- Name: auditoria_id_tabela_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_id_tabela_idx ON protocolos.auditoria USING btree (id_tabela);


--
-- Name: auditoria_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_id_usuario_idx ON protocolos.auditoria USING btree (id_usuario);


--
-- Name: auditoria_ip_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_ip_idx ON protocolos.auditoria USING btree (ip);


--
-- Name: auditoria_pid_conexao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_pid_conexao_idx ON protocolos.auditoria USING btree (pid_conexao);


--
-- Name: auditoria_usuario_banco_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_usuario_banco_idx ON protocolos.auditoria USING btree (usuario_banco);


--
-- Name: auditoria_valor_antigo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_valor_antigo_idx ON protocolos.auditoria USING btree (valor_antigo);


--
-- Name: auditoria_valor_novo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX auditoria_valor_novo_idx ON protocolos.auditoria USING btree (valor_novo);


--
-- Name: avaliacao_anexo_aprovado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX avaliacao_anexo_aprovado_idx ON protocolos.avaliacao_anexo USING btree (aprovado);


--
-- Name: avaliacao_anexo_data_hora_realizado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX avaliacao_anexo_data_hora_realizado_idx ON protocolos.avaliacao_anexo USING btree (data_hora_realizado);


--
-- Name: avaliacao_anexo_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX avaliacao_anexo_id_anexo_idx ON protocolos.avaliacao_anexo USING btree (id_anexo);


--
-- Name: avaliacao_anexo_id_usuario_avaliacao_documento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX avaliacao_anexo_id_usuario_avaliacao_documento_idx ON protocolos.avaliacao_anexo USING btree (id_usuario_avaliacao_documento);


--
-- Name: avaliacao_anexo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX avaliacao_anexo_id_usuario_idx ON protocolos.avaliacao_anexo USING btree (id_usuario);


--
-- Name: caixa_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX caixa_ativo_idx ON protocolos.caixa USING btree (ativo);


--
-- Name: caixa_caixa_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX caixa_caixa_idx ON protocolos.caixa USING btree (caixa);


--
-- Name: caixa_flag_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX caixa_flag_idx ON protocolos.caixa USING btree (flag);


--
-- Name: carimbamento_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX carimbamento_id_movimentacao_idx ON protocolos.carimbamento USING btree (id_movimentacao);


--
-- Name: carimbamento_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX carimbamento_id_processo_idx ON protocolos.carimbamento USING btree (id_processo);


--
-- Name: carimbamento_id_template_carimbo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX carimbamento_id_template_carimbo_idx ON protocolos.carimbamento USING btree (id_template_carimbo);


--
-- Name: carimbamento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX carimbamento_id_usuario_idx ON protocolos.carimbamento USING btree (id_usuario);


--
-- Name: categoria_categoria_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX categoria_categoria_idx ON protocolos.categoria USING btree (categoria);


--
-- Name: categoria_tipo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX categoria_tipo_idx ON protocolos.categoria USING btree (tipo);


--
-- Name: copia_processo_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX copia_processo_ativo_idx ON protocolos.copia_processo USING btree (ativo);


--
-- Name: copia_processo_created_at_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX copia_processo_created_at_idx ON protocolos.copia_processo USING btree (created_at);


--
-- Name: copia_processo_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX copia_processo_id_movimentacao_idx ON protocolos.copia_processo USING btree (id_movimentacao);


--
-- Name: copia_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX copia_processo_id_processo_idx ON protocolos.copia_processo USING btree (id_processo);


--
-- Name: copia_processo_id_unidade_destino_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX copia_processo_id_unidade_destino_idx ON protocolos.copia_processo USING btree (id_unidade_destino);


--
-- Name: copia_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX copia_processo_id_usuario_idx ON protocolos.copia_processo USING btree (id_usuario);


--
-- Name: dados_acesso_dispositivo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX dados_acesso_dispositivo_idx ON protocolos.dados_acesso USING btree (dispositivo);


--
-- Name: dados_acesso_ip_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX dados_acesso_ip_idx ON protocolos.dados_acesso USING btree (ip);


--
-- Name: dados_manifestante_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX dados_manifestante_processo_id_processo_idx ON protocolos.dados_manifestante_processo USING btree (id_processo);


--
-- Name: dados_manifestante_processo_id_usuario_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX dados_manifestante_processo_id_usuario_externo_idx ON protocolos.dados_manifestante_processo USING btree (id_usuario_externo);


--
-- Name: dados_manifestante_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX dados_manifestante_processo_id_usuario_idx ON protocolos.dados_manifestante_processo USING btree (id_usuario);


--
-- Name: desentranhamento_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX desentranhamento_ativo_idx ON protocolos.desentranhamento USING btree (ativo);


--
-- Name: desentranhamento_id_ficha_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX desentranhamento_id_ficha_anexo_idx ON protocolos.desentranhamento USING btree (id_ficha_anexo);


--
-- Name: desentranhamento_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX desentranhamento_id_processo_idx ON protocolos.desentranhamento USING btree (id_processo);


--
-- Name: desentranhamento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX desentranhamento_id_usuario_idx ON protocolos.desentranhamento USING btree (id_usuario);


--
-- Name: despacho_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX despacho_ativo_idx ON protocolos.despacho USING btree (ativo);


--
-- Name: despacho_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX despacho_id_movimentacao_idx ON protocolos.despacho USING btree (id_movimentacao);


--
-- Name: despacho_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX despacho_id_processo_idx ON protocolos.despacho USING btree (id_processo);


--
-- Name: despacho_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX despacho_id_usuario_idx ON protocolos.despacho USING btree (id_usuario);


--
-- Name: diligencia_dt_respondida_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX diligencia_dt_respondida_idx ON protocolos.diligencia USING btree (dt_respondida);


--
-- Name: diligencia_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX diligencia_id_processo_idx ON protocolos.diligencia USING btree (id_processo);


--
-- Name: diligencia_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX diligencia_id_usuario_idx ON protocolos.diligencia USING btree (id_usuario);


--
-- Name: documento_carimbamento_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_ativo_idx ON protocolos.documento_carimbamento USING btree (ativo);


--
-- Name: documento_carimbamento_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_id_anexo_idx ON protocolos.documento_carimbamento USING btree (id_anexo);


--
-- Name: documento_carimbamento_id_carimbamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_id_carimbamento_idx ON protocolos.documento_carimbamento USING btree (id_carimbamento);


--
-- Name: documento_carimbamento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_id_usuario_idx ON protocolos.documento_carimbamento USING btree (id_usuario);


--
-- Name: documento_carimbamento_scroll_to_x_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_scroll_to_x_idx ON protocolos.documento_carimbamento USING btree (scroll_to_x);


--
-- Name: documento_carimbamento_scroll_to_y_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_scroll_to_y_idx ON protocolos.documento_carimbamento USING btree (scroll_to_y);


--
-- Name: documento_carimbamento_x_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_x_idx ON protocolos.documento_carimbamento USING btree (x);


--
-- Name: documento_carimbamento_y_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documento_carimbamento_y_idx ON protocolos.documento_carimbamento USING btree (y);


--
-- Name: documentos_movimentacoes_aux_created_at_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documentos_movimentacoes_aux_created_at_idx ON protocolos.documentos_movimentacoes_aux USING btree (created_at);


--
-- Name: documentos_movimentacoes_aux_lotacao_origem_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documentos_movimentacoes_aux_lotacao_origem_id_idx ON protocolos.documentos_movimentacoes_aux USING btree (lotacao_origem_id);


--
-- Name: documentos_movimentacoes_aux_movimentacao_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documentos_movimentacoes_aux_movimentacao_id_idx ON protocolos.documentos_movimentacoes_aux USING btree (movimentacao_id);


--
-- Name: documentos_movimentacoes_aux_nome_arquivo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documentos_movimentacoes_aux_nome_arquivo_idx ON protocolos.documentos_movimentacoes_aux USING btree (nome_arquivo);


--
-- Name: documentos_movimentacoes_aux_processo_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX documentos_movimentacoes_aux_processo_id_idx ON protocolos.documentos_movimentacoes_aux USING btree (processo_id);


--
-- Name: empenho_processo_ctrcod_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_ctrcod_idx ON protocolos.empenho_processo USING btree (ctrcod);


--
-- Name: empenho_processo_data_criacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_data_criacao_idx ON protocolos.empenho_processo USING btree (data_criacao);


--
-- Name: empenho_processo_excluido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_excluido_idx ON protocolos.empenho_processo USING btree (excluido);


--
-- Name: empenho_processo_herdado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_herdado_idx ON protocolos.empenho_processo USING btree (herdado);


--
-- Name: empenho_processo_id_empenho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_id_empenho_idx ON protocolos.empenho_processo USING btree (id_empenho);


--
-- Name: empenho_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_id_processo_idx ON protocolos.empenho_processo USING btree (id_processo);


--
-- Name: empenho_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_id_usuario_idx ON protocolos.empenho_processo USING btree (id_usuario);


--
-- Name: empenho_processo_liccod_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX empenho_processo_liccod_idx ON protocolos.empenho_processo USING btree (liccod);


--
-- Name: encaminhamento_data_hora_recebimento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_data_hora_recebimento_idx ON protocolos.encaminhamento USING btree (data_hora_recebimento);


--
-- Name: encaminhamento_data_prazo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_data_prazo_idx ON protocolos.encaminhamento USING btree (data_prazo);


--
-- Name: encaminhamento_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_externo_idx ON protocolos.encaminhamento USING btree (externo);


--
-- Name: encaminhamento_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_id_movimentacao_idx ON protocolos.encaminhamento USING btree (id_movimentacao);


--
-- Name: encaminhamento_id_prioridade_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_id_prioridade_idx ON protocolos.encaminhamento USING btree (id_prioridade);


--
-- Name: encaminhamento_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_id_processo_idx ON protocolos.encaminhamento USING btree (id_processo);


--
-- Name: encaminhamento_id_unidade_destino_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_id_unidade_destino_idx ON protocolos.encaminhamento USING btree (id_unidade_destino);


--
-- Name: encaminhamento_id_unidade_origem_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_id_unidade_origem_idx ON protocolos.encaminhamento USING btree (id_unidade_origem);


--
-- Name: encaminhamento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_id_usuario_idx ON protocolos.encaminhamento USING btree (id_usuario);


--
-- Name: encaminhamento_id_usuario_recebimento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_id_usuario_recebimento_idx ON protocolos.encaminhamento USING btree (id_usuario_recebimento);


--
-- Name: encaminhamento_quantidade_folhas_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_quantidade_folhas_idx ON protocolos.encaminhamento USING btree (quantidade_folhas);


--
-- Name: encaminhamento_recebido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX encaminhamento_recebido_idx ON protocolos.encaminhamento USING btree (recebido);


--
-- Name: endereco_manifestante_spu_id_bairro_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX endereco_manifestante_spu_id_bairro_idx ON protocolos.endereco_manifestante_spu USING btree (id_bairro);


--
-- Name: endereco_manifestante_spu_id_cidade_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX endereco_manifestante_spu_id_cidade_idx ON protocolos.endereco_manifestante_spu USING btree (id_cidade);


--
-- Name: endereco_manifestante_spu_id_estado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX endereco_manifestante_spu_id_estado_idx ON protocolos.endereco_manifestante_spu USING btree (id_estado);


--
-- Name: endereco_manifestante_spu_id_manifestante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX endereco_manifestante_spu_id_manifestante_idx ON protocolos.endereco_manifestante_spu USING btree (id_manifestante);


--
-- Name: estados_spu_id_estado_utils_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX estados_spu_id_estado_utils_idx ON protocolos.estados_spu USING btree (id_estado_utils);


--
-- Name: estados_spu_nome_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX estados_spu_nome_idx ON protocolos.estados_spu USING btree (nome);


--
-- Name: estados_spu_sigla_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX estados_spu_sigla_idx ON protocolos.estados_spu USING btree (sigla);


--
-- Name: exclusao_anexo_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX exclusao_anexo_ativo_idx ON protocolos.exclusao_anexo USING btree (ativo);


--
-- Name: exclusao_anexo_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX exclusao_anexo_id_anexo_idx ON protocolos.exclusao_anexo USING btree (id_anexo);


--
-- Name: exclusao_anexo_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX exclusao_anexo_id_movimentacao_idx ON protocolos.exclusao_anexo USING btree (id_movimentacao);


--
-- Name: exclusao_anexo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX exclusao_anexo_id_processo_idx ON protocolos.exclusao_anexo USING btree (id_processo);


--
-- Name: exclusao_anexo_id_usuario_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX exclusao_anexo_id_usuario_externo_idx ON protocolos.exclusao_anexo USING btree (id_usuario_externo);


--
-- Name: exclusao_anexo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX exclusao_anexo_id_usuario_idx ON protocolos.exclusao_anexo USING btree (id_usuario);


--
-- Name: gerar_processo_completo_data_fim_geracao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_data_fim_geracao_idx ON protocolos.gerar_processo_completo USING btree (data_fim_geracao);


--
-- Name: gerar_processo_completo_data_ini_geracao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_data_ini_geracao_idx ON protocolos.gerar_processo_completo USING btree (data_ini_geracao);


--
-- Name: gerar_processo_completo_data_solicitacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_data_solicitacao_idx ON protocolos.gerar_processo_completo USING btree (data_solicitacao);


--
-- Name: gerar_processo_completo_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_id_anexo_idx ON protocolos.gerar_processo_completo USING btree (id_anexo);


--
-- Name: gerar_processo_completo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_id_processo_idx ON protocolos.gerar_processo_completo USING btree (id_processo);


--
-- Name: gerar_processo_completo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_id_usuario_idx ON protocolos.gerar_processo_completo USING btree (id_usuario);


--
-- Name: gerar_processo_completo_status_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_status_idx ON protocolos.gerar_processo_completo USING btree (status);


--
-- Name: gerar_processo_completo_uid_geracao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX gerar_processo_completo_uid_geracao_idx ON protocolos.gerar_processo_completo USING btree (uid_geracao);


--
-- Name: hierarquia_assunto_tipo_processo_id_assunto_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX hierarquia_assunto_tipo_processo_id_assunto_idx ON protocolos.hierarquia_assunto_tipo_processo USING btree (id_assunto);


--
-- Name: hierarquia_assunto_tipo_processo_id_assunto_pai_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX hierarquia_assunto_tipo_processo_id_assunto_pai_idx ON protocolos.hierarquia_assunto_tipo_processo USING btree (id_assunto_pai);


--
-- Name: hierarquia_assunto_tipo_processo_id_tipo_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX hierarquia_assunto_tipo_processo_id_tipo_processo_idx ON protocolos.hierarquia_assunto_tipo_processo USING btree (id_tipo_processo);


--
-- Name: hierarquia_assunto_tipo_processo_id_tipo_processo_pai_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX hierarquia_assunto_tipo_processo_id_tipo_processo_pai_idx ON protocolos.hierarquia_assunto_tipo_processo USING btree (id_tipo_processo_pai);


--
-- Name: hierarquia_assunto_tipo_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX hierarquia_assunto_tipo_processo_id_usuario_idx ON protocolos.hierarquia_assunto_tipo_processo USING btree (id_usuario);


--
-- Name: incorporacao_id_incorporado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX incorporacao_id_incorporado_idx ON protocolos.incorporacao USING btree (id_incorporado);


--
-- Name: incorporacao_id_incorporador_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX incorporacao_id_incorporador_idx ON protocolos.incorporacao USING btree (id_incorporador);


--
-- Name: incorporacao_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX incorporacao_id_movimentacao_idx ON protocolos.incorporacao USING btree (id_movimentacao);


--
-- Name: incorporacao_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX incorporacao_id_usuario_idx ON protocolos.incorporacao USING btree (id_usuario);


--
-- Name: incorporacao_status_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX incorporacao_status_ativo_idx ON protocolos.incorporacao_status USING btree (ativo);


--
-- Name: incorporacao_status_incorporacao_status_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX incorporacao_status_incorporacao_status_idx ON protocolos.incorporacao_status USING btree (incorporacao_status);


--
-- Name: ix_anexo_processo_tenant_id_id; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_anexo_processo_tenant_id_id ON protocolos.anexo_processo USING btree (tenant_id, id);


--
-- Name: ix_apensamento_apensado; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_apensamento_apensado ON protocolos.processo_apensamento USING btree (tenant_id, id_processo_apensado);


--
-- Name: ix_apensamento_principal; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_apensamento_principal ON protocolos.processo_apensamento USING btree (tenant_id, id_processo_principal);


--
-- Name: ix_ccd_classe_tenant_pai; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_ccd_classe_tenant_pai ON protocolos.ccd_classe USING btree (tenant_id, id_classe_pai);


--
-- Name: ix_encaminhamento_tenant_id_id; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_encaminhamento_tenant_id_id ON protocolos.encaminhamento USING btree (tenant_id, id);


--
-- Name: ix_especie_documental_tenant_ativo; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_especie_documental_tenant_ativo ON protocolos.especie_documental USING btree (tenant_id, ativo);


--
-- Name: ix_movimentacao_tenant_id_id; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_movimentacao_tenant_id_id ON protocolos.movimentacao USING btree (tenant_id, id);


--
-- Name: ix_processo_canal_entrada; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_processo_canal_entrada ON protocolos.processo USING btree (tenant_id, canal_entrada, data_hora_abertura);


--
-- Name: ix_processo_ccd; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_processo_ccd ON protocolos.processo USING btree (tenant_id, id_ccd_classe);


--
-- Name: ix_processo_nup; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_processo_nup ON protocolos.processo USING btree (tenant_id, nup);


--
-- Name: ix_processo_tenant_id_id; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_processo_tenant_id_id ON protocolos.processo USING btree (tenant_id, id);


--
-- Name: ix_ttd_regra_tenant_classe; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_ttd_regra_tenant_classe ON protocolos.ttd_regra USING btree (tenant_id, id_ccd_classe);


--
-- Name: ix_volume_processo; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ix_volume_processo ON protocolos.processo_volume USING btree (tenant_id, id_processo, numero);


--
-- Name: liquidacao_despesas_processo_data_criacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_despesas_processo_data_criacao_idx ON protocolos.liquidacao_despesas_processo USING btree (data_criacao);


--
-- Name: liquidacao_despesas_processo_id_feempliq_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_despesas_processo_id_feempliq_idx ON protocolos.liquidacao_despesas_processo USING btree (id_feempliq);


--
-- Name: liquidacao_despesas_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_despesas_processo_id_processo_idx ON protocolos.liquidacao_despesas_processo USING btree (id_processo);


--
-- Name: liquidacao_despesas_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_despesas_processo_id_usuario_idx ON protocolos.liquidacao_despesas_processo USING btree (id_usuario);


--
-- Name: liquidacao_processo_ano_liquidacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_processo_ano_liquidacao_idx ON protocolos.liquidacao_processo USING btree (ano_liquidacao);


--
-- Name: liquidacao_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_processo_id_processo_idx ON protocolos.liquidacao_processo USING btree (id_processo);


--
-- Name: liquidacao_processo_liqcod_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_processo_liqcod_idx ON protocolos.liquidacao_processo USING btree (liqcod);


--
-- Name: liquidacao_processo_rp_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_processo_rp_idx ON protocolos.liquidacao_processo USING btree (rp);


--
-- Name: liquidacao_processo_rp_processado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX liquidacao_processo_rp_processado_idx ON protocolos.liquidacao_processo USING btree (rp_processado);


--
-- Name: login_data_de_login_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_data_de_login_idx ON protocolos.login USING btree (data_de_login);


--
-- Name: login_data_ultimo_acesso_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_data_ultimo_acesso_idx ON protocolos.login USING btree (data_ultimo_acesso);


--
-- Name: login_id_dados_acesso_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_id_dados_acesso_idx ON protocolos.login USING btree (id_dados_acesso);


--
-- Name: login_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_id_usuario_idx ON protocolos.login USING btree (id_usuario);


--
-- Name: login_usuario_externo_data_de_login_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_usuario_externo_data_de_login_idx ON protocolos.login_usuario_externo USING btree (data_de_login);


--
-- Name: login_usuario_externo_data_ultimo_acesso_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_usuario_externo_data_ultimo_acesso_idx ON protocolos.login_usuario_externo USING btree (data_ultimo_acesso);


--
-- Name: login_usuario_externo_id_dados_acesso_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_usuario_externo_id_dados_acesso_idx ON protocolos.login_usuario_externo USING btree (id_dados_acesso);


--
-- Name: login_usuario_externo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX login_usuario_externo_id_usuario_idx ON protocolos.login_usuario_externo USING btree (id_usuario);


--
-- Name: lotacao_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_ativo_idx ON protocolos.lotacao USING btree (ativo);


--
-- Name: lotacao_coordenadoria_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_coordenadoria_idx ON protocolos.lotacao USING btree (coordenadoria);


--
-- Name: lotacao_enviar_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_enviar_externo_idx ON protocolos.lotacao USING btree (enviar_externo);


--
-- Name: lotacao_id_unidade_trabalho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_id_unidade_trabalho_idx ON protocolos.lotacao USING btree (id_unidade_trabalho);


--
-- Name: lotacao_is_protocolo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_is_protocolo_idx ON protocolos.lotacao USING btree (is_protocolo);


--
-- Name: lotacao_principal_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_principal_idx ON protocolos.lotacao USING btree (principal);


--
-- Name: lotacao_protocolo_central_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_protocolo_central_idx ON protocolos.lotacao USING btree (protocolo_central);


--
-- Name: lotacao_restrita_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX lotacao_restrita_idx ON protocolos.lotacao USING btree (restrita);


--
-- Name: manifestante_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_ativo_idx ON protocolos.manifestante USING btree (ativo);


--
-- Name: manifestante_aux_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_aux_ativo_idx ON protocolos.manifestante_aux USING btree (ativo);


--
-- Name: manifestante_aux_cpf_cnpj_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_aux_cpf_cnpj_idx ON protocolos.manifestante_aux USING btree (cpf_cnpj);


--
-- Name: manifestante_aux_id_tipo_manifestante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_aux_id_tipo_manifestante_idx ON protocolos.manifestante_aux USING btree (id_tipo_manifestante);


--
-- Name: manifestante_aux_id_usuario_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_aux_id_usuario_externo_idx ON protocolos.manifestante_aux USING btree (id_usuario_externo);


--
-- Name: manifestante_aux_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_aux_id_usuario_idx ON protocolos.manifestante_aux USING btree (id_usuario);


--
-- Name: manifestante_cpf_cnpj_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_cpf_cnpj_idx ON protocolos.manifestante USING btree (cpf_cnpj);


--
-- Name: manifestante_id_tipo_manifestante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_id_tipo_manifestante_idx ON protocolos.manifestante USING btree (id_tipo_manifestante);


--
-- Name: manifestante_id_usuario_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_id_usuario_externo_idx ON protocolos.manifestante USING btree (id_usuario_externo);


--
-- Name: manifestante_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX manifestante_id_usuario_idx ON protocolos.manifestante USING btree (id_usuario);


--
-- Name: movimentacao_data_hora_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_data_hora_movimentacao_idx ON protocolos.movimentacao USING btree (data_hora_movimentacao);


--
-- Name: movimentacao_id_acao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_acao_idx ON protocolos.movimentacao USING btree (id_acao);


--
-- Name: movimentacao_id_arquivamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_arquivamento_idx ON protocolos.movimentacao USING btree (id_arquivamento);


--
-- Name: movimentacao_id_carimbamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_carimbamento_idx ON protocolos.movimentacao USING btree (id_carimbamento);


--
-- Name: movimentacao_id_desentranhamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_desentranhamento_idx ON protocolos.movimentacao USING btree (id_desentranhamento);


--
-- Name: movimentacao_id_despacho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_despacho_idx ON protocolos.movimentacao USING btree (id_despacho);


--
-- Name: movimentacao_id_diligencia_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_diligencia_idx ON protocolos.movimentacao USING btree (id_diligencia);


--
-- Name: movimentacao_id_encaminhamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_encaminhamento_idx ON protocolos.movimentacao USING btree (id_encaminhamento);


--
-- Name: movimentacao_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_processo_idx ON protocolos.movimentacao USING btree (id_processo);


--
-- Name: movimentacao_id_solicitacao_assinatura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_solicitacao_assinatura_idx ON protocolos.movimentacao USING btree (id_solicitacao_assinatura);


--
-- Name: movimentacao_id_solicitacao_avaliacao_documento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_solicitacao_avaliacao_documento_idx ON protocolos.movimentacao USING btree (id_solicitacao_avaliacao_documento);


--
-- Name: movimentacao_id_unidade_responsavel_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_unidade_responsavel_idx ON protocolos.movimentacao USING btree (id_unidade_responsavel);


--
-- Name: movimentacao_id_usuario_assinatura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_usuario_assinatura_idx ON protocolos.movimentacao USING btree (id_usuario_assinatura);


--
-- Name: movimentacao_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_id_usuario_idx ON protocolos.movimentacao USING btree (id_usuario);


--
-- Name: movimentacao_spu_caixas_movimentacao_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_caixas_movimentacao_id_idx ON protocolos.movimentacao_spu USING btree (caixas_movimentacao_id);


--
-- Name: movimentacao_spu_data_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_data_movimentacao_idx ON protocolos.movimentacao_spu USING btree (data_movimentacao);


--
-- Name: movimentacao_spu_lotacao_destino_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_lotacao_destino_id_idx ON protocolos.movimentacao_spu USING btree (lotacao_destino_id);


--
-- Name: movimentacao_spu_lotacao_origem_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_lotacao_origem_id_idx ON protocolos.movimentacao_spu USING btree (lotacao_origem_id);


--
-- Name: movimentacao_spu_prioridades_movimentacao_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_prioridades_movimentacao_id_idx ON protocolos.movimentacao_spu USING btree (prioridades_movimentacao_id);


--
-- Name: movimentacao_spu_processo_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_processo_id_idx ON protocolos.movimentacao_spu USING btree (processo_id);


--
-- Name: movimentacao_spu_quantidade_folhas_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_quantidade_folhas_idx ON protocolos.movimentacao_spu USING btree (quantidade_folhas);


--
-- Name: movimentacao_spu_status_movimentacao_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_status_movimentacao_id_idx ON protocolos.movimentacao_spu USING btree (status_movimentacao_id);


--
-- Name: movimentacao_spu_usuario_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX movimentacao_spu_usuario_id_idx ON protocolos.movimentacao_spu USING btree (usuario_id);


--
-- Name: oficio_circular_id_processo_filho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX oficio_circular_id_processo_filho_idx ON protocolos.oficio_circular USING btree (id_processo_filho);


--
-- Name: oficio_circular_id_processo_pai_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX oficio_circular_id_processo_pai_idx ON protocolos.oficio_circular USING btree (id_processo_pai);


--
-- Name: oficio_circular_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX oficio_circular_id_usuario_idx ON protocolos.oficio_circular USING btree (id_usuario);


--
-- Name: ordem_desentranhamento_antigo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_antigo_idx ON protocolos.ordem_desentranhamento USING btree (antigo);


--
-- Name: ordem_desentranhamento_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_ativo_idx ON protocolos.ordem_desentranhamento USING btree (ativo);


--
-- Name: ordem_desentranhamento_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_id_anexo_idx ON protocolos.ordem_desentranhamento USING btree (id_anexo);


--
-- Name: ordem_desentranhamento_id_desentranhamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_id_desentranhamento_idx ON protocolos.ordem_desentranhamento USING btree (id_desentranhamento);


--
-- Name: ordem_desentranhamento_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_id_processo_idx ON protocolos.ordem_desentranhamento USING btree (id_processo);


--
-- Name: ordem_desentranhamento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_id_usuario_idx ON protocolos.ordem_desentranhamento USING btree (id_usuario);


--
-- Name: ordem_desentranhamento_ordem_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_ordem_idx ON protocolos.ordem_desentranhamento USING btree (ordem);


--
-- Name: ordem_desentranhamento_removido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX ordem_desentranhamento_removido_idx ON protocolos.ordem_desentranhamento USING btree (removido);


--
-- Name: prioridade_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX prioridade_ativo_idx ON protocolos.prioridade USING btree (ativo);


--
-- Name: prioridade_cor_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX prioridade_cor_idx ON protocolos.prioridade USING btree (cor);


--
-- Name: prioridade_fator_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX prioridade_fator_idx ON protocolos.prioridade USING btree (fator);


--
-- Name: prioridade_prioridade_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX prioridade_prioridade_idx ON protocolos.prioridade USING btree (prioridade);


--
-- Name: processo_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_ativo_idx ON protocolos.processo USING btree (ativo);


--
-- Name: processo_data_hora_abertura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_data_hora_abertura_idx ON protocolos.processo USING btree (data_hora_abertura);


--
-- Name: processo_id_assunto_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_assunto_idx ON protocolos.processo USING btree (id_assunto);


--
-- Name: processo_id_incorporacao_status_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_incorporacao_status_idx ON protocolos.processo USING btree (id_incorporacao_status);


--
-- Name: processo_id_local_atual_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_local_atual_idx ON protocolos.processo USING btree (id_local_atual);


--
-- Name: processo_id_manifestante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_manifestante_idx ON protocolos.processo USING btree (id_manifestante);


--
-- Name: processo_id_processo_pai_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_processo_pai_idx ON protocolos.processo USING btree (id_processo_pai);


--
-- Name: processo_id_ultima_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_ultima_movimentacao_idx ON protocolos.processo USING btree (id_ultima_movimentacao);


--
-- Name: processo_id_unidade_proprietaria_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_unidade_proprietaria_idx ON protocolos.processo USING btree (id_unidade_proprietaria);


--
-- Name: processo_id_usuario_externo_abertura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_usuario_externo_abertura_idx ON protocolos.processo USING btree (id_usuario_externo_abertura);


--
-- Name: processo_id_usuario_externo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_usuario_externo_idx ON protocolos.processo USING btree (id_usuario_externo);


--
-- Name: processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_id_usuario_idx ON protocolos.processo USING btree (id_usuario);


--
-- Name: processo_migrado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_migrado_idx ON protocolos.processo USING btree (migrado);


--
-- Name: processo_numero_origem_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_numero_origem_idx ON protocolos.processo USING btree (numero_origem);


--
-- Name: processo_publico_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_publico_idx ON protocolos.processo USING btree (publico);


--
-- Name: processo_vinculado_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_vinculado_id_movimentacao_idx ON protocolos.processo_vinculado USING btree (id_movimentacao);


--
-- Name: processo_vinculado_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_vinculado_id_processo_idx ON protocolos.processo_vinculado USING btree (id_processo);


--
-- Name: processo_vinculado_id_processo_vinculado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_vinculado_id_processo_vinculado_idx ON protocolos.processo_vinculado USING btree (id_processo_vinculado);


--
-- Name: processo_vinculado_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX processo_vinculado_id_usuario_idx ON protocolos.processo_vinculado USING btree (id_usuario);


--
-- Name: publicidade_processo_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX publicidade_processo_ativo_idx ON protocolos.publicidade_processo USING btree (ativo);


--
-- Name: publicidade_processo_id_despacho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX publicidade_processo_id_despacho_idx ON protocolos.publicidade_processo USING btree (id_despacho);


--
-- Name: publicidade_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX publicidade_processo_id_processo_idx ON protocolos.publicidade_processo USING btree (id_processo);


--
-- Name: publicidade_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX publicidade_processo_id_usuario_idx ON protocolos.publicidade_processo USING btree (id_usuario);


--
-- Name: publicidade_processo_publico_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX publicidade_processo_publico_idx ON protocolos.publicidade_processo USING btree (publico);


--
-- Name: responsavel_processo_id_lotacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX responsavel_processo_id_lotacao_idx ON protocolos.responsavel_processo USING btree (id_lotacao);


--
-- Name: responsavel_processo_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX responsavel_processo_id_movimentacao_idx ON protocolos.responsavel_processo USING btree (id_movimentacao);


--
-- Name: responsavel_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX responsavel_processo_id_processo_idx ON protocolos.responsavel_processo USING btree (id_processo);


--
-- Name: responsavel_processo_id_responsavel_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX responsavel_processo_id_responsavel_idx ON protocolos.responsavel_processo USING btree (id_responsavel);


--
-- Name: responsavel_processo_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX responsavel_processo_id_usuario_idx ON protocolos.responsavel_processo USING btree (id_usuario);


--
-- Name: responsavel_processo_movimentacao_id_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX responsavel_processo_movimentacao_id_idx ON protocolos.responsavel_processo USING btree (movimentacao_id);


--
-- Name: solicitacao_assinatura_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_ativo_idx ON protocolos.solicitacao_assinatura USING btree (ativo);


--
-- Name: solicitacao_assinatura_cancelada_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_cancelada_idx ON protocolos.solicitacao_assinatura USING btree (cancelada);


--
-- Name: solicitacao_assinatura_dt_fim_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_dt_fim_idx ON protocolos.solicitacao_assinatura USING btree (dt_fim);


--
-- Name: solicitacao_assinatura_dt_inicio_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_dt_inicio_idx ON protocolos.solicitacao_assinatura USING btree (dt_inicio);


--
-- Name: solicitacao_assinatura_dt_retomada_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_dt_retomada_idx ON protocolos.solicitacao_assinatura USING btree (dt_retomada);


--
-- Name: solicitacao_assinatura_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_id_processo_idx ON protocolos.solicitacao_assinatura USING btree (id_processo);


--
-- Name: solicitacao_assinatura_id_solicitante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_id_solicitante_idx ON protocolos.solicitacao_assinatura USING btree (id_solicitante);


--
-- Name: solicitacao_assinatura_id_unidade_solicitante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_id_unidade_solicitante_idx ON protocolos.solicitacao_assinatura USING btree (id_unidade_solicitante);


--
-- Name: solicitacao_assinatura_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_id_usuario_idx ON protocolos.solicitacao_assinatura USING btree (id_usuario);


--
-- Name: solicitacao_assinatura_id_usuario_retomada_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_id_usuario_retomada_idx ON protocolos.solicitacao_assinatura USING btree (id_usuario_retomada);


--
-- Name: solicitacao_assinatura_realizada_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_assinatura_realizada_idx ON protocolos.solicitacao_assinatura USING btree (realizada);


--
-- Name: solicitacao_avaliacao_documento_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_avaliacao_documento_ativo_idx ON protocolos.solicitacao_avaliacao_documento USING btree (ativo);


--
-- Name: solicitacao_avaliacao_documento_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_avaliacao_documento_id_processo_idx ON protocolos.solicitacao_avaliacao_documento USING btree (id_processo);


--
-- Name: solicitacao_avaliacao_documento_id_solicitante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_avaliacao_documento_id_solicitante_idx ON protocolos.solicitacao_avaliacao_documento USING btree (id_solicitante);


--
-- Name: solicitacao_avaliacao_documento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_avaliacao_documento_id_usuario_idx ON protocolos.solicitacao_avaliacao_documento USING btree (id_usuario);


--
-- Name: solicitacao_avaliacao_documento_realizada_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_avaliacao_documento_realizada_idx ON protocolos.solicitacao_avaliacao_documento USING btree (realizada);


--
-- Name: solicitacao_pagamento_processo_data_criacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_pagamento_processo_data_criacao_idx ON protocolos.solicitacao_pagamento_processo USING btree (data_criacao);


--
-- Name: solicitacao_pagamento_processo_excluido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_pagamento_processo_excluido_idx ON protocolos.solicitacao_pagamento_processo USING btree (excluido);


--
-- Name: solicitacao_pagamento_processo_id_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_pagamento_processo_id_processo_idx ON protocolos.solicitacao_pagamento_processo USING btree (id_processo);


--
-- Name: solicitacao_pagamento_processo_id_solicitacao_pagamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_pagamento_processo_id_solicitacao_pagamento_idx ON protocolos.solicitacao_pagamento_processo USING btree (id_solicitacao_pagamento);


--
-- Name: solicitacao_pagamento_processo_tipo_pagamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX solicitacao_pagamento_processo_tipo_pagamento_idx ON protocolos.solicitacao_pagamento_processo USING btree (tipo_pagamento);


--
-- Name: template_carimbo_secretaria_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX template_carimbo_secretaria_ativo_idx ON protocolos.template_carimbo_secretaria USING btree (ativo);


--
-- Name: template_carimbo_secretaria_id_secretaria_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX template_carimbo_secretaria_id_secretaria_idx ON protocolos.template_carimbo_secretaria USING btree (id_secretaria);


--
-- Name: template_carimbo_secretaria_id_template_carimbo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX template_carimbo_secretaria_id_template_carimbo_idx ON protocolos.template_carimbo_secretaria USING btree (id_template_carimbo);


--
-- Name: unidade_padrao_liq_pag_empenho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_empenho_idx ON protocolos.unidade_padrao_liq_pag USING btree (empenho);


--
-- Name: unidade_padrao_liq_pag_excluido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_excluido_idx ON protocolos.unidade_padrao_liq_pag USING btree (excluido);


--
-- Name: unidade_padrao_liq_pag_id_unidade_trabalho_destino_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_id_unidade_trabalho_destino_idx ON protocolos.unidade_padrao_liq_pag USING btree (id_unidade_trabalho_destino);


--
-- Name: unidade_padrao_liq_pag_id_unidade_trabalho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_id_unidade_trabalho_idx ON protocolos.unidade_padrao_liq_pag USING btree (id_unidade_trabalho);


--
-- Name: unidade_padrao_liq_pag_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_id_usuario_idx ON protocolos.unidade_padrao_liq_pag USING btree (id_usuario);


--
-- Name: unidade_padrao_liq_pag_incluir_filhas_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_incluir_filhas_idx ON protocolos.unidade_padrao_liq_pag USING btree (incluir_filhas);


--
-- Name: unidade_padrao_liq_pag_liquidacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_liquidacao_idx ON protocolos.unidade_padrao_liq_pag USING btree (liquidacao);


--
-- Name: unidade_padrao_liq_pag_pagamento_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX unidade_padrao_liq_pag_pagamento_idx ON protocolos.unidade_padrao_liq_pag USING btree (pagamento);


--
-- Name: uq_apensamento_filho_ativo; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE UNIQUE INDEX uq_apensamento_filho_ativo ON protocolos.processo_apensamento USING btree (id_processo_apensado) WHERE (desapensado_em IS NULL);


--
-- Name: uq_processo_nup_global; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE UNIQUE INDEX uq_processo_nup_global ON protocolos.processo USING btree (nup) WHERE ((nup IS NOT NULL) AND (excluido IS FALSE));


--
-- Name: uq_ttd_regra_classe_especie; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE UNIQUE INDEX uq_ttd_regra_classe_especie ON protocolos.ttd_regra USING btree (tenant_id, id_ccd_classe, id_especie_documental) WHERE (excluido IS FALSE);


--
-- Name: uq_ttd_regra_classe_sem_especie; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE UNIQUE INDEX uq_ttd_regra_classe_sem_especie ON protocolos.ttd_regra USING btree (tenant_id, id_ccd_classe) WHERE ((id_especie_documental IS NULL) AND (excluido IS FALSE));


--
-- Name: usuario_assinatura_aprovacao_pendente_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_aprovacao_pendente_idx ON protocolos.usuario_assinatura USING btree (aprovacao_pendente);


--
-- Name: usuario_assinatura_aprovado_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_aprovado_idx ON protocolos.usuario_assinatura USING btree (aprovado);


--
-- Name: usuario_assinatura_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_ativo_idx ON protocolos.usuario_assinatura USING btree (ativo);


--
-- Name: usuario_assinatura_id_assinante_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_id_assinante_idx ON protocolos.usuario_assinatura USING btree (id_assinante);


--
-- Name: usuario_assinatura_id_solicitacao_assinatura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_id_solicitacao_assinatura_idx ON protocolos.usuario_assinatura USING btree (id_solicitacao_assinatura);


--
-- Name: usuario_assinatura_id_tipo_assinatura_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_id_tipo_assinatura_idx ON protocolos.usuario_assinatura USING btree (id_tipo_assinatura);


--
-- Name: usuario_assinatura_id_unidade_trabalho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_id_unidade_trabalho_idx ON protocolos.usuario_assinatura USING btree (id_unidade_trabalho);


--
-- Name: usuario_assinatura_id_usuario_aprovacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_id_usuario_aprovacao_idx ON protocolos.usuario_assinatura USING btree (id_usuario_aprovacao);


--
-- Name: usuario_assinatura_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_id_usuario_idx ON protocolos.usuario_assinatura USING btree (id_usuario);


--
-- Name: usuario_assinatura_ordem_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_ordem_idx ON protocolos.usuario_assinatura USING btree (ordem);


--
-- Name: usuario_assinatura_realizada_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_assinatura_realizada_idx ON protocolos.usuario_assinatura USING btree (realizada);


--
-- Name: usuario_avaliacao_documento_ativo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_ativo_idx ON protocolos.usuario_avaliacao_documento USING btree (ativo);


--
-- Name: usuario_avaliacao_documento_id_avaliador_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_id_avaliador_idx ON protocolos.usuario_avaliacao_documento USING btree (id_avaliador);


--
-- Name: usuario_avaliacao_documento_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_id_movimentacao_idx ON protocolos.usuario_avaliacao_documento USING btree (id_movimentacao);


--
-- Name: usuario_avaliacao_documento_id_solicitacao_avaliacao_documento_; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_id_solicitacao_avaliacao_documento_ ON protocolos.usuario_avaliacao_documento USING btree (id_solicitacao_avaliacao_documento);


--
-- Name: usuario_avaliacao_documento_id_unidade_trabalho_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_id_unidade_trabalho_idx ON protocolos.usuario_avaliacao_documento USING btree (id_unidade_trabalho);


--
-- Name: usuario_avaliacao_documento_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_id_usuario_idx ON protocolos.usuario_avaliacao_documento USING btree (id_usuario);


--
-- Name: usuario_avaliacao_documento_ordem_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_ordem_idx ON protocolos.usuario_avaliacao_documento USING btree (ordem);


--
-- Name: usuario_avaliacao_documento_realizada_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX usuario_avaliacao_documento_realizada_idx ON protocolos.usuario_avaliacao_documento USING btree (realizada);


--
-- Name: vinculo_gerarprocesso_anexos_excluido_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX vinculo_gerarprocesso_anexos_excluido_idx ON protocolos.vinculo_gerarprocesso_anexos USING btree (excluido);


--
-- Name: vinculo_gerarprocesso_anexos_id_anexo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX vinculo_gerarprocesso_anexos_id_anexo_idx ON protocolos.vinculo_gerarprocesso_anexos USING btree (id_anexo);


--
-- Name: vinculo_gerarprocesso_anexos_id_geracao_processo_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX vinculo_gerarprocesso_anexos_id_geracao_processo_idx ON protocolos.vinculo_gerarprocesso_anexos USING btree (id_geracao_processo);


--
-- Name: vinculo_gerarprocesso_anexos_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX vinculo_gerarprocesso_anexos_id_usuario_idx ON protocolos.vinculo_gerarprocesso_anexos USING btree (id_usuario);


--
-- Name: volume_fim_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX volume_fim_idx ON protocolos.volume USING btree (fim);


--
-- Name: volume_id_movimentacao_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX volume_id_movimentacao_idx ON protocolos.volume USING btree (id_movimentacao);


--
-- Name: volume_id_usuario_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX volume_id_usuario_idx ON protocolos.volume USING btree (id_usuario);


--
-- Name: volume_inicio_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX volume_inicio_idx ON protocolos.volume USING btree (inicio);


--
-- Name: volume_volume_idx; Type: INDEX; Schema: protocolos; Owner: -
--

CREATE INDEX volume_volume_idx ON protocolos.volume USING btree (volume);


--
-- Name: email_excluido_index; Type: INDEX; Schema: utils; Owner: -
--

CREATE INDEX email_excluido_index ON utils.email USING btree (excluido);


--
-- Name: email_mensagem_erro_id_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX email_mensagem_erro_id_uindex ON utils.email_mensagem_erro USING btree (id);


--
-- Name: email_sistema_id_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX email_sistema_id_uindex ON utils.email_sistema USING btree (id);


--
-- Name: email_sistema_index; Type: INDEX; Schema: utils; Owner: -
--

CREATE INDEX email_sistema_index ON utils.email USING btree (sistema);


--
-- Name: email_status_index; Type: INDEX; Schema: utils; Owner: -
--

CREATE INDEX email_status_index ON utils.email USING btree (status);


--
-- Name: escolaridade_grauinstrucao_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX escolaridade_grauinstrucao_uindex ON utils.escolaridade USING btree (grauinstrucao);


--
-- Name: idx_tgws; Type: INDEX; Schema: utils; Owner: -
--

CREATE INDEX idx_tgws ON utils.tokens_gestorws USING btree (token);


--
-- Name: index_comentario_sessao; Type: INDEX; Schema: utils; Owner: -
--

CREATE INDEX index_comentario_sessao ON utils.comentario USING btree (app);


--
-- Name: index_comentario_sessao2; Type: INDEX; Schema: utils; Owner: -
--

CREATE INDEX index_comentario_sessao2 ON utils.comentario USING btree (sessao);


--
-- Name: ixd_unq_ativo_corrente; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX ixd_unq_ativo_corrente ON utils.ano_financeiro USING btree (ativo, corrente) WHERE ((ativo IS TRUE) AND (corrente IS TRUE));


--
-- Name: marca_veiculo_marca_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX marca_veiculo_marca_uindex ON utils.marca_veiculo USING btree (marca_veiculo);


--
-- Name: pessoa_cnh_uniq; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX pessoa_cnh_uniq ON utils.pessoa USING btree (cnh) WHERE (excluido IS FALSE);


--
-- Name: pessoa_cpf_cnpj; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX pessoa_cpf_cnpj ON utils.pessoa USING btree (cpf_cnpj) WHERE (excluido IS FALSE);


--
-- Name: pessoa_email; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX pessoa_email ON utils.pessoa USING btree (email) WHERE (excluido IS FALSE);


--
-- Name: raca_cor_funraca_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX raca_cor_funraca_uindex ON utils.raca_cor USING btree (funraca);


--
-- Name: tipo_de_entrada_no_pais_id_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX tipo_de_entrada_no_pais_id_uindex ON utils.tipo_de_entrada_no_pais USING btree (id);


--
-- Name: tipo_deficiencia_id_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX tipo_deficiencia_id_uindex ON utils.tipo_deficiencia USING btree (id);


--
-- Name: unidade_trabalho_key_uindex; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX unidade_trabalho_key_uindex ON utils.unidade_trabalho USING btree (key);


--
-- Name: usuario_cpf_per_tenant; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX usuario_cpf_per_tenant ON utils.usuario USING btree (tenant_id, cpf) WHERE (excluido IS FALSE);


--
-- Name: usuario_email_per_tenant; Type: INDEX; Schema: utils; Owner: -
--

CREATE UNIQUE INDEX usuario_email_per_tenant ON utils.usuario USING btree (tenant_id, email) WHERE (excluido IS FALSE);


--
-- Name: anexo_processo copia_id_ordem_anexo_processo_trig; Type: TRIGGER; Schema: protocolos; Owner: -
--

CREATE TRIGGER copia_id_ordem_anexo_processo_trig BEFORE INSERT ON protocolos.anexo_processo FOR EACH ROW EXECUTE FUNCTION protocolos.copia_id_ordem_anexo_processo_func();


--
-- Name: empenho_processo trigger_aud_empenho_processo; Type: TRIGGER; Schema: protocolos; Owner: -
--

CREATE TRIGGER trigger_aud_empenho_processo AFTER INSERT OR DELETE OR UPDATE ON protocolos.empenho_processo FOR EACH ROW EXECUTE FUNCTION protocolos.func_aud_empenho_processo();


--
-- Name: liquidacao_despesas_processo trigger_aud_liquidacao_despesas_processo; Type: TRIGGER; Schema: protocolos; Owner: -
--

CREATE TRIGGER trigger_aud_liquidacao_despesas_processo AFTER INSERT OR DELETE OR UPDATE ON protocolos.liquidacao_despesas_processo FOR EACH ROW EXECUTE FUNCTION protocolos.func_aud_liquidacao_despesas_processo();


--
-- Name: solicitacao_pagamento_processo trigger_aud_solicitacao_pagamento_processo; Type: TRIGGER; Schema: protocolos; Owner: -
--

CREATE TRIGGER trigger_aud_solicitacao_pagamento_processo AFTER INSERT OR DELETE OR UPDATE ON protocolos.solicitacao_pagamento_processo FOR EACH ROW EXECUTE FUNCTION protocolos.func_aud_solicitacao_pagamento_processo();


--
-- Name: cbo set_timestamp; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER set_timestamp BEFORE UPDATE ON utils.cbo FOR EACH ROW EXECUTE FUNCTION public.trigger_set_timestamp();


--
-- Name: fila set_timestamp; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER set_timestamp BEFORE UPDATE ON utils.fila FOR EACH ROW EXECUTE FUNCTION public.trigger_set_timestamp();


--
-- Name: sistema tg_copia_sistema; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER tg_copia_sistema AFTER INSERT OR UPDATE ON utils.sistema FOR EACH ROW EXECUTE FUNCTION utils.copia_sistemas_tipochamados();


--
-- Name: ano_financeiro trigger_aud_ano_financeiro; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_aud_ano_financeiro AFTER INSERT OR DELETE OR UPDATE ON utils.ano_financeiro FOR EACH ROW EXECUTE FUNCTION utils.func_aud_ano_financeiro();


--
-- Name: endereco trigger_aud_endereco; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_aud_endereco AFTER INSERT OR DELETE OR UPDATE ON utils.endereco FOR EACH ROW EXECUTE FUNCTION utils.func_aud_endereco();


--
-- Name: pessoa trigger_aud_pessoa; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_aud_pessoa AFTER INSERT OR DELETE OR UPDATE ON utils.pessoa FOR EACH ROW EXECUTE FUNCTION utils.func_aud_pessoa();


--
-- Name: secretarias_unidade_trabalho trigger_aud_secretarias_unidade_trabalho; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_aud_secretarias_unidade_trabalho AFTER INSERT OR DELETE OR UPDATE ON utils.secretarias_unidade_trabalho FOR EACH ROW EXECUTE FUNCTION utils.func_aud_secretarias_unidade_trabalho();


--
-- Name: sistema_usuario trigger_aud_sistema_usuario; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_aud_sistema_usuario AFTER INSERT OR DELETE OR UPDATE ON utils.sistema_usuario FOR EACH ROW EXECUTE FUNCTION utils.func_aud_sistema_usuario();


--
-- Name: usuario trigger_aud_usuario; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_aud_usuario AFTER INSERT OR DELETE OR UPDATE ON utils.usuario FOR EACH ROW EXECUTE FUNCTION utils.func_aud_usuario();


--
-- Name: usuario_grupo trigger_aud_usuario_grupo; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_aud_usuario_grupo AFTER INSERT OR DELETE OR UPDATE ON utils.usuario_grupo FOR EACH ROW EXECUTE FUNCTION utils.func_aud_usuario_grupo();


--
-- Name: pessoa trigger_delete_pessoa; Type: TRIGGER; Schema: utils; Owner: -
--

CREATE TRIGGER trigger_delete_pessoa BEFORE UPDATE ON utils.pessoa FOR EACH ROW EXECUTE FUNCTION utils.fn_trigger_delete_pessoa();


--
-- Name: audit_log audit_log_id_usuario_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.audit_log
    ADD CONSTRAINT audit_log_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: audit_log audit_log_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.audit_log
    ADD CONSTRAINT audit_log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: job fk_job_tenant_id; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.job
    ADD CONSTRAINT fk_job_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: job job_id_usuario_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.job
    ADD CONSTRAINT job_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: notificacao notificacao_id_usuario_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao
    ADD CONSTRAINT notificacao_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: notificacao_preferencia notificacao_preferencia_id_usuario_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao_preferencia
    ADD CONSTRAINT notificacao_preferencia_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: notificacao_preferencia notificacao_preferencia_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao_preferencia
    ADD CONSTRAINT notificacao_preferencia_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: notificacao notificacao_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.notificacao
    ADD CONSTRAINT notificacao_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: nup_sequencia nup_sequencia_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.nup_sequencia
    ADD CONSTRAINT nup_sequencia_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: tenant tenant_id_cidade_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tenant
    ADD CONSTRAINT tenant_id_cidade_fkey FOREIGN KEY (id_cidade) REFERENCES utils.cidade(id);


--
-- Name: tipo_processo_workflow tipo_processo_workflow_id_tipo_processo_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tipo_processo_workflow
    ADD CONSTRAINT tipo_processo_workflow_id_tipo_processo_fkey FOREIGN KEY (id_tipo_processo) REFERENCES protocolos.tipo_processo(id);


--
-- Name: tipo_processo_workflow tipo_processo_workflow_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.tipo_processo_workflow
    ADD CONSTRAINT tipo_processo_workflow_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: workflow_definition workflow_definition_id_usuario_criador_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_definition
    ADD CONSTRAINT workflow_definition_id_usuario_criador_fkey FOREIGN KEY (id_usuario_criador) REFERENCES utils.usuario(id);


--
-- Name: workflow_definition workflow_definition_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_definition
    ADD CONSTRAINT workflow_definition_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: workflow_instance workflow_instance_id_processo_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_instance
    ADD CONSTRAINT workflow_instance_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES protocolos.processo(id);


--
-- Name: workflow_instance workflow_instance_id_usuario_inicio_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_instance
    ADD CONSTRAINT workflow_instance_id_usuario_inicio_fkey FOREIGN KEY (id_usuario_inicio) REFERENCES utils.usuario(id);


--
-- Name: workflow_instance workflow_instance_id_workflow_definition_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_instance
    ADD CONSTRAINT workflow_instance_id_workflow_definition_fkey FOREIGN KEY (id_workflow_definition) REFERENCES aprimora_py.workflow_definition(id);


--
-- Name: workflow_instance workflow_instance_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_instance
    ADD CONSTRAINT workflow_instance_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: workflow_sla_alerta workflow_sla_alerta_id_workflow_instance_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_sla_alerta
    ADD CONSTRAINT workflow_sla_alerta_id_workflow_instance_fkey FOREIGN KEY (id_workflow_instance) REFERENCES aprimora_py.workflow_instance(id);


--
-- Name: workflow_sla_alerta workflow_sla_alerta_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_sla_alerta
    ADD CONSTRAINT workflow_sla_alerta_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: workflow_transicao_log workflow_transicao_log_id_usuario_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_transicao_log
    ADD CONSTRAINT workflow_transicao_log_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: workflow_transicao_log workflow_transicao_log_id_workflow_instance_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_transicao_log
    ADD CONSTRAINT workflow_transicao_log_id_workflow_instance_fkey FOREIGN KEY (id_workflow_instance) REFERENCES aprimora_py.workflow_instance(id);


--
-- Name: workflow_transicao_log workflow_transicao_log_tenant_id_fkey; Type: FK CONSTRAINT; Schema: aprimora_py; Owner: -
--

ALTER TABLE ONLY aprimora_py.workflow_transicao_log
    ADD CONSTRAINT workflow_transicao_log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: acoes_privadas_movimentacao acoes_privadas_movimentacao_id_acao_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.acoes_privadas_movimentacao
    ADD CONSTRAINT acoes_privadas_movimentacao_id_acao_fkey FOREIGN KEY (id_acao) REFERENCES protocolos.acao(id);


--
-- Name: anexo anexo_id_alfresco_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo
    ADD CONSTRAINT anexo_id_alfresco_fkey FOREIGN KEY (id_alfresco) REFERENCES protocolos.alfresco_aux(id);


--
-- Name: anexo anexo_id_tipo_anexo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo
    ADD CONSTRAINT anexo_id_tipo_anexo_fkey FOREIGN KEY (id_tipo_anexo) REFERENCES protocolos.tipo_anexo(id) MATCH FULL;


--
-- Name: anexo anexo_id_usuario_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo
    ADD CONSTRAINT anexo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id) MATCH FULL;


--
-- Name: anexo_processo anexo_processo_id_movimentacao_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo_processo
    ADD CONSTRAINT anexo_processo_id_movimentacao_fkey FOREIGN KEY (id_movimentacao) REFERENCES protocolos.movimentacao(id) MATCH FULL;


--
-- Name: anexo_processo anexo_processo_id_usuario_desentranhamento_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo_processo
    ADD CONSTRAINT anexo_processo_id_usuario_desentranhamento_fkey FOREIGN KEY (id_usuario_desentranhamento) REFERENCES utils.usuario(id);


--
-- Name: arquivamento arquivamento_id_status_arquivamento_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.arquivamento
    ADD CONSTRAINT arquivamento_id_status_arquivamento_fkey FOREIGN KEY (id_status_arquivamento) REFERENCES protocolos.status_arquivamento(id) MATCH FULL;


--
-- Name: assinatura_anexo assinatura_anexo_id_anexo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assinatura_anexo
    ADD CONSTRAINT assinatura_anexo_id_anexo_fkey FOREIGN KEY (id_anexo) REFERENCES protocolos.anexo(id) MATCH FULL;


--
-- Name: assinatura_anexo assinatura_anexo_id_processo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assinatura_anexo
    ADD CONSTRAINT assinatura_anexo_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES protocolos.processo(id);


--
-- Name: assistente_assinatura assistente_assinatura_id_assistente_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assistente_assinatura
    ADD CONSTRAINT assistente_assinatura_id_assistente_fkey FOREIGN KEY (id_assistente) REFERENCES utils.usuario(id);


--
-- Name: assistente_assinatura assistente_assinatura_id_gerente_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assistente_assinatura
    ADD CONSTRAINT assistente_assinatura_id_gerente_fkey FOREIGN KEY (id_gerente) REFERENCES utils.usuario(id);


--
-- Name: assistente_assinatura assistente_assinatura_id_unidade_trabalho_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assistente_assinatura
    ADD CONSTRAINT assistente_assinatura_id_unidade_trabalho_fkey FOREIGN KEY (id_unidade_trabalho) REFERENCES utils.unidade_trabalho(id);


--
-- Name: assunto assunto_id_tipo_processo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto
    ADD CONSTRAINT assunto_id_tipo_processo_fkey FOREIGN KEY (id_tipo_processo) REFERENCES protocolos.tipo_processo(id) MATCH FULL;


--
-- Name: assunto_tipo_processo_tipo_anexo assunto_tipo_processo_tipo_anexo_id_assunto_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto_tipo_processo_tipo_anexo
    ADD CONSTRAINT assunto_tipo_processo_tipo_anexo_id_assunto_fkey FOREIGN KEY (id_assunto) REFERENCES protocolos.assunto(id);


--
-- Name: assunto_tipo_processo_tipo_anexo assunto_tipo_processo_tipo_anexo_id_tipo_anexo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto_tipo_processo_tipo_anexo
    ADD CONSTRAINT assunto_tipo_processo_tipo_anexo_id_tipo_anexo_fkey FOREIGN KEY (id_tipo_anexo) REFERENCES protocolos.tipo_anexo(id);


--
-- Name: assunto_tipo_processo_tipo_anexo assunto_tipo_processo_tipo_anexo_id_tipo_processo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto_tipo_processo_tipo_anexo
    ADD CONSTRAINT assunto_tipo_processo_tipo_anexo_id_tipo_processo_fkey FOREIGN KEY (id_tipo_processo) REFERENCES protocolos.tipo_processo(id);


--
-- Name: bairros_spu bairros_spu_cidade_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.bairros_spu
    ADD CONSTRAINT bairros_spu_cidade_id_fkey FOREIGN KEY (cidade_id) REFERENCES protocolos.cidades_spu(id);


--
-- Name: carimbamento carimbamento_id_movimentacao_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.carimbamento
    ADD CONSTRAINT carimbamento_id_movimentacao_fkey FOREIGN KEY (id_movimentacao) REFERENCES protocolos.movimentacao(id);


--
-- Name: carimbamento carimbamento_id_template_carimbo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.carimbamento
    ADD CONSTRAINT carimbamento_id_template_carimbo_fkey FOREIGN KEY (id_template_carimbo) REFERENCES protocolos.template_carimbo(id);


--
-- Name: ccd_classe ccd_classe_id_classe_pai_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ccd_classe
    ADD CONSTRAINT ccd_classe_id_classe_pai_fkey FOREIGN KEY (id_classe_pai) REFERENCES protocolos.ccd_classe(id);


--
-- Name: ccd_classe ccd_classe_tenant_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ccd_classe
    ADD CONSTRAINT ccd_classe_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: cidades_spu cidades_spu_estado_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.cidades_spu
    ADD CONSTRAINT cidades_spu_estado_id_fkey FOREIGN KEY (estado_id) REFERENCES protocolos.estados_spu(id);


--
-- Name: despacho despacho_id_processo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.despacho
    ADD CONSTRAINT despacho_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES protocolos.processo(id) MATCH FULL;


--
-- Name: despacho despacho_id_usuario_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.despacho
    ADD CONSTRAINT despacho_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id) MATCH FULL;


--
-- Name: documento_carimbamento documento_carimbamento_id_carimbamento_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.documento_carimbamento
    ADD CONSTRAINT documento_carimbamento_id_carimbamento_fkey FOREIGN KEY (id_carimbamento) REFERENCES protocolos.carimbamento(id);


--
-- Name: encaminhamento encaminhamento_id_unidade_destino_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.encaminhamento
    ADD CONSTRAINT encaminhamento_id_unidade_destino_fkey FOREIGN KEY (id_unidade_destino) REFERENCES utils.unidade_trabalho(id) MATCH FULL;


--
-- Name: encaminhamento encaminhamento_id_unidade_origem_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.encaminhamento
    ADD CONSTRAINT encaminhamento_id_unidade_origem_fkey FOREIGN KEY (id_unidade_origem) REFERENCES utils.unidade_trabalho(id) MATCH FULL;


--
-- Name: especie_documental especie_documental_tenant_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.especie_documental
    ADD CONSTRAINT especie_documental_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: anexo_processo fk_anexo_processo_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo_processo
    ADD CONSTRAINT fk_anexo_processo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: anexo fk_anexo_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.anexo
    ADD CONSTRAINT fk_anexo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: arquivamento fk_arquivamento_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.arquivamento
    ADD CONSTRAINT fk_arquivamento_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: assinatura_anexo fk_assinatura_anexo_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assinatura_anexo
    ADD CONSTRAINT fk_assinatura_anexo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: assunto fk_assunto_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto
    ADD CONSTRAINT fk_assunto_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: assunto_tipo_processo_tipo_anexo fk_assunto_tipo_processo_tipo_anexo_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.assunto_tipo_processo_tipo_anexo
    ADD CONSTRAINT fk_assunto_tipo_processo_tipo_anexo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: login_usuario_externo fk_dados_acesso; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.login_usuario_externo
    ADD CONSTRAINT fk_dados_acesso FOREIGN KEY (id_dados_acesso) REFERENCES protocolos.dados_acesso(id);


--
-- Name: despacho fk_despacho_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.despacho
    ADD CONSTRAINT fk_despacho_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: encaminhamento fk_enc_id_processo; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.encaminhamento
    ADD CONSTRAINT fk_enc_id_processo FOREIGN KEY (id_processo) REFERENCES protocolos.processo(id);


--
-- Name: encaminhamento fk_encaminhamento_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.encaminhamento
    ADD CONSTRAINT fk_encaminhamento_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: manifestante fk_manifestante_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.manifestante
    ADD CONSTRAINT fk_manifestante_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: movimentacao fk_mov_id_diligencia; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT fk_mov_id_diligencia FOREIGN KEY (id_diligencia) REFERENCES protocolos.diligencia(id);


--
-- Name: movimentacao fk_mov_id_solicitacao_assinatura; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT fk_mov_id_solicitacao_assinatura FOREIGN KEY (id_solicitacao_assinatura) REFERENCES protocolos.solicitacao_assinatura(id);


--
-- Name: movimentacao fk_mov_id_solicitacao_avaliacao_documento; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT fk_mov_id_solicitacao_avaliacao_documento FOREIGN KEY (id_solicitacao_avaliacao_documento) REFERENCES protocolos.solicitacao_avaliacao_documento(id);


--
-- Name: movimentacao fk_movimentacao_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT fk_movimentacao_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: processo fk_pro_id_ultima_movimentacao; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT fk_pro_id_ultima_movimentacao FOREIGN KEY (id_ultima_movimentacao) REFERENCES protocolos.movimentacao(id);


--
-- Name: processo fk_processo_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT fk_processo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: solicitacao_assinatura fk_solicitacao_assinatura_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.solicitacao_assinatura
    ADD CONSTRAINT fk_solicitacao_assinatura_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: tipo_anexo fk_tipo_anexo_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_anexo
    ADD CONSTRAINT fk_tipo_anexo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: tipo_manifestante fk_tipo_manifestante_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_manifestante
    ADD CONSTRAINT fk_tipo_manifestante_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: tipo_processo fk_tipo_processo_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.tipo_processo
    ADD CONSTRAINT fk_tipo_processo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: usuario_assinatura fk_usuario_assinatura_tenant_id; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuario_assinatura
    ADD CONSTRAINT fk_usuario_assinatura_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: gerar_processo_completo gerar_processo_completo_id_anexo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processo_completo
    ADD CONSTRAINT gerar_processo_completo_id_anexo_fkey FOREIGN KEY (id_anexo) REFERENCES protocolos.arquivo_temporario(id);


--
-- Name: gerar_processo_completo gerar_processo_completo_id_processo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processo_completo
    ADD CONSTRAINT gerar_processo_completo_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES protocolos.processo(id);


--
-- Name: gerar_processos_envolvido gerar_processos_envolvido_id_secretaria_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processos_envolvido
    ADD CONSTRAINT gerar_processos_envolvido_id_secretaria_fkey FOREIGN KEY (id_secretaria) REFERENCES utils.unidade_trabalho(id);


--
-- Name: gerar_processos_envolvido gerar_processos_envolvido_id_usuario_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.gerar_processos_envolvido
    ADD CONSTRAINT gerar_processos_envolvido_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: hierarquia_assunto_tipo_processo hierarquia_assunto_tipo_processo_id_assunto_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.hierarquia_assunto_tipo_processo
    ADD CONSTRAINT hierarquia_assunto_tipo_processo_id_assunto_fkey FOREIGN KEY (id_assunto) REFERENCES protocolos.assunto(id);


--
-- Name: hierarquia_assunto_tipo_processo hierarquia_assunto_tipo_processo_id_assunto_pai_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.hierarquia_assunto_tipo_processo
    ADD CONSTRAINT hierarquia_assunto_tipo_processo_id_assunto_pai_fkey FOREIGN KEY (id_assunto_pai) REFERENCES protocolos.assunto(id);


--
-- Name: hierarquia_assunto_tipo_processo hierarquia_assunto_tipo_processo_id_tipo_processo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.hierarquia_assunto_tipo_processo
    ADD CONSTRAINT hierarquia_assunto_tipo_processo_id_tipo_processo_fkey FOREIGN KEY (id_tipo_processo) REFERENCES protocolos.tipo_processo(id);


--
-- Name: hierarquia_assunto_tipo_processo hierarquia_assunto_tipo_processo_id_tipo_processo_pai_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.hierarquia_assunto_tipo_processo
    ADD CONSTRAINT hierarquia_assunto_tipo_processo_id_tipo_processo_pai_fkey FOREIGN KEY (id_tipo_processo_pai) REFERENCES protocolos.tipo_processo(id);


--
-- Name: liquidacao_despesas_processo liquidacao_despesas_processo_id_feempliq_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.liquidacao_despesas_processo
    ADD CONSTRAINT liquidacao_despesas_processo_id_feempliq_fkey FOREIGN KEY (id_feempliq) REFERENCES despesas.feempliq(id);


--
-- Name: lotacoes_spu lotacoes_spu_lotacao_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.lotacoes_spu
    ADD CONSTRAINT lotacoes_spu_lotacao_id_fkey FOREIGN KEY (lotacao_id) REFERENCES protocolos.lotacoes_spu(id);


--
-- Name: movimentacao movimentacao_id_acao_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT movimentacao_id_acao_fkey FOREIGN KEY (id_acao) REFERENCES protocolos.acao(id) MATCH FULL;


--
-- Name: movimentacao movimentacao_id_arquivamento_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT movimentacao_id_arquivamento_fkey FOREIGN KEY (id_arquivamento) REFERENCES protocolos.arquivamento(id) MATCH FULL;


--
-- Name: movimentacao movimentacao_id_carimbamento_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.movimentacao
    ADD CONSTRAINT movimentacao_id_carimbamento_fkey FOREIGN KEY (id_carimbamento) REFERENCES protocolos.carimbamento(id);


--
-- Name: processo_apensamento processo_apensamento_id_processo_apensado_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_apensamento
    ADD CONSTRAINT processo_apensamento_id_processo_apensado_fkey FOREIGN KEY (id_processo_apensado) REFERENCES protocolos.processo(id);


--
-- Name: processo_apensamento processo_apensamento_id_processo_principal_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_apensamento
    ADD CONSTRAINT processo_apensamento_id_processo_principal_fkey FOREIGN KEY (id_processo_principal) REFERENCES protocolos.processo(id);


--
-- Name: processo_apensamento processo_apensamento_id_usuario_desapensamento_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_apensamento
    ADD CONSTRAINT processo_apensamento_id_usuario_desapensamento_fkey FOREIGN KEY (id_usuario_desapensamento) REFERENCES utils.usuario(id);


--
-- Name: processo_apensamento processo_apensamento_id_usuario_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_apensamento
    ADD CONSTRAINT processo_apensamento_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: processo_apensamento processo_apensamento_tenant_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_apensamento
    ADD CONSTRAINT processo_apensamento_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: processo processo_id_assunto_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_id_assunto_fkey FOREIGN KEY (id_assunto) REFERENCES protocolos.assunto(id) MATCH FULL;


--
-- Name: processo processo_id_ccd_classe_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_id_ccd_classe_fkey FOREIGN KEY (id_ccd_classe) REFERENCES protocolos.ccd_classe(id);


--
-- Name: processo processo_id_especie_documental_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_id_especie_documental_fkey FOREIGN KEY (id_especie_documental) REFERENCES protocolos.especie_documental(id);


--
-- Name: processo processo_id_manifestante_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_id_manifestante_fkey FOREIGN KEY (id_manifestante) REFERENCES protocolos.manifestante(id) MATCH FULL;


--
-- Name: processo processo_id_unidade_proprietaria_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_id_unidade_proprietaria_fkey FOREIGN KEY (id_unidade_proprietaria) REFERENCES utils.unidade_trabalho(id) MATCH FULL;


--
-- Name: processo processo_id_usuario_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo
    ADD CONSTRAINT processo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id) MATCH FULL;


--
-- Name: processo_vinculado processo_vinculado_id_movimentacao_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_vinculado
    ADD CONSTRAINT processo_vinculado_id_movimentacao_fkey FOREIGN KEY (id_movimentacao) REFERENCES protocolos.movimentacao(id);


--
-- Name: processo_volume processo_volume_id_processo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_volume
    ADD CONSTRAINT processo_volume_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES protocolos.processo(id);


--
-- Name: processo_volume processo_volume_id_usuario_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_volume
    ADD CONSTRAINT processo_volume_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES utils.usuario(id);


--
-- Name: processo_volume processo_volume_tenant_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.processo_volume
    ADD CONSTRAINT processo_volume_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: template_carimbo_secretaria template_carimbo_secretaria_id_template_carimbo_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.template_carimbo_secretaria
    ADD CONSTRAINT template_carimbo_secretaria_id_template_carimbo_fkey FOREIGN KEY (id_template_carimbo) REFERENCES protocolos.template_carimbo(id);


--
-- Name: ttd_regra ttd_regra_id_ccd_classe_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ttd_regra
    ADD CONSTRAINT ttd_regra_id_ccd_classe_fkey FOREIGN KEY (id_ccd_classe) REFERENCES protocolos.ccd_classe(id);


--
-- Name: ttd_regra ttd_regra_id_especie_documental_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ttd_regra
    ADD CONSTRAINT ttd_regra_id_especie_documental_fkey FOREIGN KEY (id_especie_documental) REFERENCES protocolos.especie_documental(id);


--
-- Name: ttd_regra ttd_regra_tenant_id_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.ttd_regra
    ADD CONSTRAINT ttd_regra_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: usuario_assinatura usuario_assinatura_id_solicitacao_assinatura_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuario_assinatura
    ADD CONSTRAINT usuario_assinatura_id_solicitacao_assinatura_fkey FOREIGN KEY (id_solicitacao_assinatura) REFERENCES protocolos.solicitacao_assinatura(id) MATCH FULL;


--
-- Name: usuario_assinatura usuario_assinatura_id_tipo_assinatura_fkey; Type: FK CONSTRAINT; Schema: protocolos; Owner: -
--

ALTER TABLE ONLY protocolos.usuario_assinatura
    ADD CONSTRAINT usuario_assinatura_id_tipo_assinatura_fkey FOREIGN KEY (id_tipo_assinatura) REFERENCES protocolos.tipo_assinatura(id) MATCH FULL;


--
-- Name: bairro bairro_id_cidade_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.bairro
    ADD CONSTRAINT bairro_id_cidade_fkey FOREIGN KEY (id_cidade) REFERENCES utils.cidade(id);


--
-- Name: cidade cidade_id_estado_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cidade
    ADD CONSTRAINT cidade_id_estado_fkey FOREIGN KEY (id_estado) REFERENCES utils.estado(id);


--
-- Name: classificacao_zona_cnae_subgrupo classificacao_zona_cnae_subgrupo_id_situacao_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.classificacao_zona_cnae_subgrupo
    ADD CONSTRAINT classificacao_zona_cnae_subgrupo_id_situacao_fkey FOREIGN KEY (id_situacao) REFERENCES utils.situacoes(id);


--
-- Name: classificacao_zona_cnae_subgrupo classificacao_zona_cnae_subgrupo_id_subgrupo_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.classificacao_zona_cnae_subgrupo
    ADD CONSTRAINT classificacao_zona_cnae_subgrupo_id_subgrupo_fkey FOREIGN KEY (id_subgrupo) REFERENCES utils.cnae_subgrupo(id);


--
-- Name: classificacao_zona_cnae_subgrupo classificacao_zona_cnae_subgrupo_id_zona_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.classificacao_zona_cnae_subgrupo
    ADD CONSTRAINT classificacao_zona_cnae_subgrupo_id_zona_fkey FOREIGN KEY (id_zona) REFERENCES utils.zona(id);


--
-- Name: cnae cnae_id_subgrupo_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae
    ADD CONSTRAINT cnae_id_subgrupo_fkey FOREIGN KEY (id_subgrupo) REFERENCES utils.cnae_subgrupo(id);


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ cnae_risco_tipos_risco_classi_id_cnae_risco_tipos_risco_cl_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ
    ADD CONSTRAINT cnae_risco_tipos_risco_classi_id_cnae_risco_tipos_risco_cl_fkey FOREIGN KEY (id_cnae_risco_tipos_risco_classificacoes) REFERENCES utils.cnae_risco_tipos_risco_classificacoes(id);


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ cnae_risco_tipos_risco_classi_id_perguntas_atividades_econ_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ
    ADD CONSTRAINT cnae_risco_tipos_risco_classi_id_perguntas_atividades_econ_fkey FOREIGN KEY (id_perguntas_atividades_economicas) REFERENCES utils.perguntas_atividades_economicas(id);


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ cnae_risco_tipos_risco_classif_id_risco_classificacoes_nao_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ
    ADD CONSTRAINT cnae_risco_tipos_risco_classif_id_risco_classificacoes_nao_fkey FOREIGN KEY (id_risco_classificacoes_nao) REFERENCES utils.risco_classificacoes(id);


--
-- Name: cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ cnae_risco_tipos_risco_classif_id_risco_classificacoes_sim_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes_perguntas_atividades_econ
    ADD CONSTRAINT cnae_risco_tipos_risco_classif_id_risco_classificacoes_sim_fkey FOREIGN KEY (id_risco_classificacoes_sim) REFERENCES utils.risco_classificacoes(id);


--
-- Name: cnae_risco_tipos_risco_classificacoes cnae_risco_tipos_risco_classificac_id_risco_classificacoes_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes
    ADD CONSTRAINT cnae_risco_tipos_risco_classificac_id_risco_classificacoes_fkey FOREIGN KEY (id_risco_classificacoes) REFERENCES utils.risco_classificacoes(id);


--
-- Name: cnae_risco_tipos_risco_classificacoes cnae_risco_tipos_risco_classificacoes_id_cnae_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes
    ADD CONSTRAINT cnae_risco_tipos_risco_classificacoes_id_cnae_fkey FOREIGN KEY (id_cnae) REFERENCES utils.cnae(id);


--
-- Name: cnae_risco_tipos_risco_classificacoes cnae_risco_tipos_risco_classificacoes_id_risco_tipos_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_risco_tipos_risco_classificacoes
    ADD CONSTRAINT cnae_risco_tipos_risco_classificacoes_id_risco_tipos_fkey FOREIGN KEY (id_risco_tipos) REFERENCES utils.risco_tipos(id);


--
-- Name: cnae_subgrupo cnae_subgrupo_id_cnae_subgrupo_empresasimples_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_subgrupo
    ADD CONSTRAINT cnae_subgrupo_id_cnae_subgrupo_empresasimples_fkey FOREIGN KEY (id_cnae_subgrupo_empresasimples) REFERENCES empresasimples.cnae_subgrupos(id);


--
-- Name: cnae_subgrupo cnae_subgrupo_id_grupo_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.cnae_subgrupo
    ADD CONSTRAINT cnae_subgrupo_id_grupo_fkey FOREIGN KEY (id_grupo) REFERENCES utils.cnae_grupo(id);


--
-- Name: distrito distrito_id_cidade_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.distrito
    ADD CONSTRAINT distrito_id_cidade_fkey FOREIGN KEY (id_cidade) REFERENCES utils.cidade(id);


--
-- Name: endereco endereco_id_bairro_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_id_bairro_fkey FOREIGN KEY (id_bairro) REFERENCES utils.bairro(id);


--
-- Name: endereco endereco_id_cidade_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_id_cidade_fkey FOREIGN KEY (id_cidade) REFERENCES utils.cidade(id);


--
-- Name: endereco endereco_id_comprovante_residencia_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_id_comprovante_residencia_fkey FOREIGN KEY (id_comprovante_residencia) REFERENCES utils.arquivo(id);


--
-- Name: endereco endereco_id_distrito_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_id_distrito_fkey FOREIGN KEY (id_distrito) REFERENCES utils.distrito(id);


--
-- Name: endereco endereco_id_estado_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_id_estado_fkey FOREIGN KEY (id_estado) REFERENCES utils.estado(id);


--
-- Name: endereco endereco_id_localidade_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_id_localidade_fkey FOREIGN KEY (id_localidade) REFERENCES utils.localidade(id);


--
-- Name: endereco endereco_id_pais_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT endereco_id_pais_fkey FOREIGN KEY (id_pais) REFERENCES utils.pais(id);


--
-- Name: estado estado_id_regiao_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.estado
    ADD CONSTRAINT estado_id_regiao_fkey FOREIGN KEY (id_regiao) REFERENCES utils.regiao(id);


--
-- Name: endereco fk_endereco_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.endereco
    ADD CONSTRAINT fk_endereco_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: grupo fk_grupo_nivel; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo
    ADD CONSTRAINT fk_grupo_nivel FOREIGN KEY (id_nivel) REFERENCES utils.nivel(id);


--
-- Name: grupo fk_grupo_sistema; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo
    ADD CONSTRAINT fk_grupo_sistema FOREIGN KEY (id_sistema) REFERENCES utils.sistema(id);


--
-- Name: grupo fk_grupo_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo
    ADD CONSTRAINT fk_grupo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: grupo_transacao fk_grupo_transacao_grupo; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao
    ADD CONSTRAINT fk_grupo_transacao_grupo FOREIGN KEY (id_grupo) REFERENCES utils.grupo(id);


--
-- Name: grupo_transacao fk_grupo_transacao_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao
    ADD CONSTRAINT fk_grupo_transacao_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: grupo_transacao fk_grupo_transacao_transacao; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao
    ADD CONSTRAINT fk_grupo_transacao_transacao FOREIGN KEY (id_transacao) REFERENCES utils.transacao(id);


--
-- Name: servico_origem fk_id_icone; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servico_origem
    ADD CONSTRAINT fk_id_icone FOREIGN KEY (id_icone) REFERENCES utils.icone(id);


--
-- Name: sistema_constante fk_sistema_constante_sistema; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_constante
    ADD CONSTRAINT fk_sistema_constante_sistema FOREIGN KEY (id_sistema) REFERENCES utils.sistema(id);


--
-- Name: sistema_transacao fk_sistema_transacao_sistema; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_transacao
    ADD CONSTRAINT fk_sistema_transacao_sistema FOREIGN KEY (id_sistema) REFERENCES utils.sistema(id);


--
-- Name: sistema_transacao fk_sistema_transacao_transacao; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_transacao
    ADD CONSTRAINT fk_sistema_transacao_transacao FOREIGN KEY (id_transacao) REFERENCES utils.transacao(id);


--
-- Name: sistema_usuario fk_sistema_usuario_sistema; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_usuario
    ADD CONSTRAINT fk_sistema_usuario_sistema FOREIGN KEY (id_sistema) REFERENCES utils.sistema(id);


--
-- Name: sistema_usuario fk_sistema_usuario_tipo_usuario; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.sistema_usuario
    ADD CONSTRAINT fk_sistema_usuario_tipo_usuario FOREIGN KEY (id_tipo_usuario) REFERENCES utils.tipo_usuario(id);


--
-- Name: tipo_unidade_trabalho fk_tipo_unidade_trabalho_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.tipo_unidade_trabalho
    ADD CONSTRAINT fk_tipo_unidade_trabalho_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: unidade_trabalho fk_unidade_trabalho_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.unidade_trabalho
    ADD CONSTRAINT fk_unidade_trabalho_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: usuario_externo fk_usuario_externo_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_externo
    ADD CONSTRAINT fk_usuario_externo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: usuario_grupo fk_usuario_grupo_grupo; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_grupo
    ADD CONSTRAINT fk_usuario_grupo_grupo FOREIGN KEY (id_grupo) REFERENCES utils.grupo(id);


--
-- Name: usuario_grupo fk_usuario_grupo_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_grupo
    ADD CONSTRAINT fk_usuario_grupo_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: usuario fk_usuario_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario
    ADD CONSTRAINT fk_usuario_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: usuario fk_usuario_unidade_trabalho; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario
    ADD CONSTRAINT fk_usuario_unidade_trabalho FOREIGN KEY (id_unidade_trabalho) REFERENCES utils.unidade_trabalho(id);


--
-- Name: usuario_unidade_trabalho fk_usuario_unidade_trabalho_tenant_id; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.usuario_unidade_trabalho
    ADD CONSTRAINT fk_usuario_unidade_trabalho_tenant_id FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id);


--
-- Name: grupo_externo grupo_externo_id_sistema_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_externo
    ADD CONSTRAINT grupo_externo_id_sistema_fkey FOREIGN KEY (id_sistema) REFERENCES utils.sistema(id);


--
-- Name: grupo_transacao_externa grupo_transacao_externa_id_grupo_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao_externa
    ADD CONSTRAINT grupo_transacao_externa_id_grupo_fkey FOREIGN KEY (id_grupo) REFERENCES utils.grupo_externo(id);


--
-- Name: grupo_transacao_externa grupo_transacao_externa_id_transacao_externa_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_transacao_externa
    ADD CONSTRAINT grupo_transacao_externa_id_transacao_externa_fkey FOREIGN KEY (id_transacao_externa) REFERENCES utils.transacao_externa(id);


--
-- Name: grupo_usuario_externo grupo_usuario_externo_id_grupo_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.grupo_usuario_externo
    ADD CONSTRAINT grupo_usuario_externo_id_grupo_fkey FOREIGN KEY (id_grupo) REFERENCES utils.grupo_externo(id);


--
-- Name: localidade localidade_id_cidade_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.localidade
    ADD CONSTRAINT localidade_id_cidade_fkey FOREIGN KEY (id_cidade) REFERENCES utils.cidade(id);


--
-- Name: localidade localidade_id_distrito_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.localidade
    ADD CONSTRAINT localidade_id_distrito_fkey FOREIGN KEY (id_distrito) REFERENCES utils.distrito(id);


--
-- Name: metricas metricas_id_sistema_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.metricas
    ADD CONSTRAINT metricas_id_sistema_fkey FOREIGN KEY (id_sistema) REFERENCES utils.sistema(id);


--
-- Name: perguntas_atividades_economicas_resposta perguntas_atividades_economic_id_perguntas_atividades_econ_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas_resposta
    ADD CONSTRAINT perguntas_atividades_economic_id_perguntas_atividades_econ_fkey FOREIGN KEY (id_perguntas_atividades_economicas) REFERENCES utils.perguntas_atividades_economicas(id);


--
-- Name: perguntas_atividades_economicas_resposta perguntas_atividades_economicas_resposta_id_cnae_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas_resposta
    ADD CONSTRAINT perguntas_atividades_economicas_resposta_id_cnae_fkey FOREIGN KEY (id_cnae) REFERENCES utils.cnae(id);


--
-- Name: perguntas_atividades_economicas_resposta perguntas_atividades_economicas_resposta_id_risco_tipos_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.perguntas_atividades_economicas_resposta
    ADD CONSTRAINT perguntas_atividades_economicas_resposta_id_risco_tipos_fkey FOREIGN KEY (id_risco_tipos) REFERENCES utils.risco_tipos(id);


--
-- Name: pessoa pessoa_id_arquivo_foto_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.pessoa
    ADD CONSTRAINT pessoa_id_arquivo_foto_fkey FOREIGN KEY (id_arquivo_foto) REFERENCES utils.arquivo(id);


--
-- Name: pessoa pessoa_id_usuario_auditoria_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.pessoa
    ADD CONSTRAINT pessoa_id_usuario_auditoria_fkey FOREIGN KEY (id_usuario_auditoria) REFERENCES utils.usuario(id);


--
-- Name: risco_tipos_enquadramentos risco_tipos_enquadramentos_id_risco_tipos_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos_enquadramentos
    ADD CONSTRAINT risco_tipos_enquadramentos_id_risco_tipos_fkey FOREIGN KEY (id_risco_tipos) REFERENCES utils.risco_tipos(id);


--
-- Name: risco_tipos_enquadramentos_regras risco_tipos_enquadramentos_re_id_risco_tipos_enquadramento_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.risco_tipos_enquadramentos_regras
    ADD CONSTRAINT risco_tipos_enquadramentos_re_id_risco_tipos_enquadramento_fkey FOREIGN KEY (id_risco_tipos_enquadramentos) REFERENCES utils.risco_tipos_enquadramentos(id);


--
-- Name: servico_unidade_trabalho servico_unidade_trabalho_fk; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servico_unidade_trabalho
    ADD CONSTRAINT servico_unidade_trabalho_fk FOREIGN KEY (id_tipo_servico) REFERENCES utils.tipo_servico(id);


--
-- Name: servico_unidade_trabalho servico_unidade_trabalho_id_servico_origem_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.servico_unidade_trabalho
    ADD CONSTRAINT servico_unidade_trabalho_id_servico_origem_fkey FOREIGN KEY (id_servico_origem) REFERENCES utils.servico_origem(id);


--
-- Name: transacao_externa transacao_externa_id_sistema_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.transacao_externa
    ADD CONSTRAINT transacao_externa_id_sistema_fkey FOREIGN KEY (id_sistema) REFERENCES utils.sistema(id);


--
-- Name: unidade_trabalho unidade_trabalho_id_unidade_pai_fkey; Type: FK CONSTRAINT; Schema: utils; Owner: -
--

ALTER TABLE ONLY utils.unidade_trabalho
    ADD CONSTRAINT unidade_trabalho_id_unidade_pai_fkey FOREIGN KEY (id_unidade_pai) REFERENCES utils.unidade_trabalho(id);


--
-- Name: audit_log; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: job; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.job ENABLE ROW LEVEL SECURITY;

--
-- Name: notificacao; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.notificacao ENABLE ROW LEVEL SECURITY;

--
-- Name: notificacao_preferencia; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.notificacao_preferencia ENABLE ROW LEVEL SECURITY;

--
-- Name: nup_sequencia; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.nup_sequencia ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_log tenant_isolation_insert; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_insert ON aprimora_py.audit_log FOR INSERT WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: job tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.job USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: notificacao tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.notificacao USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: notificacao_preferencia tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.notificacao_preferencia USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: nup_sequencia tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.nup_sequencia USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_processo_workflow tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.tipo_processo_workflow USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_definition tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.workflow_definition USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_instance tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.workflow_instance USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_sla_alerta tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.workflow_sla_alerta USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_transicao_log tenant_isolation_modify; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_modify ON aprimora_py.workflow_transicao_log USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: audit_log tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.audit_log FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: job tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.job FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: notificacao tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.notificacao FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: notificacao_preferencia tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.notificacao_preferencia FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: nup_sequencia tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.nup_sequencia FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_processo_workflow tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.tipo_processo_workflow FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_definition tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.workflow_definition FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_instance tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.workflow_instance FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_sla_alerta tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.workflow_sla_alerta FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: workflow_transicao_log tenant_isolation_select; Type: POLICY; Schema: aprimora_py; Owner: -
--

CREATE POLICY tenant_isolation_select ON aprimora_py.workflow_transicao_log FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_processo_workflow; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.tipo_processo_workflow ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_definition; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.workflow_definition ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_instance; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.workflow_instance ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_sla_alerta; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.workflow_sla_alerta ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_transicao_log; Type: ROW SECURITY; Schema: aprimora_py; Owner: -
--

ALTER TABLE aprimora_py.workflow_transicao_log ENABLE ROW LEVEL SECURITY;

--
-- Name: anexo; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.anexo ENABLE ROW LEVEL SECURITY;

--
-- Name: anexo_processo; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.anexo_processo ENABLE ROW LEVEL SECURITY;

--
-- Name: arquivamento; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.arquivamento ENABLE ROW LEVEL SECURITY;

--
-- Name: assinatura_anexo; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.assinatura_anexo ENABLE ROW LEVEL SECURITY;

--
-- Name: assunto; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.assunto ENABLE ROW LEVEL SECURITY;

--
-- Name: assunto_tipo_processo_tipo_anexo; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.assunto_tipo_processo_tipo_anexo ENABLE ROW LEVEL SECURITY;

--
-- Name: ccd_classe; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.ccd_classe ENABLE ROW LEVEL SECURITY;

--
-- Name: despacho; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.despacho ENABLE ROW LEVEL SECURITY;

--
-- Name: encaminhamento; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.encaminhamento ENABLE ROW LEVEL SECURITY;

--
-- Name: especie_documental; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.especie_documental ENABLE ROW LEVEL SECURITY;

--
-- Name: manifestante; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.manifestante ENABLE ROW LEVEL SECURITY;

--
-- Name: movimentacao; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.movimentacao ENABLE ROW LEVEL SECURITY;

--
-- Name: processo; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.processo ENABLE ROW LEVEL SECURITY;

--
-- Name: processo_apensamento; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.processo_apensamento ENABLE ROW LEVEL SECURITY;

--
-- Name: processo_volume; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.processo_volume ENABLE ROW LEVEL SECURITY;

--
-- Name: solicitacao_assinatura; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.solicitacao_assinatura ENABLE ROW LEVEL SECURITY;

--
-- Name: anexo tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.anexo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: anexo_processo tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.anexo_processo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: arquivamento tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.arquivamento USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: assinatura_anexo tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.assinatura_anexo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: assunto tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.assunto USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: assunto_tipo_processo_tipo_anexo tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.assunto_tipo_processo_tipo_anexo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: ccd_classe tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.ccd_classe USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: despacho tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.despacho USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: encaminhamento tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.encaminhamento USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: especie_documental tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.especie_documental USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: manifestante tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.manifestante USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: movimentacao tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.movimentacao USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: processo tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.processo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: processo_apensamento tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.processo_apensamento USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: processo_volume tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.processo_volume USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: solicitacao_assinatura tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.solicitacao_assinatura USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_anexo tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.tipo_anexo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_manifestante tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.tipo_manifestante USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_processo tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.tipo_processo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: ttd_regra tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.ttd_regra USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_assinatura tenant_isolation_modify; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_modify ON protocolos.usuario_assinatura USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: anexo tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.anexo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: anexo_processo tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.anexo_processo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: arquivamento tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.arquivamento FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: assinatura_anexo tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.assinatura_anexo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: assunto tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.assunto FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: assunto_tipo_processo_tipo_anexo tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.assunto_tipo_processo_tipo_anexo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: ccd_classe tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.ccd_classe FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: despacho tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.despacho FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: encaminhamento tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.encaminhamento FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: especie_documental tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.especie_documental FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: manifestante tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.manifestante FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: movimentacao tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.movimentacao FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: processo tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.processo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: processo_apensamento tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.processo_apensamento FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: processo_volume tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.processo_volume FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: solicitacao_assinatura tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.solicitacao_assinatura FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_anexo tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.tipo_anexo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_manifestante tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.tipo_manifestante FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_processo tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.tipo_processo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: ttd_regra tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.ttd_regra FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_assinatura tenant_isolation_select; Type: POLICY; Schema: protocolos; Owner: -
--

CREATE POLICY tenant_isolation_select ON protocolos.usuario_assinatura FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_anexo; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.tipo_anexo ENABLE ROW LEVEL SECURITY;

--
-- Name: tipo_manifestante; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.tipo_manifestante ENABLE ROW LEVEL SECURITY;

--
-- Name: tipo_processo; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.tipo_processo ENABLE ROW LEVEL SECURITY;

--
-- Name: ttd_regra; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.ttd_regra ENABLE ROW LEVEL SECURITY;

--
-- Name: usuario_assinatura; Type: ROW SECURITY; Schema: protocolos; Owner: -
--

ALTER TABLE protocolos.usuario_assinatura ENABLE ROW LEVEL SECURITY;

--
-- Name: endereco; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.endereco ENABLE ROW LEVEL SECURITY;

--
-- Name: grupo; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.grupo ENABLE ROW LEVEL SECURITY;

--
-- Name: grupo_transacao; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.grupo_transacao ENABLE ROW LEVEL SECURITY;

--
-- Name: endereco tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.endereco USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: grupo tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.grupo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: grupo_transacao tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.grupo_transacao USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_unidade_trabalho tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.tipo_unidade_trabalho USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: unidade_trabalho tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.unidade_trabalho USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.usuario USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_externo tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.usuario_externo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_grupo tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.usuario_grupo USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_unidade_trabalho tenant_isolation_modify; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_modify ON utils.usuario_unidade_trabalho USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: endereco tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.endereco FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: grupo tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.grupo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: grupo_transacao tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.grupo_transacao FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_unidade_trabalho tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.tipo_unidade_trabalho FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: unidade_trabalho tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.unidade_trabalho FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.usuario FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_externo tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.usuario_externo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_grupo tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.usuario_grupo FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: usuario_unidade_trabalho tenant_isolation_select; Type: POLICY; Schema: utils; Owner: -
--

CREATE POLICY tenant_isolation_select ON utils.usuario_unidade_trabalho FOR SELECT USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::integer));


--
-- Name: tipo_unidade_trabalho; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.tipo_unidade_trabalho ENABLE ROW LEVEL SECURITY;

--
-- Name: unidade_trabalho; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.unidade_trabalho ENABLE ROW LEVEL SECURITY;

--
-- Name: usuario; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.usuario ENABLE ROW LEVEL SECURITY;

--
-- Name: usuario_externo; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.usuario_externo ENABLE ROW LEVEL SECURITY;

--
-- Name: usuario_grupo; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.usuario_grupo ENABLE ROW LEVEL SECURITY;

--
-- Name: usuario_unidade_trabalho; Type: ROW SECURITY; Schema: utils; Owner: -
--

ALTER TABLE utils.usuario_unidade_trabalho ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--


