from epub_binder_app.ui.helpers import natural_sort_key


def test_natural_sort_orders_part_prefix_before_volume_number():
    names = [
        "작품 2부 1권.epub",
        "작품 1부 11권.epub",
        "작품 1부 10권.epub",
    ]

    assert sorted(names, key=natural_sort_key) == [
        "작품 1부 10권.epub",
        "작품 1부 11권.epub",
        "작품 2부 1권.epub",
    ]


def test_natural_sort_orders_parenthesized_part_by_volume_number():
    names = [
        "너희들은 변호됐다 29권 (완결).epub",
        "너희들은 변호됐다 17권(2부).epub",
        "너희들은 변호됐다 8권.epub",
    ]

    assert sorted(names, key=natural_sort_key) == [
        "너희들은 변호됐다 8권.epub",
        "너희들은 변호됐다 17권(2부).epub",
        "너희들은 변호됐다 29권 (완결).epub",
    ]


def test_natural_sort_keeps_side_story_volume_with_series():
    names = [
        "홍등가의 소드마스터 17권 외전.epub",
        "홍등가의 소드마스터 16권 (완결).epub",
    ]

    assert sorted(names, key=natural_sort_key) == [
        "홍등가의 소드마스터 16권 (완결).epub",
        "홍등가의 소드마스터 17권 외전.epub",
    ]
