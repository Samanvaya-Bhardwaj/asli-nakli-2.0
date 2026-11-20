from asali_codes.alphabet import ALPHABET
from asali_codes.checks import luhn32_is_valid
from asali_codes.evaluate import METHODS, NOISE, evaluate, make_noisy, make_population


def test_the_population_is_made_of_valid_codes_of_three_makers_and_is_repeatable():
    a, b = make_population(300, seed=1), make_population(300, seed=1)
    assert a == b and len(set(a)) == 300
    assert all(luhn32_is_valid(s) and len(s) == 11 for s in a)
    assert {s[:2] for s in a} == {"TP", "MV", "KS"}


def test_every_noise_kind_changes_the_code_and_never_leaves_the_alphabet_unless_it_looks_like_a_real_misread():
    pop = make_population(200, seed=2)
    import random

    rng = random.Random(3)
    for kind in NOISE:
        for s in pop[:50]:
            noisy = make_noisy(s, kind, rng)
            assert noisy != s
            if kind in ("swap", "double"):
                assert set(noisy) <= set(ALPHABET)


def test_the_methods_are_ranked_the_way_the_design_argues():
    res = evaluate(
        population=300, per_condition=5, seed=5, kinds=["lookalike1", "swap", "lookalike_neighbours"]
    )
    top1 = {m: res["overall"][m]["top1"] for m in METHODS}
    assert (
        top1["exact"]
        < top1["levenshtein"]
        <= top1["weighted"]
        <= top1["weighted_checksum"]
        <= top1["weighted_checksum_context"]
    )
    assert (
        res["overall"]["weighted_checksum"]["wrong_auto_accept"]
        <= res["overall"]["levenshtein"]["wrong_auto_accept"]
    )
