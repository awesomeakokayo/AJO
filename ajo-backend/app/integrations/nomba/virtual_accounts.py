import logging

from sqlalchemy.orm import Session

from app import models
from app.integrations.nomba.client import nomba_client
from app.integrations.nomba.schemas import VirtualAccountResponse

logger = logging.getLogger(__name__)


async def create_circle_virtual_account(
    db: Session,
    circle: models.Circle,
) -> VirtualAccountResponse:
    account_ref = f"ajo-circle-{circle.id}"

    payload = {
        "accountRef": account_ref,
        "accountName": circle.name,
        "expectedAmount": str(int(circle.contribution_amount)),
    }

    data = await nomba_client.post("/v1/accounts/virtual", payload)
    response = VirtualAccountResponse(**data)

    circle.nomba_account_ref = response.accountRef
    circle.nomba_account_number = response.accountNumber
    db.commit()

    logger.info(
        "Created Nomba virtual account for circle %d: %s (%s)",
        circle.id, response.accountNumber, response.accountRef,
    )
    return response


async def fetch_virtual_account(account_ref: str) -> VirtualAccountResponse:
    data = await nomba_client.get(f"/v1/accounts/virtual/{account_ref}")
    return VirtualAccountResponse(**data)
