# -*- coding: utf-8 -*-
"""
Script para gerar recomendações de disciplinas com base no histórico
acadêmico (JSON v16) e no fluxograma (JSON v1) de um aluno.

Versão 2.0 (Refinamento de Maestria):
- Remove completamente a lógica de pré-requisitos, que não existe
  nos JSONs de fluxograma atuais.
- A recomendação agora é baseada nas `componentes_pendentes` do histórico
  e priorizada pelo `nivel_sugerido` (semestre) do fluxograma.
- Corrige a leitura do JSON do histórico (v16), lendo `componente['codigo']`
  em vez de `componente['nome']`.
- Adiciona uma estratégia de recomendação secundária: sugere optativas
  do fluxograma que o aluno ainda não cursou.
"""

import json
import sys
from collections import defaultdict

# Situações que contam como "aprovado"
STATUS_APROVADO = {"MM", "MS", "SS", "APR", "DISP"}
# Situações que contam como "atualmente matriculado"
STATUS_MATRICULADO = {"MATR", "-"}

def carregar_dados(caminho_arquivo):
    """Carrega um arquivo JSON e retorna seu conteúdo."""
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Erro: Arquivo não encontrado: {caminho_arquivo}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Erro: O arquivo {caminho_arquivo} não é um JSON válido.", file=sys.stderr)
        sys.exit(1)

def criar_mapa_fluxo(fluxo_data):
    """
    Cria um dicionário (mapa) de todas as disciplinas do fluxograma,
    armazenando seu nível (semestre) e natureza.
    """
    mapa_fluxo = {}
    
    # Processar Níveis (Obrigatórias)
    # fluxo_data['niveis'] é um dict como: {"1": [...], "2": [...]}
    for nivel_str, disciplinas in fluxo_data.get('niveis', {}).items():
        try:
            nivel_int = int(nivel_str)
        except ValueError:
            nivel_int = 99 # Fallback para níveis não numéricos

        for disciplina in disciplinas:
            codigo = disciplina['codigo']
            disciplina['nivel_sugerido'] = nivel_int
            disciplina['natureza'] = 'OBRIGATORIO'
            mapa_fluxo[codigo] = disciplina
            
    # Processar Optativas (Geral)
    # fluxo_data['optativas'] é uma list como: [...]
    for disciplina in fluxo_data.get('optativas', []):
        codigo = disciplina['codigo']
        # Não sobrescreve se a optativa já estava listada em um nível
        if codigo not in mapa_fluxo:
            # Tenta pegar o nível de origem, senão usa 99 (geral)
            nivel_sugerido = disciplina.get('nivel_sugerido_origem', 99)
            disciplina['nivel_sugerido'] = int(nivel_sugerido) if nivel_sugerido else 99
            disciplina['natureza'] = 'OPTATIVO'
            mapa_fluxo[codigo] = disciplina
            
    return mapa_fluxo

def processar_historico(historico_data):
    """
    Processa o JSON do histórico (v16) e retorna dois conjuntos:
    códigos de disciplinas aprovadas e matriculadas.
    """
    aprovadas = set()
    matriculadas = set()
    
    # USA A ESTRUTURA CORRETA DO JSON v16
    for componente in historico_data.get('componentes_cursados', []):
        codigo_disciplina = componente.get('codigo') # CORRIGIDO
        situacao = componente.get('situacao', '')
        
        if not codigo_disciplina:
            continue
            
        if situacao in STATUS_APROVADO:
            aprovadas.add(codigo_disciplina)
        elif situacao in STATUS_MATRICULADO:
            matriculadas.add(codigo_disciplina)
            
    return aprovadas, matriculadas

def gerar_recomendacoes(historico_data, mapa_fluxo, aprovadas, matriculadas):
    """
    Compara as disciplinas pendentes (do histórico) com o mapa do fluxo
    e gera as recomendações, priorizadas por nível.
    """
    recomendadas_pendentes = []
    pendentes_desconhecidas = []
    optativas_sugeridas = []

    disciplinas_pendentes = historico_data.get('componentes_pendentes', [])

    # 1. Processar a lista de PENDENTES do histórico
    for item in disciplinas_pendentes:
        codigo_pendente = item.get('codigo')

        if not codigo_pendente or codigo_pendente == 'ENADE':
            continue
            
        # Ignora se o aluno já está matriculado na pendência
        if codigo_pendente in matriculadas:
            continue
        # Ignora se, por algum motivo, uma pendência já foi aprovada
        if codigo_pendente in aprovadas:
            continue
            
        if codigo_pendente in mapa_fluxo:
            # Se a pendência está no fluxograma, obtemos seu nível
            disciplina_fluxo = mapa_fluxo[codigo_pendente]
            recomendadas_pendentes.append({
                "codigo": codigo_pendente,
                "nome": disciplina_fluxo.get('nome', item.get('nome')), # Prefere nome do fluxo
                "ch": disciplina_fluxo.get('carga_horaria', {}).get('total_h', item.get('ch')),
                "nivel_sugerido": disciplina_fluxo.get('nivel_sugerido', 99)
            })
        else:
            # Se a pendência não está no fluxograma (ex: optativa de outro depto)
            pendentes_desconhecidas.append({
                "codigo": codigo_pendente,
                "nome": item.get('nome'),
                "ch": item.get('ch'),
                "motivo": "Código não encontrado no JSON do fluxograma fornecido."
            })
            
    # 2. Priorizar (como solicitado)
    recomendadas_pendentes.sort(key=lambda d: d.get('nivel_sugerido', 99))
    
    # 3. Estratégia Adicional: Sugerir optativas do fluxo (que não estão pendentes)
    for codigo, disciplina in mapa_fluxo.items():
        if disciplina['natureza'] == 'OPTATIVO':
            if codigo not in aprovadas and codigo not in matriculadas:
                optativas_sugeridas.append(disciplina)
    
    optativas_sugeridas.sort(key=lambda d: d.get('nivel_sugerido', 99))

    return recomendadas_pendentes, pendentes_desconhecidas, optativas_sugeridas

def imprimir_resultados(recomendadas, pendentes_desconhecidas, optativas_sugeridas, aluno_nome):
    """Imprime os resultados da análise no console."""
    
    print(f"\n--- Análise de Recomendações para {aluno_nome} ---")
    
    print("\n--- [AÇÃO PRIORITÁRIA] Disciplinas Pendentes (Obrigatórias/Optativas) ---")
    print("Disciplinas que você deixou para trás. A recomendação é focar nestas primeiro, por ordem de nível:\n")
    
    if recomendadas:
        for disciplina in recomendadas:
            nivel = disciplina.get('nivel_sugerido', '?')
            ch = disciplina.get('ch', 'N/A')
            print(f"  [Nível {nivel}] {disciplina['codigo']} - {disciplina['nome']} ({ch}h)")
    else:
         print("  Parabéns! Nenhuma disciplina obrigatória ou optativa do fluxo consta como pendente.")
         print("  (Verifique os avisos abaixo caso existam pendências não reconhecidas).")

    print("\n--- [SUGESTÕES] Disciplinas Optativas do Fluxograma ---")
    print("Disciplinas optativas do seu curso que você ainda não cursou (ou não está cursando):\n")
    
    if optativas_sugeridas:
         # Mostrar apenas as 10 primeiras para não poluir o terminal
        for disciplina in optativas_sugeridas[:10]:
            ch = disciplina.get('carga_horaria', {}).get('total_h', 'N/A')
            print(f"  {disciplina['codigo']} - {disciplina['nome']} ({ch}h)")
        if len(optativas_sugeridas) > 10:
            print(f"  ...e mais {len(optativas_sugeridas) - 10} optativas.")
    else:
        print("  Você já cursou (ou está cursando) todas as optativas listadas no fluxograma.")

    if pendentes_desconhecidas:
        print("\n--- [AVISO] Disciplinas Pendentes não encontradas no Fluxograma ---")
        print("Estas disciplinas constam como pendentes no seu histórico, mas não foram encontradas no JSON do fluxo.")
        print("Isso é comum para optativas de outros departamentos.\n")
        for item in pendentes_desconhecidas:
            print(f"  {item['codigo']} - {item['nome']} ({item['ch']}h)")
            print(f"  Motivo: {item['motivo']}\n")

    print("\n--- Próximos Passos ---")
    print(" * Lembre-se que este script é uma sugestão. A oferta de turmas pode variar.")
    print(" * Confirme sua matrícula e grade de horários no sistema oficial da universidade.")

def main():
    """Função principal para orquestrar a lógica de recomendação."""

    if len(sys.argv) < 3:
        print("Erro: Argumentos insuficientes.", file=sys.stderr)
        print("Uso: python recomendar.py <arquivo_historico.json> <arquivo_fluxo.json>", file=sys.stderr)
        sys.exit(1)

    arquivo_historico_path = sys.argv[1]
    arquivo_fluxo_path = sys.argv[2]

    print(f"Carregando histórico de: {arquivo_historico_path}")
    historico_data = carregar_dados(arquivo_historico_path)
    
    print(f"Carregando fluxograma de: {arquivo_fluxo_path}")
    fluxo_data = carregar_dados(arquivo_fluxo_path)

    # Extrai o nome do aluno para o relatório
    aluno_nome = historico_data.get('dados_pessoais', {}).get('nome', 'Aluno(a)')

    print("Construindo mapa do fluxograma...")
    mapa_fluxo = criar_mapa_fluxo(fluxo_data)

    print("Processando progresso do aluno...")
    aprovadas, matriculadas = processar_historico(historico_data)

    print("Gerando recomendações...")
    recomendadas, pendentes_desconhecidas, optativas_sugeridas = gerar_recomendacoes(
        historico_data, mapa_fluxo, aprovadas, matriculadas
    )

    imprimir_resultados(recomendadas, pendentes_desconhecidas, optativas_sugeridas, aluno_nome)

if __name__ == "__main__":
    main()
