import os


class NombaSettings:
    base_url: str
    account_id: str
    subaccount_id: str
    client_id: str
    client_secret: str
    webhook_signature_key: str

    def __init__(self):
        self.base_url = os.getenv("NOMBA_BASE_URL", "https://api.nomba.com")
        self.account_id = os.getenv("NOMBA_ACCOUNT_ID")
        self.subaccount_id = os.getenv("NOMBA_SUBACCOUNT_ID")
        self.client_id = os.getenv("NOMBA_CLIENT_ID")
        self.client_secret = os.getenv("NOMBA_CLIENT_SECRET")
        self.webhook_signature_key = os.getenv("NOMBA_WEBHOOK_SIGNATURE_KEY")


nomba_settings = NombaSettings()
