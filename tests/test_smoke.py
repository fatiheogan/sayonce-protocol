import sayonce
from sayonce.messages import Intent, MessageType


def test_version():
    assert sayonce.__version__ == "0.1.0"


def test_enums():
    assert MessageType.HELLO == 1
    assert Intent.REQUEST == 1
