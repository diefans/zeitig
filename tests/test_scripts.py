def test_regex_type():
    from zeitig import scripts

    r = scripts.Regex()
    r.convert('.*', None, None)
