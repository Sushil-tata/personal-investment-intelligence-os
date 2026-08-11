from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Personal Investment Intelligence OS"
    short_name: str = "PIIOS"
    app_version: str = "0.3.2"
    api_prefix: str = "/api/v1"
    env: str = "dev"
    db_url: str = "postgresql+psycopg://piios:piios@localhost:5432/piios_db"
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"
    vector_backend: str = "chroma"
    vector_path: str = "./.vector_store"
    vector_collection: str = "piios_research_memory"
    model_version: str = "piios-model-0.3.2"
    live_market_feeds: bool = True
    allow_synthetic_market_fallbacks: bool = False
    run_db_migrations_in_tests: bool = False
    live_tickers: str = "NVDA,AVGO,MSFT,PG,KO,COST,TSLA,XOM,DE,UBER"
    portfolio_dual_run_enabled: bool = False
    portfolio_dual_run_money_tolerance: float = 0.01
    portfolio_dual_run_percentage_tolerance: float = 0.01

    market_refresh_cron: str = "0 18 * * *"
    watchlist_refresh_cron: str = "30 18 * * *"
    alert_generation_cron: str = "0 19 * * *"
    weekly_drift_cron: str = "0 9 * * 1"
    weekly_reco_cron: str = "0 10 * * 1"

    model_config = SettingsConfigDict(env_prefix="PIIOS_", env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def live_tickers_list(self) -> list[str]:
        return [part.strip().upper() for part in self.live_tickers.split(",") if part.strip()]


settings = Settings()
