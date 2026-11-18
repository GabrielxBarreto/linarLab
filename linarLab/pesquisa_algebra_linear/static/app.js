(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('experiment-form');
  const runButton = $('run-button');
  const chartCanvas = $('results-chart');
  let activeJobId = null;
  let pollTimer = null;
  let chartInstance = null;
  let allSummaryRows = [];
  let currentFiles = null;

  const metricInfo = {
    erro_relativo_mediano: { label: 'Erro relativo', unit: 'Erro relativo (mediana)', format: 'number' },
    residuo_relativo_mediano: { label: 'Resíduo relativo', unit: 'Resíduo relativo (mediana)', format: 'number' },
    erro_retroativo_mediano: { label: 'Erro retroativo', unit: 'Erro retroativo (mediana)', format: 'number' },
    tempo_mediano_s: { label: 'Tempo de execução', unit: 'Tempo mediano (segundos)', format: 'time' },
    erro_absoluto_mediano: { label: 'Erro absoluto', unit: 'Erro absoluto (mediana)', format: 'number' },
  };

  const methodColors = {
    Gauss: '#5479ef',
    LU: '#22a879',
    QR_Householder: '#9270db',
  };

  function parseList(text, cast, label) {
    const values = text.split(',').map((part) => part.trim()).filter(Boolean).map((part) => {
      const value = cast(part);
      if (!Number.isFinite(value)) throw new Error(`Valor inválido em ${label}: ${part}`);
      return value;
    });
    if (!values.length) throw new Error(`Informe ao menos um valor em ${label}.`);
    if (new Set(values).size !== values.length) throw new Error(`Remova valores repetidos de ${label}.`);
    return values;
  }

  function getPayload() {
    return {
      dimensoes: parseList($('dimensions').value, Number, 'dimensões'),
      condicoes: parseList($('conditions').value, Number, 'números de condição'),
      num_sementes: Number($('seeds').value),
      repeticoes_tempo: Number($('timings').value),
      seed_base: Number($('seed-base').value),
    };
  }

  function updateEstimate() {
    try {
      const dimensions = parseList($('dimensions').value, Number, 'dimensões');
      const conditions = parseList($('conditions').value, Number, 'condições');
      const seeds = Number($('seeds').value);
      const total = dimensions.length * conditions.length * seeds * 3;
      $('execution-estimate').textContent = Number.isFinite(total) ? total.toLocaleString('pt-BR') : '—';
    } catch (_) {
      $('execution-estimate').textContent = '—';
    }
  }

  ['dimensions', 'conditions', 'seeds'].forEach((id) => {
    $(id).addEventListener('input', updateEstimate);
  });

  function setRunStatus(status, label) {
    const badge = $('run-status');
    badge.className = `run-badge ${status}`;
    badge.textContent = label;
  }

  function setProgress(current, total, message) {
    const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
    $('progress-current').textContent = Number(current || 0).toLocaleString('pt-BR');
    $('progress-total').textContent = Number(total || 0).toLocaleString('pt-BR');
    $('progress-percent').textContent = `${percent}%`;
    $('progress-fill').style.width = `${percent}%`;
    $('progress-message').textContent = message || 'Executando experimento...';
  }

  function setCurrentCase(currentCase) {
    $('current-dimension').textContent = currentCase?.dimensao ?? '—';
    $('current-condition').textContent = currentCase?.condicao != null ? fmt(currentCase.condicao) : '—';
    $('current-method').textContent = currentCase?.metodo || '—';
    $('current-result').textContent = currentCase?.status || '—';
  }

  function showError(message) {
    const box = $('job-error');
    box.textContent = message;
    box.classList.remove('hidden');
  }

  function clearError() {
    $('job-error').textContent = '';
    $('job-error').classList.add('hidden');
  }

  function fmt(value, digits = 4) {
    if (value === null || value === undefined || value === '') return '—';
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    if (number === 0) return '0';
    if (Math.abs(number) >= 10000 || Math.abs(number) < 0.001) {
      return number.toExponential(3).replace('e+', 'e');
    }
    return number.toLocaleString('pt-BR', { maximumSignificantDigits: digits });
  }

  function fmtInt(value) {
    return Number(value || 0).toLocaleString('pt-BR');
  }

  async function startExperiment(event) {
    event.preventDefault();
    clearError();
    let payload;
    try {
      payload = getPayload();
      if (payload.dimensoes.some((n) => !Number.isInteger(n) || n < 2 || n > 500)) {
        throw new Error('As dimensões devem ser inteiros entre 2 e 500.');
      }
      if (payload.condicoes.some((n) => n < 1)) {
        throw new Error('Os números de condição devem ser maiores ou iguais a 1.');
      }
      if (!Number.isInteger(payload.num_sementes) || payload.num_sementes < 1 || payload.num_sementes > 50) {
        throw new Error('Use de 1 a 50 sementes.');
      }
      if (!Number.isInteger(payload.repeticoes_tempo) || payload.repeticoes_tempo < 1 || payload.repeticoes_tempo > 50) {
        throw new Error('Use de 1 a 50 repetições de tempo.');
      }
      if (!Number.isInteger(payload.seed_base) || payload.seed_base < 0) {
        throw new Error('A semente inicial deve ser um inteiro não negativo.');
      }
    } catch (error) {
      showError(error.message);
      return;
    }

    runButton.disabled = true;
    runButton.querySelector('span:nth-child(2)').textContent = 'Preparando execução...';
    setRunStatus('running', 'INICIANDO');
    setProgress(0, payload.dimensoes.length * payload.condicoes.length * payload.num_sementes * 3, 'Solicitando início dos experimentos...');
    setCurrentCase(null);

    try {
      const response = await fetch('/api/experimentos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Falha ao iniciar o experimento.');
      activeJobId = data.job_id;
      pollStatus();
    } catch (error) {
      setRunStatus('failed', 'ERRO');
      runButton.disabled = false;
      runButton.querySelector('span:nth-child(2)').textContent = 'Executar experimentos';
      showError(error.message);
    }
  }

  async function pollStatus() {
    if (!activeJobId) return;
    try {
      const response = await fetch(`/api/status/${activeJobId}`, { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível consultar o andamento.');

      const status = data.status;
      setProgress(data.progress, data.total, data.message);
      setCurrentCase(data.current_case);

      if (status === 'queued' || status === 'running') {
        setRunStatus('running', status === 'queued' ? 'NA FILA' : 'EM EXECUÇÃO');
        pollTimer = window.setTimeout(pollStatus, 700);
        return;
      }

      if (status === 'completed') {
        setRunStatus('completed', 'CONCLUÍDO');
        runButton.disabled = false;
        runButton.querySelector('span:nth-child(2)').textContent = 'Executar nova bateria';
        await loadResults(activeJobId);
        return;
      }

      setRunStatus('failed', 'FALHA');
      runButton.disabled = false;
      runButton.querySelector('span:nth-child(2)').textContent = 'Tentar novamente';
      showError(data.message || 'O experimento terminou com uma falha.');
    } catch (error) {
      setRunStatus('failed', 'ERRO DE CONEXÃO');
      runButton.disabled = false;
      runButton.querySelector('span:nth-child(2)').textContent = 'Tentar novamente';
      showError(error.message);
    }
  }

  async function loadResults(jobId) {
    const response = await fetch(`/api/resultados/${jobId}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível carregar os resultados.');

    allSummaryRows = data.summary || [];
    currentFiles = data.files;
    populateDimensionFilter(data.config?.dimensoes || []);
    const systems = (data.config?.dimensoes?.length || 0)
      * (data.config?.condicoes?.length || 0)
      * (data.config?.num_sementes || 0);
    const successes = allSummaryRows.reduce((sum, row) => sum + Number(row.n_execucoes_sucesso || 0), 0);
    const failures = allSummaryRows.reduce((sum, row) => sum + Number(row.n_falhas || 0), 0);

    $('systems-count').textContent = fmtInt(systems);
    $('success-count').textContent = fmtInt(successes);
    $('failure-count').textContent = fmtInt(failures);
    $('results-indicator').textContent = 'DADOS CARREGADOS';
    $('results-indicator').classList.add('ready');
    $('download-summary').href = data.files.summary;
    $('download-detailed').href = data.files.detailed;
    $('download-row').classList.remove('hidden');
    $('dimension-filter').disabled = false;
    $('metric-filter').disabled = false;
    renderAnalysis();
    $('analysis-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function populateDimensionFilter(dimensions) {
    const select = $('dimension-filter');
    select.innerHTML = '';
    dimensions.forEach((dimension) => {
      const option = document.createElement('option');
      option.value = String(dimension);
      option.textContent = `${dimension} × ${dimension}`;
      select.appendChild(option);
    });
    if (dimensions.length) select.value = String(dimensions[0]);
  }

  function filteredRows() {
    const dimension = Number($('dimension-filter').value);
    return allSummaryRows
      .filter((row) => Number(row.dimensao) === dimension)
      .sort((a, b) => Number(a.condicao_alvo) - Number(b.condicao_alvo));
  }

  function renderAnalysis() {
    const rows = filteredRows();
    renderTable(rows);
    renderChart(rows);
  }

  function renderTable(rows) {
    const body = $('results-table-body');
    body.innerHTML = '';
    $('table-row-count').textContent = `${rows.length.toLocaleString('pt-BR')} registros`;
    if (!rows.length) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="8" class="table-empty">Nenhum registro para a dimensão selecionada.</td>';
      body.appendChild(tr);
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement('tr');
      const values = [
        fmtInt(row.dimensao),
        fmt(row.condicao_alvo),
        row.metodo,
        fmtInt(row.n_execucoes_sucesso),
        fmt(row.tempo_mediano_s),
        fmt(row.erro_relativo_mediano),
        fmt(row.residuo_relativo_mediano),
        fmt(row.erro_retroativo_mediano),
      ];
      values.forEach((value, index) => {
        const td = document.createElement('td');
        td.textContent = value;
        if (index === 2) {
          td.className = 'method-cell';
          td.dataset.method = row.metodo;
        }
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
  }

  function renderChart(rows) {
    const metricKey = $('metric-filter').value;
    const info = metricInfo[metricKey] || metricInfo.erro_relativo_mediano;
    $('chart-unit').textContent = `${info.unit} · eixo X em escala logarítmica`;

    const methods = ['Gauss', 'LU', 'QR_Householder'];
    const datasets = methods.map((method) => {
      const points = rows
        .filter((row) => row.metodo === method && row[metricKey] !== null && Number(row[metricKey]) > 0)
        .map((row) => ({ x: Number(row.condicao_alvo), y: Number(row[metricKey]) }))
        .sort((a, b) => a.x - b.x);
      return {
        label: method === 'QR_Householder' ? 'QR Householder' : method,
        data: points,
        borderColor: methodColors[method],
        backgroundColor: methodColors[method],
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0.16,
        fill: false,
      };
    });

    const hasPoints = datasets.some((dataset) => dataset.data.length > 0);
    if (!hasPoints || typeof Chart === 'undefined') {
      if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
      chartCanvas.classList.add('hidden');
      $('chart-empty').classList.remove('hidden');
      $('chart-empty').querySelector('strong').textContent = typeof Chart === 'undefined'
        ? 'Biblioteca do gráfico indisponível'
        : 'Não há valores positivos para esta métrica';
      $('chart-empty').querySelector('span').textContent = typeof Chart === 'undefined'
        ? 'A tabela continua disponível abaixo; verifique sua conexão para carregar o Chart.js.'
        : 'Os valores iguais a zero ou ausentes não são exibidos em escala logarítmica.';
      return;
    }

    chartCanvas.classList.remove('hidden');
    $('chart-empty').classList.add('hidden');
    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(chartCanvas, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'nearest', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#172238',
            padding: 11,
            titleFont: { family: 'DM Sans', size: 10 },
            bodyFont: { family: 'DM Sans', size: 10 },
            callbacks: {
              title: (items) => items.length ? `κ₂(A): ${fmt(items[0].parsed.x)}` : '',
              label: (context) => `${context.dataset.label}: ${fmt(context.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            type: 'logarithmic',
            title: { display: true, text: 'Número de condição desejado', color: '#8793a6', font: { family: 'DM Sans', size: 10, weight: '600' } },
            ticks: { color: '#909bad', font: { family: 'DM Sans', size: 9 }, callback: (value) => fmt(value, 3) },
            grid: { color: '#eff2f6' },
          },
          y: {
            title: { display: true, text: info.format === 'time' ? 'Segundos' : 'Valor da métrica', color: '#8793a6', font: { family: 'DM Sans', size: 10, weight: '600' } },
            ticks: { color: '#909bad', font: { family: 'DM Sans', size: 9 }, callback: (value) => fmt(value, 3) },
            grid: { color: '#eff2f6' },
          },
        },
      },
    });
  }

  form.addEventListener('submit', startExperiment);
  $('dimension-filter').addEventListener('change', renderAnalysis);
  $('metric-filter').addEventListener('change', renderAnalysis);
  updateEstimate();
})();
