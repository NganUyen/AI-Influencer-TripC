from services.customer_token_vault import CustomerTokenVault


def test_customer_token_vault_round_trip():
    sealed = CustomerTokenVault.seal(
        {
            "access_token": "access-123",
            "refresh_token": "refresh-123",
            "scope": "tweet.write users.read",
        }
    )

    opened = CustomerTokenVault.open(sealed)

    assert opened["access_token"] == "access-123"
    assert opened["refresh_token"] == "refresh-123"
    assert opened["scope"] == "tweet.write users.read"
