"""Import every module's models so Base.metadata / Alembic autogenerate see all tables."""

from app.ai import models as ai_models  # noqa: F401
from app.audit import models as audit_models  # noqa: F401
from app.billing import models as billing_models  # noqa: F401
from app.customers import models as customers_models  # noqa: F401
from app.ledger import models as ledger_models  # noqa: F401
from app.payments import models as payments_models  # noqa: F401
from app.products import models as products_models  # noqa: F401
from app.security import models as security_models  # noqa: F401
from app.subscriptions import models as subscriptions_models  # noqa: F401
from app.usage import models as usage_models  # noqa: F401
