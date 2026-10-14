"""Reference growth curves for juniors, by age.

Source: Abdel-Hamid T. M. (2015). Crossbreeding parameters for growth traits in
a complete three breeds diallel cross design of rabbits in Egypt. Journal of
Advanced Veterinary and Animal Research 2(2):120-127, Table 2 ("Effects of
mating type of rabbit on body weights at different ages"), least-squares mean
body weight in grams at 4, 6, 8, 10 and 12 weeks.
https://bdvets.org/JAVAR/V2I2/b60_pp120-127.pdf
  NN (New Zealand White purebred):   590, 1105, 1494, 1810, 2131
  NN x CC (NZW sire x Californian):  607, 1307, 1710, 1977, 2218
The study measured weaning (4 wk) to 12 weeks only, so there is no curve
before 4 weeks or after 12; values between are straight-line interpolations.
Commercial US meat lines are often heavier; the band is a guide, not a standard.
"""

NZ_SOURCE = "New Zealand White, Abdel-Hamid 2015 (JAVAR 2:120-127)"
CROSS_SOURCE = "NZ x Californian, Abdel-Hamid 2015 (JAVAR 2:120-127)"

NZ = {28: 590, 42: 1105, 56: 1494, 70: 1810, 84: 2131}
NZ_X_CAL = {28: 607, 42: 1307, 56: 1710, 70: 1977, 84: 2218}

# Within this fraction of the curve counts as on track.
ON_TRACK = 0.10


def curve_for(rabbit):
    """(points, label) for a rabbit's breed, or (None, "") when no sourced curve fits."""
    breed = (rabbit.breed or "").lower()
    if "new zealand" not in breed and "nz" not in breed.split():
        return None, ""
    if "californian" in breed or "cal" in breed.split():
        return NZ_X_CAL, CROSS_SOURCE
    return NZ, NZ_SOURCE


def expected(points, age_days):
    """Interpolated reference grams at an age, or None outside the measured range."""
    days = sorted(points)
    if not points or age_days < days[0] or age_days > days[-1]:
        return None
    for lo, hi in zip(days, days[1:]):
        if lo <= age_days <= hi:
            return points[lo] + (points[hi] - points[lo]) * (age_days - lo) / (hi - lo)
    return points[days[-1]]


def versus(points, age_days, grams):
    """Fraction above (+) or below (-) the curve, or None."""
    ref = expected(points, age_days) if points else None
    return None if not ref or not grams else (grams - ref) / ref
