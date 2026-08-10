import os
from pathlib import Path
from typing import Annotated, List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Raiz de apps/api — o .env fica aqui, ao lado do requirements.txt.
API_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = API_ROOT / ".env"

DEFAULT_SECRET_KEY = "super-secret-key-change-in-production-omnichannel-base"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Omnichannel SaaS Platform AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Settings for local testing vs production
    ENVIRONMENT: str = "local"
    MOCK_INTEGRATIONS: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./omnichannel_real.db"

    # Redis & RabbitMQ
    REDIS_URL: str = "redis://localhost:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # BaseLinker — sempre via .env, nunca no código-fonte
    BASELINKER_API_TOKEN: str = ""
    BASELINKER_TOKEN: str = ""  # alias legado aceito no .env

    # Mercado Livre — credenciais do app criado no DevCenter
    # https://developers.mercadolivre.com.br/devcenter
    ML_CLIENT_ID: str = ""
    ML_CLIENT_SECRET: str = ""
    ML_REDIRECT_URI: str = "http://localhost:8000/api/v1/ml/auth/callback"
    ML_SITE_ID: str = "MLB"  # MLB = Brasil
    ML_WEBHOOK_SECRET: str = ""
    # Escrita no ML bloqueada até homologação explícita
    ML_READ_ONLY: bool = True

    # Feed read-only (bridge Base Antigravity → ML)
    # Base: .../api/base-antigravity/ml  → /feed /orders /items /questions /token
    ML_FEED_BASE_URL: str = "https://fourmc-market-api.onrender.com/api/base-antigravity/ml"
    ML_FEED_URL: str = "https://fourmc-market-api.onrender.com/api/base-antigravity/ml/feed"
    ML_FEED_ORDERS_URL: str = "https://fourmc-market-api.onrender.com/api/base-antigravity/ml/orders"
    ML_FEED_TOKEN_URL: str = "https://fourmc-market-api.onrender.com/api/base-antigravity/ml/token"

    # BaseLinker — molde/estudo; writes bloqueados por default
    BASELINKER_READ_ONLY: bool = True

    # ---------------------------------------------------------------------------
    # Bling ERP API v3 — Macro Fiscal (Etapa 2)
    # Docs: docs/BLING_API_STUDY.md · developer.bling.com.br
    # Defaults seguros até homologação: READ_ONLY + NF-e off.
    # ---------------------------------------------------------------------------
    BLING_CLIENT_ID: str = ""
    BLING_CLIENT_SECRET: str = ""
    BLING_REDIRECT_URI: str = "http://localhost:8000/api/v1/bling/callback"
    BLING_ACCOUNT_KEY: str = "4mc"  # chave em BlingConfigDB (4mc / portal / max / …)
    BLING_READ_ONLY: bool = True
    NFE_EMIT_ENABLED: bool = False
    # Auto: após sync, pedidos pagos sem bling_pedido_id → push (ainda respeita READ_ONLY/NFE)
    BLING_AUTO_PUSH_ON_PAID: bool = True
    # ID da Natureza de Operação no Bling (obrigatório para emitir NF-e)
    BLING_NATUREZA_OPERACAO_ID: int = 0
    BLING_API_BASE_URL: str = "https://api.bling.com.br/Api/v3"
    BLING_AUTH_BASE_URL: str = "https://www.bling.com.br/Api/v3/oauth"

    # CORS Origins — aceita lista JSON ou valores separados por vírgula no .env.
    # NoDecode desliga o parser JSON do pydantic-settings para que o validator
    # abaixo receba a string crua de "a,b,c".
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # JWT Security
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        # O .env carrega chaves consumidas por outros módulos (PORT, HOST,
        # USE_SQLITE, JWT_SECRET). Ignorar em vez de rejeitar.
        extra="ignore",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Aceita 'a,b,c' no .env, além do formato lista JSON."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Aceita o alias legado BASELINKER_TOKEN quando o principal não vier.
        if not self.BASELINKER_API_TOKEN and self.BASELINKER_TOKEN:
            self.BASELINKER_API_TOKEN = self.BASELINKER_TOKEN

        if self.ENVIRONMENT == "production" and self.SECRET_KEY == DEFAULT_SECRET_KEY:
            raise ValueError(
                "CRITICAL: SECRET_KEY padrão não pode ser usada em ambiente de produção!"
            )


settings = Settings()

# Espelha no ambiente do processo para os módulos que ainda leem os.getenv
# diretamente (infrastructure/database.py, baselinker_client.py).
for _key in ("DATABASE_URL", "BASELINKER_API_TOKEN", "BASELINKER_TOKEN", "REDIS_URL", "RABBITMQ_URL"):
    _value = getattr(settings, _key, "")
    if _value:
        os.environ.setdefault(_key, str(_value))
