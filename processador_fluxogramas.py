"""
Script para processar múltiplos arquivos PDF de fluxogramas de cursos da UnB,
extrair informações das disciplinas e estruturá-las em arquivos JSON.

Este script lê PDFs da pasta 'dados/fluxogramas_emitidos' e salva os JSONs
resultantes na pasta 'dados/dados_estruturados_fluxos'.
"""

import pdfplumber
import re
import json
import os
import sys
from collections import defaultdict

def limpar_texto(texto):
    """Remove espaços extras e quebras de linha."""
    return ' '.join(texto.split()) if texto else ""

def extrair_carga_horaria(ch_detalhada_texto):
    """
    Extrai a carga horária total e detalhada (aula, orientação) de uma string.
    Exemplo: "60h Aula" -> {"total_h": 60, "aula_h": 60, "orientacao_h": 0}
             "90h Orientação Acadêmica/Profissional" -> {"total_h": 90, "aula_h": 0, "orientacao_h": 90}
    """
    ch_detalhada_texto = limpar_texto(ch_detalhada_texto)
    carga_horaria = {"total_h": 0, "aula_h": 0, "orientacao_h": 0}

    # Tenta extrair o total de horas
    total_match = re.match(r"(\d+)\s*h", ch_detalhada_texto)
    if total_match:
        carga_horaria["total_h"] = int(total_match.group(1))

    # Tenta extrair horas de aula
    aula_match = re.search(r"(\d+)\s*h\s*Aula", ch_detalhada_texto, re.IGNORECASE)
    if aula_match:
        carga_horaria["aula_h"] = int(aula_match.group(1))
        # Se só encontrou Aula, assume que é o total
        if carga_horaria["total_h"] == 0:
             carga_horaria["total_h"] = carga_horaria["aula_h"]

    # Tenta extrair horas de orientação
    orientacao_match = re.search(r"(\d+)\s*h\s*Orientação", ch_detalhada_texto, re.IGNORECASE)
    if orientacao_match:
        carga_horaria["orientacao_h"] = int(orientacao_match.group(1))
        # Se só encontrou Orientação, assume que é o total
        if carga_horaria["total_h"] == 0:
             carga_horaria["total_h"] = carga_horaria["orientacao_h"]

    # Se total_h ainda for 0, tenta pegar qualquer número seguido de 'h'
    if carga_horaria["total_h"] == 0:
        match_geral = re.search(r"(\d+)\s*h", ch_detalhada_texto)
        if match_geral:
            carga_horaria["total_h"] = int(match_geral.group(1))

    # Se aula e orientação somam o total, ótimo. Senão, ajusta aula_h se possível.
    if carga_horaria["aula_h"] == 0 and carga_horaria["orientacao_h"] == 0 and carga_horaria["total_h"] > 0:
        carga_horaria["aula_h"] = carga_horaria["total_h"] # Assume Aula se não especificado
    elif carga_horaria["aula_h"] + carga_horaria["orientacao_h"] != carga_horaria["total_h"] and carga_horaria["total_h"] > 0:
         # Heurística: Se a soma não bate, prioriza aula_h se for igual ao total_h
         if carga_horaria["aula_h"] == carga_horaria["total_h"]:
              carga_horaria["orientacao_h"] = 0
         elif carga_horaria["orientacao_h"] == carga_horaria["total_h"]:
              carga_horaria["aula_h"] = 0
         # Senão, mantém como extraído (pode indicar erro no PDF ou parsing)


    return carga_horaria

def extrair_info_curso(texto_primeira_pagina):
    """Extrai informações gerais do curso da primeira página."""
    info = {}
    # Regex para capturar dados chave=valor
    patterns = {
        "codigo_matriz": r"Código:\s*([\w\/]+)",
        "nome_matriz": r"Matriz Curricular:\s*(.*?)(?=\n)",
        "unidade_vinculacao": r"Unidade de Vinculação:\s*(.*?)(?=\n)",
        "carga_horaria_minima": r"Carga Horária Mínima:\s*(\d+h?)",
        "prazo_minimo": r"Mínimo:\s*(\d+)",
        "prazo_medio": r"Médio:\s*(\d+)",
        "prazo_maximo": r"Máximo:\s*(\d+)"
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, texto_primeira_pagina, re.IGNORECASE)
        if match:
            info[key] = limpar_texto(match.group(1))
        else:
            info[key] = None # Ou um valor padrão

    # Ajusta carga horaria
    if info["carga_horaria_minima"]:
        ch_match = re.search(r"(\d+)", info["carga_horaria_minima"])
        if ch_match:
            info["carga_horaria_minima"] = int(ch_match.group(1))

    # Junta prazos
    if info["prazo_minimo"] or info["prazo_medio"] or info["prazo_maximo"]:
         info["prazos_semestres"] = {
              "minimo": int(info["prazo_minimo"]) if info["prazo_minimo"] else None,
              "medio": int(info["prazo_medio"]) if info["prazo_medio"] else None,
              "maximo": int(info["prazo_maximo"]) if info["prazo_maximo"] else None,
         }
    # Remove as chaves individuais de prazo
    info.pop("prazo_minimo", None)
    info.pop("prazo_medio", None)
    info.pop("prazo_maximo", None)


    return info

def processar_fluxograma_pdf(pdf_path):
    """Processa um único PDF de fluxograma e retorna dados estruturados."""
    dados_fluxo = {
        "curso_info": {},
        "niveis": defaultdict(list),
        "optativas": []
    }
    texto_completo = ""
    nivel_atual = None
    processando_optativas = False
    processando_nivel = False

    # Regex para identificar início de seção de nível ou optativas
    regex_nivel = re.compile(r"(\d+)\s*(?:º|o|ª|a)?\s*Nível")
    regex_optativas = re.compile(r"Componentes Optativos")
    # Regex para identificar uma linha de disciplina (flexível)
    # Formato: CODIGO NOME [-] CH DETALHADA TIPO NATUREZA (Tipo e Natureza podem estar em outra linha/coluna)
    # Ajuste para capturar códigos como FAU0109, ECO0019, etc.
    regex_disciplina = re.compile(r"([A-Z]{3}\d{3,4})\s+(.*?)(?:\s+-\s+|\s+)(\d+h(?:[\s\w\/]+)?)\b")


    try:
        with pdfplumber.open(pdf_path) as pdf:
            texto_primeira_pagina = pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=2) or ""
            dados_fluxo["curso_info"] = extrair_info_curso(texto_primeira_pagina)

            for i, page in enumerate(pdf.pages):
                texto_pagina = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                texto_completo += texto_pagina + "\n" # Acumula texto para debug se necessário

                linhas = texto_pagina.split('\n')
                for linha in linhas:
                    linha_limpa = limpar_texto(linha)

                    match_optativas = regex_optativas.search(linha_limpa)
                    if match_optativas:
                        processando_optativas = True
                        processando_nivel = False
                        nivel_atual = None
                        continue # Pula para próxima linha

                    match_nivel = regex_nivel.search(linha_limpa)
                    if match_nivel:
                        nivel_atual = match_nivel.group(1)
                        processando_nivel = True
                        processando_optativas = False
                        continue # Pula para próxima linha

                    # Se não for cabeçalho de seção, tenta extrair disciplina
                    if processando_nivel or processando_optativas:
                        match_disciplina = regex_disciplina.match(linha_limpa)
                        if match_disciplina:
                            codigo = limpar_texto(match_disciplina.group(1))
                            # Nome pode ter sido cortado pela CH, pega até o início da CH
                            nome_provavel = limpar_texto(match_disciplina.group(2))
                            ch_detalhada_texto = limpar_texto(match_disciplina.group(3))

                            # Remove a CH do nome se ela foi capturada junto
                            if nome_provavel.endswith(ch_detalhada_texto.split()[0]):
                                nome_provavel = limpar_texto(nome_provavel[:-len(ch_detalhada_texto.split()[0])].strip())
                                # Caso especial: Remove '-' se ficou sobrando
                                if nome_provavel.endswith('-'):
                                      nome_provavel = nome_provavel[:-1].strip()


                            carga_horaria = extrair_carga_horaria(ch_detalhada_texto)

                            disciplina_info = {
                                "codigo": codigo,
                                "nome": nome_provavel if nome_provavel else "Nome não extraído",
                                "carga_horaria_detalhada": ch_detalhada_texto,
                                "carga_horaria": carga_horaria,
                                # Tipo e Natureza são inferidos pela seção
                                "tipo": "DISCIPLINA", # Assumindo que todos são disciplinas
                            }

                            if processando_optativas:
                                disciplina_info["natureza"] = "OPTATIVO"
                                dados_fluxo["optativas"].append(disciplina_info)
                            elif processando_nivel and nivel_atual:
                                # Verifica se a linha original contém "OBRIGATORIO" para confirmar
                                if "OBRIGATORIO" in linha:
                                    disciplina_info["natureza"] = "OBRIGATORIO"
                                    dados_fluxo["niveis"][nivel_atual].append(disciplina_info)
                                # Se não contém OBRIGATORIO, pode ser uma optativa listada sob um nível (comum em alguns fluxos)
                                elif "OPTATIVO" in linha or not any(n in linha for n in ["OBRIGATORIO", "Tipo", "Natureza"]):
                                     # Se a linha não tem natureza explícita ou tem OPTATIVO
                                     # mas está sob um Nível, adiciona como optativa
                                     disciplina_info["natureza"] = "OPTATIVO"
                                     # Adiciona uma nota sobre o nível sugerido
                                     disciplina_info["nivel_sugerido_origem"] = nivel_atual
                                     dados_fluxo["optativas"].append(disciplina_info)


    except Exception as e:
        print(f"Erro ao processar {pdf_path}: {e}", file=sys.stderr)
        # print(f"Texto problemático:\n{texto_completo[-500:]}") # Descomentar para debug
        return None

    # Converte defaultdict para dict normal para serialização JSON
    dados_fluxo["niveis"] = dict(dados_fluxo["niveis"])
    return dados_fluxo

if __name__ == "__main__":
    dir_base = os.path.dirname(os.path.abspath(__file__))
    dir_entrada = os.path.join(dir_base, "dados", "fluxogramas_emitidos")
    dir_saida = os.path.join(dir_base, "dados", "dados_estruturados_fluxos")

    print(f"Diretório de entrada: {dir_entrada}")
    print(f"Diretório de saída: {dir_saida}")

    if not os.path.isdir(dir_entrada):
        print(f"Erro: Diretório de entrada não encontrado: {dir_entrada}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(dir_saida, exist_ok=True)

    arquivos_processados = 0
    arquivos_falha = 0
    for nome_arquivo in os.listdir(dir_entrada):
        if nome_arquivo.lower().endswith(".pdf"):
            caminho_pdf_completo = os.path.join(dir_entrada, nome_arquivo)
            print(f"\nProcessando arquivo: {nome_arquivo}...")

            dados_estruturados = processar_fluxograma_pdf(caminho_pdf_completo)

            if dados_estruturados:
                nome_base = os.path.splitext(nome_arquivo)[0]
                nome_arquivo_json = f"{nome_base}.json"
                caminho_json_completo = os.path.join(dir_saida, nome_arquivo_json)

                try:
                    with open(caminho_json_completo, 'w', encoding='utf-8') as f_json:
                        json.dump(dados_estruturados, f_json, ensure_ascii=False, indent=4)
                    print(f"Arquivo JSON salvo com sucesso em: {caminho_json_completo}")
                    arquivos_processados += 1
                except Exception as e:
                    print(f"Erro ao salvar JSON para {nome_arquivo}: {e}", file=sys.stderr)
                    arquivos_falha += 1
            else:
                print(f"Falha ao processar o PDF: {nome_arquivo}")
                arquivos_falha += 1

    print(f"\n--- Processamento Concluído ---")
    print(f"Total de arquivos PDF encontrados: {arquivos_processados + arquivos_falha}")
    print(f"Arquivos processados com sucesso: {arquivos_processados}")
    print(f"Arquivos com falha no processamento: {arquivos_falha}")
    print(f"Diretório de saída: {dir_saida}")