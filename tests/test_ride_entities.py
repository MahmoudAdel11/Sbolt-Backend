import pytest

from app.domain.ride.entities import RideTier, tiers_at_or_below


@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (RideTier.ECONOMY, {RideTier.ECONOMY}),
        (RideTier.COMFORT, {RideTier.ECONOMY, RideTier.COMFORT}),
        (RideTier.PREMIUM, {RideTier.ECONOMY, RideTier.COMFORT, RideTier.PREMIUM}),
    ],
)
def test_tiers_at_or_below_returns_own_tier_and_everything_ranked_lower(
    tier: RideTier, expected: set[RideTier]
) -> None:
    assert set(tiers_at_or_below(tier)) == expected


def test_tiers_at_or_below_never_includes_a_higher_tier() -> None:
    assert RideTier.PREMIUM not in tiers_at_or_below(RideTier.ECONOMY)
    assert RideTier.PREMIUM not in tiers_at_or_below(RideTier.COMFORT)
    assert RideTier.COMFORT not in tiers_at_or_below(RideTier.ECONOMY)
