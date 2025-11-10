import json
import os
import glob
from typing import Dict, Any, List, Set, Tuple, Callable

def calcular_metricas(lista_gabarito: List[Dict], lista_predito: List[Dict]) -> Dict[str, Any]:
    """
    Calcula as métricas de Precisão, Recall e F1-Score comparando duas listas
    de dicionários (itens extraídos).
    
    A comparação é estrita: um item só é considerado "igual" se for
    idêntico ao do gabarito.
    """
    
    # Serializa os objetos JSON para strings canônicas para permitir
    # a comparação em conjuntos (sets). Isso garante que a ordem das
    # chaves não afete o resultado.
    try:
        # Nota: Usamos 'frozenset' para serializar listas internas (como 'requisitos')
        # de forma que a ordem dos requisitos não importe.
        set_gabarito = {json.dumps(item, sort_keys=True) for item in lista_gabarito}
        set_predito = {json.dumps(item, sort_keys=True) for item in lista_predito}
    except TypeError as e:
        print(f"  [Erro] Falha ao serializar item. Possível tipo de dado não-serializável: {e}")
        return {'tp': 0, 'fp': 0, 'fn': 0, 'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0, 'error': str(e)}

    # 1. Verdadeiro Positivo (TP): Itens idênticos em ambos os conjuntos.
    tp = len(set_gabarito.intersection(set_predito))
    
    # 2. Falso Positivo (FP): Itens no predito que não estão no gabarito.
    #    (Itens "inventados" ou extraídos com erro).
    fp = len(set_predito - set_gabarito)
    
    # 3. Falso Negativo (FN): Itens no gabarito que não estão no predito.
    #    (Itens "perdidos" ou extraídos com erro).
    fn = len(set_gabarito - set_predito)

    # Calcular Métricas
    
    # Precisão = TP / (TP + FP)
    if (tp + fp) == 0:
        # Se não previu nada (TP+FP=0), a precisão é perfeita (1.0)
        # (pois não houve falsos positivos).
        precision = 1.0
    else:
        precision = tp / (tp + fp)

    # Recall = TP / (TP + FN)
    if (tp + fn) == 0:
        # Se não havia nada no gabarito (TP+FN=0), o recall é perfeito (1.0)
        # (pois não houve falsos negativos).
        recall = 1.0
    else:
        recall = tp / (tp + fn)

    # F1-Score = 2 * (Precisão * Recall) / (Precisão + Recall)
    if (precision + recall) == 0:
        f1_score = 0.0
    else:
        f1_score = 2 * (precision * recall) / (precision + recall)
        
    # Tratamento especial para o caso [0, 0, 0] que leva a P=1, R=1, F1=1
    # Se todos são 0, o F1-Score deve ser 1.0 (comparação perfeita de vazio vs vazio)
    # A lógica acima já trata isso corretamente.

    return {
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score
    }

def carregar_json(filepath: str) -> Dict[str, Any]:
    """Carrega um arquivo JSON com tratamento de erro."""
    if not os.path.exists(filepath):
        print(f"  [Aviso] Arquivo não encontrado: {filepath}")
        return {} # Retorna dicionário vazio se o arquivo não existe

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                print(f"  [Aviso] Arquivo JSON está vazio: {filepath}")
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"  [Erro] Falha ao decodificar JSON (mal formatado): {filepath}")
    except Exception as e:
        print(f"  [Erro] Erro inesperado ao ler {filepath}: {e}")
    return {}

# --- FUNÇÕES DE EXTRAÇÃO CUSTOMIZADAS ---

def extrair_lista_historico(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrai a lista de disciplinas de um arquivo de histórico.
    Chave esperada: "componentes_cursados"
    """
    if not isinstance(data, dict):
        return []
    lista = data.get("componentes_cursados", [])
    if not isinstance(lista, list):
        print("  [Aviso] Chave 'componentes_cursados' não é uma lista.")
        return []
    return lista

def extrair_lista_fluxo(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrai e "achata" (flattens) as listas de disciplinas de um
    arquivo de fluxograma, combinando "niveis" e "disciplinas_optativas".
    """
    lista_total = []
    if not isinstance(data, dict):
        return []

    # 1. Extrair de "niveis"
    niveis = data.get("niveis", {})
    if isinstance(niveis, dict):
        for nivel, lista_disciplinas in niveis.items():
            if isinstance(lista_disciplinas, list):
                lista_total.extend(lista_disciplinas)
            else:
                print(f"  [Aviso] Valor do nível '{nivel}' não é uma lista.")
    else:
        print("  [Aviso] Chave 'niveis' não é um dicionário.")

    # 2. Extrair de "disciplinas_optativas"
    optativas = data.get("disciplinas_optativas", [])
    if isinstance(optativas, list):
        lista_total.extend(optativas)
    else:
        print("  [Aviso] Chave 'disciplinas_optativas' não é uma lista.")
        
    return lista_total

# --- FIM DAS FUNÇÕES DE EXTRAÇÃO ---


def analisar_conjunto(
    nome_conjunto: str,
    dir_gabarito: str,
    dir_python: str,
    dir_llm: str,
    sufixo_gabarito: str,
    sufixo_python: str,
    sufixo_llm: str,
    extractor_func: Callable[[Dict], List] # Função de extração
) -> Dict[str, Dict[str, float]]:
    """
    Analisa um conjunto completo de dados (ex: 'fluxos' ou 'historicos'),
    comparando os extratores Python e LLM com o gabarito.
    """
    print(f"\n--- Iniciando Análise do Conjunto: {nome_conjunto} ---")
    
    resultados_python = []
    resultados_llm = []

    # Encontra todos os arquivos de gabarito
    arquivos_gabarito = glob.glob(os.path.join(dir_gabarito, f"*{sufixo_gabarito}"))
    
    if not arquivos_gabarito:
        print(f"[ERRO] Nenhum arquivo de gabarito encontrado em: {dir_gabarito}")
        return {}

    for gab_path in arquivos_gabarito:
        basename = os.path.basename(gab_path)
        base_id = basename.replace(sufixo_gabarito, '')
        
        print(f"Processando: {base_id}")

        # Construir caminhos para os arquivos preditos
        py_path = os.path.join(dir_python, base_id + sufixo_python)
        llm_path = os.path.join(dir_llm, base_id + sufixo_llm)

        # Carregar dados
        dados_gabarito = carregar_json(gab_path)
        dados_python = carregar_json(py_path)
        dados_llm = carregar_json(llm_path)

        # Extrair as listas para comparação usando a função customizada
        lista_gabarito = extractor_func(dados_gabarito)
        
        if not lista_gabarito and dados_gabarito: # Se o dict não estava vazio
            print(f"  [Aviso] Gabarito {base_id} não produziu dados (verificar chaves).")

        # --- Comparar Python vs Gabarito ---
        lista_python = extractor_func(dados_python)
        metricas_py = calcular_metricas(lista_gabarito, lista_python)
        resultados_python.append(metricas_py)
        print(f"  Python: F1={metricas_py['f1_score']:.4f} (P={metricas_py['precision']:.4f}, R={metricas_py['recall']:.4f}) | TP:{metricas_py['tp']}, FP:{metricas_py['fp']}, FN:{metricas_py['fn']}")

        # --- Comparar LLM vs Gabarito ---
        lista_llm = extractor_func(dados_llm)
        metricas_llm = calcular_metricas(lista_gabarito, lista_llm)
        resultados_llm.append(metricas_llm)
        print(f"  LLM:    F1={metricas_llm['f1_score']:.4f} (P={metricas_llm['precision']:.4f}, R={metricas_llm['recall']:.4f}) | TP:{metricas_llm['tp']}, FP:{metricas_llm['fp']}, FN:{metricas_llm['fn']}")


    # Calcular médias
    
    def calcular_media(resultados: List[Dict]) -> Dict[str, float]:
        if not resultados:
            return {'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0, 'count': 0}
        
        validos = [r for r in resultados if 'error' not in r]
        num_erros = len(resultados) - len(validos)
        
        if not validos:
             return {'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0, 'count': 0, 'erros_serializacao': num_erros}

        media_precision = sum(r['precision'] for r in validos) / len(validos)
        media_recall = sum(r['recall'] for r in validos) / len(validos)
        media_f1 = sum(r['f1_score'] for r in validos) / len(validos)
        return {
            'precision': media_precision,
            'recall': media_recall,
            'f1_score': media_f1,
            'count': len(validos),
            'erros_serializacao': num_erros
        }

    media_python = calcular_media(resultados_python)
    media_llm = calcular_media(resultados_llm)

    return {"Python": media_python, "LLM": media_llm}


def main():
    # Define os caminhos base
    base_dir = "UnBAnalytics/dados"
    
    if not os.path.isdir(base_dir):
         base_dir = "dados"
         if not os.path.isdir(base_dir):
             print(f"Erro: Diretório de dados 'UnBAnalytics/dados' ou 'dados' não encontrado.")
             print(f"Por favor, execute este script no diretório raiz do projeto.")
             return

    # --- Configurações para Fluxogramas ---
    dir_gabarito_fluxos = os.path.join(base_dir, "gabaritos/fluxos")
    dir_python_fluxos = os.path.join(base_dir, "dados_estruturados_fluxos")
    dir_llm_fluxos = os.path.join(base_dir, "Dados_estruturados_LLM/fluxos")
    
    resultados_fluxos = analisar_conjunto(
        nome_conjunto="Fluxogramas",
        dir_gabarito=dir_gabarito_fluxos,
        dir_python=dir_python_fluxos,
        dir_llm=dir_llm_fluxos,
        sufixo_gabarito="_gab.json",
        sufixo_python=".json",
        sufixo_llm="_extraido.json",
        extractor_func=extrair_lista_fluxo # <--- USANDO A FUNÇÃO CORRETA
    )

    # --- Configurações para Históricos ---
    dir_gabarito_historicos = os.path.join(base_dir, "gabaritos/historicos")
    dir_python_historicos = os.path.join(base_dir, "dados_estruturados_historico")
    dir_llm_historicos = os.path.join(base_dir, "Dados_estruturados_LLM/historicos")

    resultados_historicos = analisar_conjunto(
        nome_conjunto="Históricos Acadêmicos",
        dir_gabarito=dir_gabarito_historicos,
        dir_python=dir_python_historicos,
        dir_llm=dir_llm_historicos,
        sufixo_gabarito="_gab.json",
        sufixo_python=".json",
        sufixo_llm=".json",
        extractor_func=extrair_lista_historico # <--- USANDO A FUNÇÃO CORRETA
    )
    
    # --- Imprimir Relatório Final ---
    print("\n" + "="*50)
    print("      RELATÓRIO FINAL DE PRECISÃO DE EXTRAÇÃO (v3)")
    print("="*50)

    def imprimir_relatorio(nome: str, resultados: Dict):
        if not resultados:
            print(f"\nResultados para {nome} não puderam ser calculados.")
            return
            
        py_stats = resultados.get("Python", {}) 
        llm_stats = resultados.get("LLM", {})
        
        count = py_stats.get('count', 0)
        if count == 0:
            print(f"\n--- {nome} ---")
            print("  Nenhum arquivo de gabarito foi encontrado ou processado.")
            return

        print(f"\n--- {nome} (Baseado em {count} arquivos) ---")
        
        print("\nExtrator PYTHON:")
        print(f"  F1-Score Médio: {py_stats.get('f1_score', 0.0):.4f}")
        print(f"  Precisão Média: {py_stats.get('precision', 0.0):.4f}")
        print(f"  Recall Médio:   {py_stats.get('recall', 0.0):.4f}")
        if py_stats.get('erros_serializacao', 0) > 0:
             print(f"  AVISO: {py_stats['erros_serializacao']} arquivos falharam na serialização.")


        print("\nExtrator LLM (Gemini):")
        print(f"  F1-Score Médio: {llm_stats.get('f1_score', 0.0):.4f}")
        print(f"  Precisão Média: {llm_stats.get('precision', 0.0):.4f}")
        print(f"  Recall Médio:   {llm_stats.get('recall', 0.0):.4f}")
        if llm_stats.get('erros_serializacao', 0) > 0:
             print(f"  AVISO: {llm_stats['erros_serializacao']} arquivos falharam na serialização.")
        print("-"*(len(nome) + 6))

    imprimir_relatorio("Análise de FLUXOGRAMAS", resultados_fluxos)
    imprimir_relatorio("Análise de HISTÓRICOS", resultados_historicos)
    print("\n" + "="*50)

if __name__ == "__main__":
    main()