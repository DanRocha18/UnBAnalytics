"""
Script para processar múltiplos arquivos PDF de históricos acadêmicos da UnB,
extrair informações detalhadas e estruturá-las em arquivos JSON.
"""

import pdfplumber
import re
import json
import sys
import os

def _limpar_celula(texto):
    """Função auxiliar para remover quebras de linha e espaços extras."""
    return texto.replace('\n', ' ').strip() if texto else ""

def _extrair_ch_numerico(ch_texto):
    """Extrai o valor numérico de uma string de carga horária (ex: '60 h' -> 60)."""
    if not ch_texto:
        return 0
    # Lida com '60 h' ou apenas '60'
    ch_str = str(ch_texto).lower().replace('h', '').strip()
    match = re.search(r"^(\d+)", ch_str)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            pass
    return 0

def _extrair_dados_pessoais_completo(texto_pagina):
    """
    Extrai todos os dados pessoais. Funciona com `extract_text()` sem layout.
    """
    dados = {
        'nome': None,
        'matricula': None,
        'ira': None,
        'curso_codigo_nome': None,
        'status': None,
        'cpf': None,
        'nascimento': None,
        'data_emissao': None
    }

    padroes = {
        'nome': r"Nome:\s*([^\n]+)",
        'matricula': r"Matrícula:\s*(\d+)",
        'ira': r"IRA:\s*([\d\.]+)",
        'curso_codigo_nome': r"Curso:\s*([^\n]+)",
        'status': r"Status:\s*([^\n]+)",
        'cpf': r"Nº do CPF:\s*([^\n]+)",
        'nascimento': r"Data de Nascimento:\s*([\d\/]+)",
        'data_emissao': r"Emitido em:\s*([^\n]+)"
    }

    for chave, padrao in padroes.items():
        match = re.search(padrao, texto_pagina, re.IGNORECASE)
        if match:
            dados[chave] = _limpar_celula(match.group(1))

    # Limpeza pós-extração
    if dados['nome']:
         dados['nome'] = dados['nome'].split('Data de Nascimento:')[0].strip()
    if dados['cpf']:
        dados['cpf'] = dados['cpf'].split(' ')[0].strip()
    if dados['status']:
         dados['status'] = dados['status'].split(' ')[0].strip()
    if dados['curso_codigo_nome']:
         dados['curso_codigo_nome'] = dados['curso_codigo_nome'].split('Currículo:')[0].strip()

    if dados['ira']:
        try:
            dados['ira'] = float(dados['ira'])
        except (ValueError, TypeError):
            dados['ira'] = None

    return dados

def _processar_tabela_cursados(tabela, indice_cabecalho):
    """
    Processa uma tabela de componentes curriculares cursados.
    ÍNDICES CORRIGIDOS:
    [0]Ano.Período, [1]Status(*), [2]Cód., [3]Nome, [4]CH, [5]Turma,
    [6]Freq, [7]Nota, [8]Situação
    """
    componentes_cursados = []
    for linha in tabela[indice_cabecalho + 1:]:
        if len(linha) >= 9 and linha[0] and re.match(r'\d{4}\.\d', _limpar_celula(linha[0])):
            componente = {
                "ano_periodo": _limpar_celula(linha[0]),
                "codigo": _limpar_celula(linha[2]),
                "nome": _limpar_celula(linha[3]),
                "ch": _extrair_ch_numerico(linha[4]),
                "turma": _limpar_celula(linha[5]),
                "freq": _limpar_celula(linha[6]),
                "nota": _limpar_celula(linha[7]),
                "situacao": _limpar_celula(linha[8])
            }
            componentes_cursados.append(componente)
        elif len(linha) >= 8 and "ENADE" in _limpar_celula(linha[2]):
             componente = {
                "ano_periodo": _limpar_celula(linha[0]),
                "codigo": "ENADE",
                "nome": _limpar_celula(linha[3]),
                "ch": 0,
                "turma": _limpar_celula(linha[4]),
                "freq": _limpar_celula(linha[5]),
                "nota": _limpar_celula(linha[6]),
                "situacao": _limpar_celula(linha[7])
            }
             componentes_cursados.append(componente)
    return componentes_cursados

def _processar_tabela_pendentes(tabela):
    """
    Processa tabelas de componentes pendentes (Obrigatórios ou Optativos).
    v16: Baseado na LÓGICA ORIGINAL DO USUÁRIO (que funciona).
    Itera a partir de tabela[1] e espera 3 colunas: [0]Cód, [1]Nome, [2]CH.
    Adiciona um filtro para ignorar a linha de cabeçalho.
    """
    componentes_pendentes = []
    for linha in tabela[1:]: # Começa da linha 1 (provado pelo JSON original)
        
        # O filtro do script original: len >= 3 e linha[0] existe
        if len(linha) >= 3 and linha[0]:
            codigo_limpo = _limpar_celula(linha[0])
            
            # Filtro de Maestria: Ignora a linha de cabeçalho que o original capturava
            if codigo_limpo.lower() == "código":
                continue
            
            componente = {
                "codigo": codigo_limpo,
                "nome": _limpar_celula(linha[1]),
                "ch": _extrair_ch_numerico(linha[2]) # Converte para int
            }
            componentes_pendentes.append(componente)
    return componentes_pendentes

def analisar_historico_unb(caminho_pdf):
    """
    Analisa um arquivo PDF de histórico da UnB (v16.0).
    Usa `extract_text()` (sem layout) para Dados Pessoais.
    Usa `extract_tables()` (sem args) para as listas.
    Ignora `cargas_horarias_pendentes`.
    Usa a lógica de detecção ORIGINAL do usuário para pendentes.
    """
    dados_finais = {
        "dados_pessoais": {},
        "cargas_horarias_pendentes": {
            "obrigatoria_pendente_ch": 0,
            "optativa_pendente_ch": 0,
            "complementar_pendente_ch": 0
        },
        "componentes_cursados": [],
        "componentes_pendentes": []
    }
    
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            
            #  1. Extração de Texto
            texto_pagina_1_simples = pdf.pages[0].extract_text()
            if texto_pagina_1_simples:
                dados_finais["dados_pessoais"] = _extrair_dados_pessoais_completo(texto_pagina_1_simples)
            
            # 2. Extração de Tabelas
            for page in pdf.pages:
                tabelas = page.extract_tables()

                for tabela in tabelas:
                    if not tabela or not tabela[0] or not tabela[0][0]:
                        continue

                    #  Detecção de Tabela
                    header_l0_str = _limpar_celula(str(tabela[0]))

                    # 1. Tabela Cursados
                    if 'Componente Curricular' in header_l0_str and 'Situação' in header_l0_str and 'Nota' in header_l0_str:
                        dados_finais["componentes_cursados"].extend(_processar_tabela_cursados(tabela, 0))

                    # 2. Tabela Pendentes
                    elif 'Componentes Curriculares Obrigatórios Pendentes' in header_l0_str:
                        dados_finais["componentes_pendentes"].extend(_processar_tabela_pendentes(tabela))

                    # 3. Tabela Pendentes
                    elif 'Componentes Optativos - Pendentes' in header_l0_str:
                         dados_finais["componentes_pendentes"].extend(_processar_tabela_pendentes(tabela))
            
            # 3. Desduplicar listas
            def desduplicar_lista_de_dicionarios(lista):
                vistos = set()
                lista_unica = []
                for d in lista:
                    representacao = tuple(sorted(d.items()))
                    if representacao not in vistos:
                        vistos.add(representacao)
                        lista_unica.append(d)
                return lista_unica

            dados_finais["componentes_cursados"] = desduplicar_lista_de_dicionarios(dados_finais["componentes_cursados"])
            dados_finais["componentes_pendentes"] = desduplicar_lista_de_dicionarios(dados_finais["componentes_pendentes"])

            return dados_finais
        
    except Exception as e:
        print(f"  [ERRO FATAL] Ocorreu um erro ao processar o PDF {caminho_pdf}: {e}", file=sys.stderr)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f"  [DEBUG] Erro na linha {exc_tb.tb_lineno}", file=sys.stderr)
        return None

if __name__ == '__main__':
    try:
        dir_base = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        dir_base = os.path.abspath('.')
        
    dir_entrada = os.path.join(dir_base, "dados", "historicos_emitidos")
    dir_saida = os.path.join(dir_base, "dados", "dados_estruturados_historico")

    print(f"Iniciando processamento de históricos (v16.0 - Lógica de Detecção Original)...")
    print(f"Diretório de entrada: {dir_entrada}")
    print(f"Diretório de saída: {dir_saida}")

    if not os.path.isdir(dir_entrada):
        print(f"Erro: Diretório de entrada não encontrado: {dir_entrada}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(dir_saida, exist_ok=True)

    arquivos_processados = 0
    arquivos_falha = 0
    
    try:
        lista_arquivos_pdf = [f for f in os.listdir(dir_entrada) if f.lower().endswith(".pdf")]
    except FileNotFoundError:
        print(f"Erro: Diretório de entrada não encontrado no path: {dir_entrada}", file=sys.stderr)
        sys.exit(1)
    
    if not lista_arquivos_pdf:
        print("Nenhum arquivo PDF encontrado no diretório de entrada.")

    for nome_arquivo in lista_arquivos_pdf:
        caminho_pdf_completo = os.path.join(dir_entrada, nome_arquivo)
        print(f"\nProcessando arquivo: {nome_arquivo}...")
        
        dados_do_historico = analisar_historico_unb(caminho_pdf_completo)
        
        if dados_do_historico and dados_do_historico.get("dados_pessoais", {}).get('matricula'):
            matricula = dados_do_historico["dados_pessoais"]["matricula"]
            nome_base_json = f"historico_{matricula}.json"
            
            caminho_json_completo = os.path.join(dir_saida, nome_base_json)

            try:
                with open(caminho_json_completo, 'w', encoding='utf-8') as f_json:
                    json.dump(dados_do_historico, f_json, ensure_ascii=False, indent=4)
                print(f"  Análise concluída. Resultado salvo em: {caminho_json_completo}")
                arquivos_processados += 1
            except Exception as e:
                print(f"  [ERRO] Erro ao salvar JSON para {nome_arquivo}: {e}", file=sys.stderr)
                arquivos_falha += 1
        else:
            print(f"  [ERRO] Falha ao processar ou extrair dados essenciais: {nome_arquivo}")
            arquivos_falha += 1

    print(f"\n--- Processamento de Históricos Concluído ---")
    print(f"Total de arquivos PDF encontrados: {len(lista_arquivos_pdf)}")
    print(f"Arquivos processados com sucesso: {arquivos_processados}")
    print(f"Arquivos com falha no processamento: {arquivos_falha}")

