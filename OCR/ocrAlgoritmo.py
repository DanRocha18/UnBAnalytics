import cv2
import pytesseract
import re
import json 
from pdf2image import convert_from_path
from PIL import Image

def preprocessar_imagem(imagem):
    """
    Converte uma imagem para escala de cinza e aplica um limiar para binarização.
    Esta é uma etapa crucial para melhorar a precisão do OCR.
    """
    # Converte para escala de cinza
    gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    
    # Aplica um limiar adaptativo para obter uma imagem em preto e branco mais nítida
    # Isso ajuda a lidar com diferentes condições de iluminação na imagem
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Melhora a imagem para o OCR removendo ruídos
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    
    return 255 - opening # Inverte as cores para ter texto preto em fundo branco


def extrair_do_historico(pdf_path):
    """
    Extrai e estrutura os dados de um PDF de histórico acadêmico.
    """
    print(f"Iniciando processamento do histórico: {pdf_path}")
    
   # Converter PDF para uma lista de imagens
    try:
        paginas_img = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        print(f"Erro ao converter PDF. Verifique se o Poppler está instalado e no PATH. Erro: {e}")
        return None

    texto_completo = ""
    for i, img_pil in enumerate(paginas_img):
        print(f"Processando página {i+1}/{len(paginas_img)}...")
        # Salva a imagem temporariamente para o OpenCV ler
        temp_img_path = f"temp_page_{i}.png"
        img_pil.save(temp_img_path)
        
        img_cv = cv2.imread(temp_img_path)
        img_processada = preprocessar_imagem(img_cv)
        
        # Executar OCR na imagem da página
        config_ocr = r'--oem 3 --psm 6 -l por' # Configuração para português
        texto_pagina = pytesseract.image_to_string(img_processada, config=config_ocr)
        texto_completo += texto_pagina + "\n"

    # Usar REGEX para extrair as informações do texto completo
    
    # Regex para encontrar disciplinas e suas situações
    regex_disciplinas = re.compile(r'([A-Z]{3,4}\d{4,5}).*?\b(APR|DISP|REP|REPF|TRANC|MATR)\b', re.DOTALL)
    
    matches = regex_disciplinas.findall(texto_completo)
    
    aprovadas = []
    reprovadas = []
    trancadas = []
    em_curso = []

    for codigo, situacao in matches:
        if situacao in ["APR", "DISP"]:
            aprovadas.append(codigo)
        elif situacao in ["REP", "REPF"]:
            reprovadas.append(codigo)
        elif situacao == "TRANC":
            trancadas.append(codigo)
        elif situacao == "MATR":
            em_curso.append(codigo)
            
    # Lógica para encontrar reprovações pendentes:
    # são as disciplinas reprovadas que não constam na lista de aprovadas.
    aprovadas_set = set(aprovadas)
    reprovadas_pendentes = [cod for cod in reprovadas if cod not in aprovadas_set]
    
    # Remove duplicatas mantendo a ordem
    aprovadas = sorted(list(set(aprovadas)))
    
    historico_estruturado = {
        "disciplinas_aprovadas": aprovadas,
        "disciplinas_reprovadas_pendentes": sorted(list(set(reprovadas_pendentes))),
        "disciplinas_trancadas": sorted(list(set(trancadas))),
        "disciplinas_em_curso": sorted(list(set(em_curso)))
    }
    
    print("Extração do histórico concluída.")
    return historico_estruturado


def extrair_do_fluxograma(image_path):
    """
    Tenta extrair e estruturar dados de uma imagem de fluxograma.
    Esta função é uma prova de conceito e tem limitações significativas.
    """
    print(f"Iniciando processamento do fluxograma: {image_path}")
    
    img = cv2.imread(image_path)
    if img is None:
        print("Erro: Não foi possível ler a imagem do fluxograma.")
        return None

    img_processada = preprocessar_imagem(img)

    config_ocr = r'--oem 3 --psm 4 -l por'
    texto_completo = pytesseract.image_to_string(img_processada, config=config_ocr)
    
    regex_disciplinas = re.compile(r'([A-Z]{3}-\d{5,6})\s*([\w\sÀ-ú]+?)(?=[A-Z]{3}-\d{5,6}|$)')
    
    matches = regex_disciplinas.findall(texto_completo)
    
    fluxograma_estruturado = {}

    print("AVISO: A extração de semestre e pré-requisitos de uma imagem é instável.")
    print("Os valores a seguir são placeholders.")
    
    for codigo, nome in matches:
        nome_limpo = re.sub(r'\s+', ' ', nome).strip()
        fluxograma_estruturado[codigo] = {
            "nome": nome_limpo,
            "semestre": 0, # Placeholders
            "tipo": "obrigatoria",
            "prerequisitos": [] 
        }
        
    print("Extração do fluxograma concluída.")
    return fluxograma_estruturado


if __name__ == '__main__':
    # Caminhos para os arquivos de entrada
    caminho_pdf_historico = 'historico_academico.pdf'
    caminho_img_fluxo = 'fluxograma.jpg'

    # Processa o histórico e salva em JSON
    dados_historico = extrair_do_historico(caminho_pdf_historico)
    if dados_historico:
        with open('historico_extraido.json', 'w', encoding='utf-8') as f:
            json.dump(dados_historico, f, indent=2, ensure_ascii=False)
        print("Salvo em 'historico_extraido.json'")

    # Processa o fluxograma e salva em JSON
    # NOTA: O resultado desta função será muito imperfeito.
    dados_fluxo = extrair_do_fluxograma(caminho_img_fluxo)
    if dados_fluxo:
        with open('fluxograma_extraido.json', 'w', encoding='utf-8') as f:
            json.dump(dados_fluxo, f, indent=2, ensure_ascii=False)
        print("Salvo em 'fluxograma_extraido.json'")