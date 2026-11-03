import pytest
from conftest import assert_test_database

class FakeConn:
    def __init__(self, name):
        self.name = name
    def execute(self, sql):
        assert sql == "select current_database()"
        return self
    def fetchone(self):
        return (self.name,)

def test_refuses_non_test_database():
    with pytest.raises(RuntimeError, match="postgres"):
        assert_test_database(FakeConn("postgres"))

def test_accepts_test_database():
    assert_test_database(FakeConn("collegedata_test"))
