from contextlib import contextmanager

@contextmanager
def setup(tmp, root, config):
    yield config.replace('source = "selections/', 'source = "' + root.as_posix() + '/selections/')


def check(effect):
    assert effect["status"] == "QUALIFIED" and len(effect["sha256"]) == 64
