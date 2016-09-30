

def test_block_function(testdir):
    testdir.makepyfile("""
        import pytest
        def test_block():
            pytest.block("test")
    """)

    res = testdir.runpytest()
    res.stdout.fnmatch_lines([
        "* 1 blocked *",
    ])


def test_block_mark(testdir):
    testdir.makepyfile("""
        import pytest
        @pytest.mark.block
        def test_block():
            pass
    """)

    res = testdir.runpytest()
    res.stdout.fnmatch_lines([
        "* 1 blocked *",
    ])


def test_blockif_mark(testdir):
    testdir.makepyfile("""
        import pytest
        @pytest.mark.blockif(True, reason="yay")
        def test_block():
            pass
    """)

    res = testdir.runpytest()
    res.stdout.fnmatch_lines([
        "* 1 blocked *",
    ])
