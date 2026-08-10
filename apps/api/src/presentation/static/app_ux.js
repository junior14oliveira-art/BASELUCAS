/**
 * BASE ANTIGRAVITY — helpers de UX / erros (heurísticas Nielsen) para /app.
 * PT-BR. Cache local nunca é apagado por falha de rede/sync.
 * Carregado via /app/static/app_ux.js — compartilhável entre inline scripts.
 */
(function (global) {
  'use strict';

  var _toastTimer = null;

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function hideToast() {
    var el = document.getElementById('app-toast');
    if (el) el.classList.remove('show');
    if (_toastTimer) {
      clearTimeout(_toastTimer);
      _toastTimer = null;
    }
  }

  /**
   * @param {string} message
   * @param {'success'|'error'|'info'|'warning'} [kind]
   * @param {{label:string,onClick?:Function}[]} [actions]
   */
  function showToast(message, kind, actions) {
    var el = document.getElementById('app-toast');
    if (!el) {
      try { alert(message); } catch (_) {}
      return;
    }
    var type = kind || 'info';
    if (type !== 'success' && type !== 'error' && type !== 'info' && type !== 'warning') {
      type = 'info';
    }
    el.className = 'app-toast ' + type + ' show';
    el.setAttribute('role', type === 'error' || type === 'warning' ? 'alert' : 'status');
    var html = '<div style="flex:1;"><div>' + escapeHtml(message) + '</div>';
    if (actions && actions.length) {
      html += '<div class="toast-actions">';
      actions.forEach(function (a, i) {
        html += '<button type="button" data-toast-action="' + i + '">' + escapeHtml(a.label) + '</button>';
      });
      html += '</div>';
    }
    html += '</div><button type="button" aria-label="Fechar" style="border:none;background:transparent;color:inherit;cursor:pointer;font-size:1.1rem;line-height:1;" onclick="window.AppUx && AppUx.hideToast()">×</button>';
    el.innerHTML = html;
    if (actions && actions.length) {
      el.querySelectorAll('[data-toast-action]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var idx = Number(btn.getAttribute('data-toast-action'));
          hideToast();
          try {
            if (actions[idx] && actions[idx].onClick) actions[idx].onClick();
          } catch (e) {
            console.error(e);
          }
        });
      });
    }
    if (_toastTimer) clearTimeout(_toastTimer);
    var hold = actions && actions.length ? 12000 : type === 'error' || type === 'warning' ? 7000 : 4500;
    _toastTimer = setTimeout(hideToast, hold);
  }

  /** Mensagens honestas para ações ainda não ligadas à API (Nielsen #1 e #5). */
  var STUB_ACTION_LABELS = {
    star: 'Favoritar pedidos',
    flag: 'Sinalizar pedidos',
    email: 'Enviar e-mail / WhatsApp',
    print: 'Imprimir etiquetas',
    ship: 'Despachar pacotes',
    filter: 'Filtro avançado',
    sort: 'Ordenar por preço',
  };

  function notifyStub(action, selCount) {
    var label = STUB_ACTION_LABELS[action] || ('Ação "' + action + '"');
    var n = typeof selCount === 'number' ? selCount : 0;
    var extra =
      n > 0
        ? ' (' + n + ' pedido(s) selecionado(s) — seleção mantida).'
        : '. Selecione pedidos quando a função estiver disponível.';
    showToast(
      label + ' ainda não está disponível nesta versão' + extra,
      'warning'
    );
  }

  function friendlyHttpError(err, res) {
    if (res) {
      if (res.status === 429) {
        return 'Muitas requisições (429). Aguarde um momento e tente novamente. O cache local foi mantido.';
      }
      if (res.status >= 500) {
        return 'Servidor indisponível (' + res.status + '). Seus dados locais continuam no SQLite.';
      }
      if (res.status === 404) {
        return 'Endpoint não encontrado (404). Reinicie a API ou atualize a página (Ctrl+F5).';
      }
      if (res.status === 401 || res.status === 403) {
        return 'Sem permissão (' + res.status + '). Verifique o token no .env (sem expor o valor).';
      }
    }
    var msg = String((err && err.message) || err || 'Erro desconhecido');
    if (/failed to fetch|networkerror|network request failed/i.test(msg)) {
      return 'Sem conexão com a API local. Confira se o uvicorn está rodando em :8000. Cache preservado.';
    }
    if (/timeout|timed out/i.test(msg)) {
      return 'Tempo esgotado. Tente novamente — o cache local não foi apagado.';
    }
    return msg;
  }

  function setBusyButtons(selector, busy, label) {
    document.querySelectorAll(selector).forEach(function (btn) {
      if (!btn.dataset.origHtml) btn.dataset.origHtml = btn.innerHTML;
      btn.disabled = !!busy;
      if (busy) {
        btn.innerHTML =
          '<span class="material-icons" style="animation:spin 1s linear infinite;font-size:18px;">sync</span> ' +
          (label || 'Aguarde...');
      } else {
        btn.innerHTML = btn.dataset.origHtml;
      }
    });
  }

  /**
   * Validação de intervalo: de ≤ até.
   * @returns {{ok:boolean, from:Date|null, to:Date|null, error?:string}}
   */
  function validateDateRange(fromValue, toValue) {
    if (!fromValue && !toValue) {
      return { ok: false, from: null, to: null, error: 'Informe Data de e/ou Data até para filtrar.' };
    }
    var from = null;
    var to = null;
    if (fromValue) {
      from = new Date(fromValue + 'T00:00:00');
      from.setHours(0, 0, 0, 0);
      if (isNaN(from.getTime())) {
        return { ok: false, from: null, to: null, error: 'Data inicial inválida.' };
      }
    }
    if (toValue) {
      to = new Date(toValue + 'T00:00:00');
      to.setHours(23, 59, 59, 999);
      if (isNaN(to.getTime())) {
        return { ok: false, from: null, to: null, error: 'Data final inválida.' };
      }
    }
    if (from && to && from.getTime() > to.getTime()) {
      return {
        ok: false,
        from: null,
        to: null,
        error: 'Intervalo inválido: "Data de" deve ser menor ou igual a "Data até".',
      };
    }
    return { ok: true, from: from, to: to };
  }

  /**
   * Confirmação de ação destrutiva local (Nielsen: prevenção de erros).
   * @param {string} message
   * @returns {boolean}
   */
  function confirmDestructive(message) {
    try {
      return !!window.confirm(message);
    } catch (_) {
      return false;
    }
  }

  /** Tip padrão para empty state com filtros. */
  var CLEAR_FILTER_TIP =
    'Dica: use Limpar filtro / Limpar filtros para voltar à lista completa do cache local.';

  /** Empty state inline para tbody de tabela (Nielsen #1 / #6). */
  function emptyTableRowHtml(colspan, title, hint) {
    var c = colspan || 7;
    var t = title || 'Nenhum pedido nesta visão.';
    var h = hint || CLEAR_FILTER_TIP;
    return (
      '<tr class="empty-row"><td colspan="' +
      c +
      '" style="text-align:center;padding:28px 16px;">' +
      '<div style="font-weight:700;color:#E2E8F0;">' +
      escapeHtml(t) +
      '</div>' +
      '<p style="margin:8px 0 0;font-size:0.78rem;color:#94A3B8;line-height:1.4;max-width:420px;margin-left:auto;margin-right:auto;">' +
      escapeHtml(h) +
      '</p></td></tr>'
    );
  }

  function emptyFilterHtml(opts) {
    opts = opts || {};
    var title = opts.title || 'Nenhum resultado neste filtro.';
    var clearFn = opts.clearFn || 'clearAllFilters()';
    var clearLabel = opts.clearLabel || 'Limpar filtros';
    return (
      '<div class="empty-state empty-state--filter">' +
      '<div>' +
      escapeHtml(title) +
      '</div>' +
      '<p style="margin:10px 0 0;font-size:0.8rem;line-height:1.4;">' +
      escapeHtml(CLEAR_FILTER_TIP) +
      '</p>' +
      '<div style="margin-top:12px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">' +
      '<button type="button" class="btn" onclick="' +
      clearFn +
      '">' +
      escapeHtml(clearLabel) +
      '</button>' +
      (opts.extraButtonsHtml || '') +
      '</div></div>'
    );
  }

  /**
   * Liga empty states de lista/filtro sem quebrar switchTab.
   * Espera elementos #orders-empty, #orders-filter-empty, etc.
   */
  function syncListEmptyStates(cfg) {
    cfg = cfg || {};
    var total = cfg.totalCount || 0;
    var filtered = cfg.filteredCount || 0;
    var hasActiveFilter = !!cfg.hasActiveFilter;
    var emptyEl = cfg.emptyEl ? document.getElementById(cfg.emptyEl) : null;
    var filterEmptyEl = cfg.filterEmptyEl ? document.getElementById(cfg.filterEmptyEl) : null;
    var tableWrap = cfg.hideTableSelector
      ? document.querySelector(cfg.hideTableSelector)
      : null;

    if (emptyEl) emptyEl.style.display = total === 0 ? 'block' : 'none';
    if (filterEmptyEl) {
      var showFilterEmpty = total > 0 && filtered === 0 && hasActiveFilter;
      filterEmptyEl.style.display = showFilterEmpty ? 'block' : 'none';
    }
    if (tableWrap) {
      var hide = (total === 0) || (total > 0 && filtered === 0 && hasActiveFilter);
      tableWrap.style.display = hide ? 'none' : '';
    }
  }

  global.AppUx = {
    escapeHtml: escapeHtml,
    showToast: showToast,
    hideToast: hideToast,
    friendlyHttpError: friendlyHttpError,
    setBusyButtons: setBusyButtons,
    validateDateRange: validateDateRange,
    confirmDestructive: confirmDestructive,
    CLEAR_FILTER_TIP: CLEAR_FILTER_TIP,
    emptyFilterHtml: emptyFilterHtml,
    emptyTableRowHtml: emptyTableRowHtml,
    syncListEmptyStates: syncListEmptyStates,
    STUB_ACTION_LABELS: STUB_ACTION_LABELS,
    notifyStub: notifyStub,
  };

  // Aliases globais compatíveis com o inline de /app (não sobrescreve se já existir).
  if (typeof global.showAppToast !== 'function') {
    global.showAppToast = function (m, k, a) {
      return showToast(m, k, a);
    };
  }
  if (typeof global.hideAppToast !== 'function') {
    global.hideAppToast = hideToast;
  }
  if (typeof global.friendlyHttpError !== 'function') {
    global.friendlyHttpError = friendlyHttpError;
  }
  if (typeof global.confirmDestructive !== 'function') {
    global.confirmDestructive = confirmDestructive;
  }
})(typeof window !== 'undefined' ? window : globalThis);
