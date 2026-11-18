# Lab Linear — Experimentos de Álgebra Linear Numérica

Interface web local para configurar, executar e analisar experimentos de comparação entre eliminação de Gauss, decomposição LU e decomposição QR por Householder.

## Estrutura

- `matrizes.py`: gera matrizes com número de condição controlado e sistemas `Ax = b` com solução verdadeira conhecida.
- `metodos.py`: Gauss com pivoteamento parcial, LU com pivoteamento parcial e QR por Householder.
- `metricas.py`: erro absoluto, erro relativo, resíduo absoluto, resíduo relativo e erro retroativo.
- `experimentos.py`: executor dos testes, agregação por mediana e exportação dos CSVs. Também aceita uma função de callback para atualizar o progresso da interface.
- `app.py`: aplicação Flask e API para iniciar experimentos, consultar o progresso, visualizar resultados e baixar CSVs.
- `templates/index.html`: estrutura da interface.
- `static/style.css`: estilos responsivos.
- `static/app.js`: validação do formulário, atualização do progresso, tabela e gráfico.

## Requisitos

Python 3.10 ou superior.

## Instalação no Ubuntu/Linux

Na pasta do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Executar a interface

```bash
python app.py
```

Abra no navegador:

```text
http://127.0.0.1:5000
```

A aplicação fica vinculada a `127.0.0.1` por padrão, ou seja, é destinada ao uso local. Não exponha o servidor publicamente sem implementar autenticação, proteção contra CSRF, limites de recursos e configuração adequada de produção.

## Utilização

1. Informe as dimensões das matrizes, separadas por vírgulas.
2. Informe os números de condição desejados, também separados por vírgulas.
3. Escolha o número de sementes, repetições para medição de tempo e a semente inicial.
4. Clique em **Executar experimentos**.
5. Acompanhe o progresso no painel de monitoramento.
6. Ao finalizar, selecione uma dimensão e uma métrica para atualizar o gráfico e a tabela.
7. Baixe o CSV de resumo ou o CSV detalhado.

A interface permite dimensões de 2 a 500, de 1 a 50 sementes e de 1 a 50 repetições de tempo. A quantidade de avaliações método–sistema–semente por bateria é limitada a 5.000 para evitar configurações acidentalmente muito grandes. Cada avaliação executa uma chamada de aquecimento e o número configurado de repetições cronometradas.

## CSVs

Cada bateria da interface recebe um identificador e grava seus arquivos em `resultados_web/<id-da-execucao>/`:

- `resultados_detalhados.csv`: uma linha por dimensão, condicionamento, semente e método.
- `resumo_resultados.csv`: medianas das sementes por dimensão, condicionamento e método.

O gráfico usa o número de condição em escala logarítmica no eixo X. A tabela mantém as medianas do CSV de resumo.

## Observações metodológicas

- Para a mesma dimensão e repetição, os números de condição compartilham a mesma semente. Isso mantém os fatores ortogonais e a solução verdadeira pareados entre condições, conforme a estratégia do gerador.
- A geração da matriz e o cálculo do número de condição não entram na cronometragem do solucionador.
- O tempo inclui a resolução completa: fatoração e substituições nos métodos LU e QR.
- São executadas chamadas de aquecimento antes das repetições cronometradas; o CSV armazena a mediana dos tempos.
- O resumo agrega as sementes por mediana. Para análise estatística mais completa, consulte também os dados detalhados.
- Os resultados descrevem as implementações e o ambiente de execução utilizados; não devem ser interpretados como uma comparação universal de todas as implementações possíveis dos algoritmos.

## Execução em terminal (sem interface)

A bateria fixa configurada no início de `experimentos.py` continua disponível:

```bash
python experimentos.py
```

Nesse modo, os arquivos são gravados em `resultados/`.
