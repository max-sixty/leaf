def exhaust(limiter, request):
    for _ in range(limiter.capacity):
        assert limiter.allow(request)


def test_bucket_key_prefers_token_and_falls_back_to_address(limiter, request):
    tokened = request(token="alpha", remote_addr="203.0.113.8")
    untokened = request(token=None, remote_addr="198.51.100.4")

    assert limiter.bucket_key(tokened) == "tok:alpha"
    assert limiter.bucket_key(untokened) == "ip:198.51.100.4"


def test_two_tokens_behind_one_address_each_get_a_full_budget(limiter, request):
    alpha = request(token="alpha", remote_addr="203.0.113.8")
    bravo = request(token="bravo", remote_addr="203.0.113.8")

    exhaust(limiter, alpha)

    assert limiter.allow(bravo)


def test_two_addresses_on_one_token_share_one_budget(limiter, request):
    office = request(token="alpha", remote_addr="203.0.113.8")
    home = request(token="alpha", remote_addr="198.51.100.4")

    exhaust(limiter, office)

    assert not limiter.allow(home)
