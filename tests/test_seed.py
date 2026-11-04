import pytest

from app import db
from app.models import User
from seed import _require_empty_database


def test_seed_refuses_to_run_when_customer_data_exists(app):
    with app.app_context():
        customer = User(
            username="existing_customer",
            email="existing@example.com",
            full_name="Existing Customer",
        )
        customer.set_password("SecurePass123!")
        db.session.add(customer)
        db.session.commit()

        with pytest.raises(RuntimeError, match="already contains customer data"):
            _require_empty_database()

        assert db.session.get(User, customer.id) is not None
