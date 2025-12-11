import json
import os
import glob
from typing import Dict, Any, List, Set, Callable

class Cores:
    VERDE = '\033[92m'
    VERMELHO = '\033[91m'
    AMARELO = '\033[93m'
    RESET = '\033[0m'
    NEGRITO = '\033[1m'

def normalizar_item(item: Dict) -> str:
    """Serializa o item JSON de forma determinística para comparação."""
    return json.dumps(item, sort_keys=True, ensure_ascii=False)

def calcular_metricas_detalhadas(lista_gabarito: List[Dict], lista_predito: List[Dict], nome_arquivo: str = "") -> Dict[str, Any]:
    """
    Calcula P/R/F1 e identifica os itens exatos de erro.
    """
    try:
        set_gabarito = {normalizar_item(item) for item in lista_gabarito}
        set_predito = {normalizar_item(item) for item in lista_predito}
    except TypeError as e:
        return {'erro': str(e)}

    # Conjuntos de interseção e diferenças
    intersection = set_gabarito.intersection(set_predito)
    only_in_gabarito = set_gabarito - set_predito  # Falsos Negativos (FN)
    only_in_predito = set_predito - set_gabarito   # Falsos Positivos (FP)

    tp = len(intersection)
    fp = len(only_in_predito)
    fn = len(only_in_gabarito)

    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if not set_predito else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if not set_gabarito else 0.0)
    
    if (precision + recall) == 0:
        f1_score = 0.0
    else:
        f1_score = 2 * (precision * recall) / (precision + recall)

    return {
        'tp': tp, 'fp': fp, 'fn': fn,
        'precision': precision, 'recall': recall, 'f1_score': f1_score,
        'diff_fn': list(only_in_gabarito), # O que o modelo perdeu
        'diff_fp': list(only_in_predito)   # O que o modelo alucinou
    }

def imprimir_diff(metricas: Dict, nome_modelo: str):
    """Imprime as diferenças encontradas de forma legível."""
    # Se for perfeito ou tiver erro de execução, não imprime diff
    if metricas.get('f1_score') == 1.0 or 'erro' in metricas:
        return

    print(f"    {Cores.AMARELO}>> Diferenças no {nome_modelo}:{Cores.RESET}")
    
    if metricas['fp'] > 0:
        print(f"    {Cores.VERMELHO}[+] Alucinações (FP): {metricas['fp']} itens{Cores.RESET}")
        for item in metricas['diff_fp'][:3]:
            print(f"       -> {item}")
        if metricas['fp'] > 3: print("       ... (mais itens)")

    if metricas['fn'] > 0:
        print(f"    {Cores.AMARELO}[-] Perdas (FN): {metricas['fn']} itens{Cores.RESET}")
        for item in metricas['diff_fn'][:3]:
            print(f"       -> {item}")
        if metricas['fn'] > 3: print("       ... (mais itens)")

def carregar_json(filepath: str) -> Dict[str, Any]:
    if not os.path.exists(filepath): return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.loads(f.read())
    except: return {}

def extrair_historico(data: Dict) -> List[Dict]:
    return data.get("componentes_cursados", [])

def extrair_fluxo(data: Dict) -> List[Dict]:
    lista = []
    # Niveis
    niveis = data.get("niveis", {})
    if isinstance(niveis, dict):
        for _, disc in niveis.items():
            if isinstance(disc, list): lista.extend(disc)
    # Optativas
    opt = data.get("disciplinas_optativas", [])
    if isinstance(opt, list): lista.extend(opt)
    return lista

def analisar_comparativo(
    dir_base: str, 
    tipo: str, 
    dir_gab: str, 
    dir_py: str, 
    dir_llm: str,
    extractor: Callable
):
    print(f"\n{Cores.NEGRITO}{'='*80}")
    print(f" ANÁLISE COMPARATIVA: {tipo.upper()}")
    print(f"{'='*80}{Cores.RESET}")

    arquivos = glob.glob(os.path.join(dir_base, dir_gab, "*_gab.json"))
    
    acumulado_py = {'p': [], 'r': [], 'f1': []}
    acumulado_llm = {'p': [], 'r': [], 'f1': []}

    for path_gab in arquivos:
        filename = os.path.basename(path_gab)
        base_id = filename.replace('_gab.json', '')
        
        path_py = os.path.join(dir_base, dir_py, f"{base_id}.json")
        # Ajuste: Fluxos tem sufixo _extraido.json na pasta LLM
        sufixo_llm = "_extraido.json" if "fluxo" in tipo.lower() else ".json"
        path_llm = os.path.join(dir_base, dir_llm, f"{base_id}{sufixo_llm}")

        dados_gab = extractor(carregar_json(path_gab))
        dados_py = extractor(carregar_json(path_py))
        dados_llm = extractor(carregar_json(path_llm))

        if not dados_gab: 
            print(f"[AVISO] Gabarito vazio ou inválido: {base_id}")
            continue

        # Calcular
        m_py = calcular_metricas_detalhadas(dados_gab, dados_py)
        m_llm = calcular_metricas_detalhadas(dados_gab, dados_llm)

        # Acumular Médias (apenas se não houve erro crítico)
        if 'erro' not in m_py:
            acumulado_py['p'].append(m_py['precision'])
            acumulado_py['r'].append(m_py['recall'])
            acumulado_py['f1'].append(m_py['f1_score'])
        
        if 'erro' not in m_llm:
            acumulado_llm['p'].append(m_llm['precision'])
            acumulado_llm['r'].append(m_llm['recall'])
            acumulado_llm['f1'].append(m_llm['f1_score'])

        # --- IMPRESSÃO DOS RESULTADOS POR ARQUIVO ---
        print(f"\nArquivo: {Cores.NEGRITO}{base_id}{Cores.RESET}")
        
        # Python
        if 'erro' in m_py:
            print(f"  PYTHON | Erro: {m_py['erro']}")
        else:
            print(f"  PYTHON | TP:{m_py['tp']:02d} FP:{m_py['fp']:02d} FN:{m_py['fn']:02d} | "
                  f"F1: {m_py['f1_score']:.3f} P: {m_py['precision']:.3f} R: {m_py['recall']:.3f}")
            imprimir_diff(m_py, "PYTHON")

        # LLM
        if 'erro' in m_llm:
             print(f"  LLM    | Erro: {m_llm['erro']}")
        else:
            print(f"  LLM    | TP:{m_llm['tp']:02d} FP:{m_llm['fp']:02d} FN:{m_llm['fn']:02d} | "
                  f"F1: {m_llm['f1_score']:.3f} P: {m_llm['precision']:.3f} R: {m_llm['recall']:.3f}")
            imprimir_diff(m_llm, "LLM")

    # Médias Finais
    def media(lista): return sum(lista)/len(lista) if lista else 0

    print(f"\n{Cores.NEGRITO}--- MÉDIAS GERAIS ({tipo}) ---{Cores.RESET}")
    print(f"PYTHON >> F1: {media(acumulado_py['f1']):.4f} | Precision: {media(acumulado_py['p']):.4f} | Recall: {media(acumulado_py['r']):.4f}")
    print(f"LLM    >> F1: {media(acumulado_llm['f1']):.4f} | Precision: {media(acumulado_llm['p']):.4f} | Recall: {media(acumulado_llm['r']):.4f}")

def main():
    base = "UnBAnalytics/dados"
    if not os.path.exists(base): base = "dados"

    # Históricos
    analisar_comparativo(
        base, "Históricos", 
        "gabaritos/historicos", 
        "dados_estruturados_historico", 
        "Dados_estruturados_LLM/historicos",
        extrair_historico
    )

    # Fluxos
    analisar_comparativo(
        base, "Fluxogramas", 
        "gabaritos/fluxos", 
        "dados_estruturados_fluxos", 
        "Dados_estruturados_LLM/fluxos",
        extrair_fluxo
    )

if __name__ == "__main__":
    main()