/**
 * Ponto de entrada standalone do Base Lucas.
 *
 * Em produção o normal é NÃO usar este arquivo: monte o router direto no app
 * do 4M&C Market (ver README, seção "Integração"). Este servidor existe para
 * rodar e testar o módulo isolado.
 */

require("dotenv").config();

const express = require("express");
const baseRoutes = require("./routes/baseRoutes");
const migration = require("./migrations/001_base_tables");
const ml = require("./controllers/baseMercadolivreController");

const app = express();
app.use(express.json({ limit: "5mb" }));

// CORS restrito às origens do projeto — sem liberar geral.
const ORIGENS = (process.env.BASE_ALLOWED_ORIGINS ||
  "https://controleestoque4mec.pro,http://localhost:3000,http://localhost:5173")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);

app.use((req, res, next) => {
  const origem = req.headers.origin;
  if (origem && ORIGENS.includes(origem)) {
    res.setHeader("Access-Control-Allow-Origin", origem);
    res.setHeader("Vary", "Origin");
  }
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

app.use("/api/v1/base", baseRoutes);

// Frontend estático. Em produção ele vive no HostGator; aqui é servido junto
// para dar um alvo de teste local sem precisar de um segundo servidor.
const path = require("path");
app.use("/app", express.static(path.join(__dirname, "..", "..", "frontend")));

app.get("/", (req, res) => res.redirect("/app"));

const PORT = Number(process.env.PORT || 3000);

async function bootstrap() {
  await migration.up();
  console.log("[base] migrations aplicadas");

  if (String(process.env.BASE_AUTO_SYNC ?? "true").toLowerCase() !== "false") {
    ml.iniciarCronSync(Number(process.env.BASE_SYNC_INTERVAL_MS || 300000));
    console.log("[base] cron de sync ML ativo (5 min)");
  }

  app.listen(PORT, () => console.log(`[base] Base Lucas ouvindo na porta ${PORT}`));
}

bootstrap().catch((err) => {
  console.error("[base] falha no bootstrap:", err);
  process.exit(1);
});

module.exports = app;
