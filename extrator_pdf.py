import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os

def extrair_texto_de_pdf(caminho_pdf, caminho_tesseract):
    """
    Extrai o texto de um arquivo PDF usando OCR com Tesseract.

    Args:
        caminho_pdf (str): O caminho para o arquivo PDF.
        caminho_tesseract (str): O caminho para o executável do Tesseract OCR.

    Returns:
        str: O texto extraído de todas as páginas do PDF.
    """
    # Define o caminho para o executável do Tesseract
    pytesseract.pytesseract.tesseract_cmd = caminho_tesseract

    texto_completo = ""
    try:
        # Abre o arquivo PDF
        documento = fitz.open(caminho_pdf)

        # Itera sobre cada página do PDF
        for num_pagina in range(len(documento)):
            pagina = documento.load_page(num_pagina)

            # Renderiza a página como uma imagem
            pix = pagina.get_pixmap()
            img_bytes = pix.tobytes("png")
            imagem = Image.open(io.BytesIO(img_bytes))

            # Utiliza o Tesseract para extrair o texto da imagem
            # O 'lang' pode ser ajustado para o idioma do documento, 'por' para português
            texto_pagina = pytesseract.image_to_string(imagem, lang='por')
            
            texto_completo += f"--- PÁGINA {num_pagina + 1} ---\n{texto_pagina}\n\n"

        documento.close()
        return texto_completo

    except FileNotFoundError:
        return "Erro: O arquivo PDF não foi encontrado."
    except Exception as e:
        return f"Ocorreu um erro: {e}"

if __name__ == "__main__":
    # IMPORTANTE: Altere este caminho para o local onde o Tesseract foi instalado
    caminho_tesseract_ocr = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # Coloque o nome do seu arquivo PDF aqui
    nome_arquivo_pdf = "historico_190104821.pdf"

    # Extrai o texto
    texto_extraido = extrair_texto_de_pdf(nome_arquivo_pdf, caminho_tesseract_ocr)

    # Imprime o texto extraído
    print(texto_extraido)

    # Opcional: Salva o texto extraído em um arquivo .txt
    nome_arquivo_saida = "texto_extraido_historico.txt"
    with open(nome_arquivo_saida, "w", encoding="utf-8") as f:
        f.write(texto_extraido)

    print(f"\nTexto também salvo em '{nome_arquivo_saida}'")