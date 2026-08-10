/**
 * Módulo 6 — Dashboard Executivo & Charts.
 * Origem: apps/api/src/presentation/routers/dashboard.py
 *
 * Os períodos e a granularidade automática (por hora em recorte de 1 dia,
 * por dia no resto) espelham o filtro implementado na UI do Base Lucas.
 */

const pedidos = require("../services/ordersRepository");

const PERIODOS = {
  total: "todo o período",
  hoje: "hoje",
  ontem: "ontem",
  "7dias": "últimos 7 dias",
  "30dias": "últimos 30 dias",
  custom: "período personalizado",
};

const inicioDoDia = (d) => {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
};
const fimDoDia = (d) => {
  const x = new Date(d);
  x.setHours(23, 59, 59, 999);
  return x;
};

/** Traduz o preset em um intervalo concreto. */
function resolverPeriodo(periodo, from, to) {
  const agora = new Date();
  switch (periodo) {
    case "hoje":
      return { from: inicioDoDia(agora), to: fimDoDia(agora) };
    case "ontem": {
      const o = new Date(agora);
      o.setDate(o.getDate() - 1);
      return { from: inicioDoDia(o), to: fimDoDia(o) };
    }
    case "7dias": {
      const d = new Date(agora);
      d.setDate(d.getDate() - 6);
      return { from: inicioDoDia(d), to: fimDoDia(agora) };
    }
    case "30dias": {
      const d = new Date(agora);
      d.setDate(d.getDate() - 29);
      return { from: inicioDoDia(d), to: fimDoDia(agora) };
    }
    case "custom":
      return {
        from: from ? new Date(`${from}T00:00:00`) : null,
        to: to ? new Date(`${to}T23:59:59`) : null,
      };
    default:
      return { from: null, to: null };
  }
}

function parseData(valor) {
  if (!valor) return null;
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? null : d;
}

function filtrarPorPeriodo(lista, from, to) {
  if (!from && !to) return lista;
  return lista.filter((o) => {
    const d = parseData(o.date);
    if (!d) return false;
    if (from && d < from) return false;
    if (to && d > to) return false;
    return true;
  });
}

/** Série temporal pronta para o Chart.js. */
function montarSerie(lista, from, to) {
  const datas = lista.map((o) => parseData(o.date)).filter(Boolean);
  const ini = from || (datas.length ? new Date(Math.min(...datas)) : new Date());
  const fim = to || (datas.length ? new Date(Math.max(...datas)) : new Date());
  const spanDias = Math.max(
    1,
    Math.round((fimDoDia(fim) - inicioDoDia(ini)) / 86400000)
  );
  const porHora = spanDias <= 1;

  const buckets = new Map();
  if (porHora) {
    for (let h = 0; h < 24; h++) buckets.set(`${String(h).padStart(2, "0")}h`, 0);
  } else {
    const limite = Math.min(spanDias, 60);
    for (let i = limite - 1; i >= 0; i--) {
      const d = new Date(fimDoDia(fim));
      d.setDate(d.getDate() - i);
      buckets.set(
        `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`,
        0
      );
    }
  }

  for (const pedido of lista) {
    const d = parseData(pedido.date);
    if (!d) continue;
    const chave = porHora
      ? `${String(d.getHours()).padStart(2, "0")}h`
      : `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (buckets.has(chave)) buckets.set(chave, buckets.get(chave) + 1);
  }

  return {
    labels: [...buckets.keys()],
    valores: [...buckets.values()],
    granularidade: porHora ? "hora" : "dia",
  };
}

/**
 * GET /api/v1/base/dashboard/kpis?period=hoje|ontem|7dias|30dias|total|custom
 * Com period=custom, aceita &from=YYYY-MM-DD&to=YYYY-MM-DD.
 */
async function getKpis(req, res) {
  try {
    const periodo = String(req.query.period || "total");
    const { from, to } = resolverPeriodo(periodo, req.query.from, req.query.to);

    const todos = await pedidos.listarPedidos({ limit: 5000 });
    const lista = filtrarPorPeriodo(todos, from, to);

    const faturamento = lista.reduce((s, o) => s + Number(o.price || 0), 0);
    const ticket = lista.length ? faturamento / lista.length : 0;

    // Quando o recorte vem vazio, dizer onde os dados realmente estão.
    let aviso = null;
    if (!lista.length && todos.length) {
      const datas = todos.map((o) => parseData(o.date)).filter(Boolean);
      if (datas.length) {
        const min = new Date(Math.min(...datas));
        const max = new Date(Math.max(...datas));
        aviso =
          `Nenhum pedido neste recorte. O cache vai de ` +
          `${min.toLocaleDateString("pt-BR")} a ${max.toLocaleDateString("pt-BR")}.`;
      }
    }

    res.json({
      period: periodo,
      period_label: PERIODOS[periodo] || periodo,
      from: from ? from.toISOString() : null,
      to: to ? to.toISOString() : null,
      pedidos_total: lista.length,
      pedidos_no_cache: todos.length,
      faturamento_total: Number(faturamento.toFixed(2)),
      ticket_medio: Number(ticket.toFixed(2)),
      warning: aviso,
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao montar KPIs", detail: err.message });
  }
}

/** GET /api/v1/base/dashboard/series — dataset do gráfico de volume. */
async function getSeries(req, res) {
  try {
    const periodo = String(req.query.period || "total");
    const { from, to } = resolverPeriodo(periodo, req.query.from, req.query.to);

    const todos = await pedidos.listarPedidos({ limit: 5000 });
    const lista = filtrarPorPeriodo(todos, from, to);
    const serie = montarSerie(lista, from, to);

    res.json({
      period: periodo,
      period_label: PERIODOS[periodo] || periodo,
      granularity: serie.granularidade,
      labels: serie.labels,
      datasets: [{ label: "Pedidos", data: serie.valores }],
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao montar série", detail: err.message });
  }
}

/** GET /api/v1/base/dashboard/distribution — dataset do donut por fila. */
async function getDistribution(req, res) {
  try {
    const periodo = String(req.query.period || "total");
    const { from, to } = resolverPeriodo(periodo, req.query.from, req.query.to);

    const todos = await pedidos.listarPedidos({ limit: 5000 });
    const lista = filtrarPorPeriodo(todos, from, to);

    const contagem = {};
    for (const o of lista) {
      const fila = o.status || "(sem fila)";
      contagem[fila] = (contagem[fila] || 0) + 1;
    }
    const labels = Object.keys(contagem);

    res.json({
      period: periodo,
      labels: labels.length ? labels : ["Sem pedidos no período"],
      datasets: [{ data: labels.length ? labels.map((l) => contagem[l]) : [1] }],
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao montar distribuição", detail: err.message });
  }
}

module.exports = { getKpis, getSeries, getDistribution, resolverPeriodo, PERIODOS };
