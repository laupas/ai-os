from pydantic import BaseModel, ConfigDict


class TradeLimits(BaseModel):
    """Hard limits, enforced in code before Kraken is contacted: the connector's
    settings. Fix them in aios.yaml under `connectors.crypto.settings`, where no
    agent can change them; `connector.yaml` describes them for the console."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    pairs: dict[str, str] = {"BTC": "XBTCHF", "ETH": "ETHCHF"}
    min_chf: float = 10
    max_chf_per_order: float = 200
    max_chf_per_day: float = 500
    max_orders_per_day: int = 5
    cooldown_seconds: int = 60
    taker_fee_rate: float = 0.004
    """Only for estimates; the real fee comes back from Kraken."""
