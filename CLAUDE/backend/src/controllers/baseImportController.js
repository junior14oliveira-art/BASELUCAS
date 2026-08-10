/**
 * Stub — importação Baselinker/ML ainda não implementada neste workspace.
 * Mantém as rotas registráveis para o servidor subir (OAuth Bling etc.).
 */

function notImplemented(req, res) {
  res.status(501).json({
    ok: false,
    error: "import_not_implemented",
    message: "Importação ainda não disponível neste build.",
  });
}

exports.importarBaseLinker = notImplemented;
exports.importarPedidosBaseLinker = notImplemented;
exports.importarMercadoLivre = notImplemented;
exports.importarTudo = notImplemented;
