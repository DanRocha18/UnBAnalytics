# Projeto para recomendação de disciplinas baseadas no histórico e fluxograma de curso

## Projeto desenvolvido que visa orientar o estudande na seleção de disciplinas para o semestre seguinte

### Tecnologias utilizadas:
- Scripts em Python
- Biblioteca Pandas
- Biblioteca Scikit-learn
- Biblioteca Numpy
- Biblioteca Matplotlib
- Biblioteca Seaborn
- Extrações de dados feitos utilizando LLM Gemini PRO

### Objetivo:

Uma estudo feito com 30 alunos e 23 cursos diferentes da Universidade de Brasília, com principal objetivo de verificar a eficácia de extrações e estruturações de dados não estruturados, como históricos acadêmicos e fluxogramas de cursos em PDF, utilizando LLM e scripts de extração/estruturação de dados, analisando as métricas de precisão, recall e F1-Score, para cada uma das extrações/estruturações dos dois métodos utilizados.

Além disso, o projeto visa recomendar disciplinas para os alunos com base em seus históricos acadêmicos e nos fluxogramas dos cursos, utilizando técnicas de análise de dados, verificando se os dados extraídos tanto por LLM quanto por scripts são capazes de serem analisados pelo script e pelo LLM para terem uma recomendação favorável de disciplinas para o semestre seguinte.

### Como utilizar:

1. Certifique-se de ter o Python instalado em sua máquina.
2. Instale as bibliotecas necessárias utilizando o pip:
   ```
   pip install pandas scikit-learn numpy matplotlib seaborn
   ```
3. Clone este repositório para sua máquina local.
4. Prepare os arquivos PDF do histórico acadêmico e do fluxograma do curso.
5. Na pasta historicos_emitidos, insira os arquivos pdf dos históricos acadêmicos a serem extraídos.
6. Na pasta fluxogramas_cursos, insira os arquivos pdf dos fluxogramas dos cursos a serem extraídos.
7. Execute os scripts de extração para gerar os arquivos JSON:
    ```
    python processador_historico.py
    python processador_fluxograma.py
    ```
8. Execute para analise de precisão das extrações:
    ```
    python analise_precisao.py
    ```
9. Por fim, se quiser, execute o script de recomendação de disciplinas:
    ```
    python recomendar.py caminho_para_historico.json caminho_para_fluxograma.json
    ```

### Autor:
**Daniel Rocha Oliveira** - Estudante de Engenharia de Software na Universidade de Brasília (UnB).

- GitHub: [DanRocha18](https://github.com/DanRocha18)