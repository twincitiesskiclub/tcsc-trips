from app.conditions.wax import recommend_wax, WaxBand


def test_cold_below_14():
    band = recommend_wax(temp_f=5)
    assert band == WaxBand.GREEN
    assert recommend_wax(temp_f=13).label.startswith('Green')


def test_blue_14_to_28():
    assert recommend_wax(temp_f=14) == WaxBand.BLUE
    assert recommend_wax(temp_f=20) == WaxBand.BLUE
    assert recommend_wax(temp_f=27) == WaxBand.BLUE


def test_purple_28_to_32():
    assert recommend_wax(temp_f=28) == WaxBand.PURPLE
    assert recommend_wax(temp_f=31) == WaxBand.PURPLE


def test_red_above_32():
    assert recommend_wax(temp_f=32) == WaxBand.RED
    assert recommend_wax(temp_f=45) == WaxBand.RED


def test_label_is_descriptive():
    assert recommend_wax(20).label == 'Blue wax · firm snow'
