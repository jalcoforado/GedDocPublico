from app.auth.password import hash_md5, verify_md5


def test_admin123_matches_known_md5():
    # Same hash stored in utils.usuario for admin@local.test
    assert hash_md5("admin123") == "0192023a7bbd73250516f069df18b500"


def test_verify_round_trip():
    assert verify_md5("admin123", "0192023a7bbd73250516f069df18b500") is True
    assert verify_md5("wrong", "0192023a7bbd73250516f069df18b500") is False


def test_php_php_md5_examples():
    # Sanity check vs. PHP's md5() behavior — UTF-8 input
    assert hash_md5("") == "d41d8cd98f00b204e9800998ecf8427e"
    assert hash_md5("foo") == "acbd18db4cc2f85cedef654fccc4a4d8"
