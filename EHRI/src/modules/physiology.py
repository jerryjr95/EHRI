def deviation(current, baseline):
    if baseline == 0:
        return 0
    return abs(current - baseline) / baseline


def physiology_score(hr, spo2, rr,
                     base_hr=75,
                     base_spo2=98,
                     base_rr=16):

    hr_dev = deviation(hr, base_hr)
    spo2_dev = deviation(spo2, base_spo2)
    rr_dev = deviation(rr, base_rr)

    total = (hr_dev * 0.3) + (spo2_dev * 0.5) + (rr_dev * 0.2)

    score = min(10, max(1, total * 20))

    return round(score, 2)