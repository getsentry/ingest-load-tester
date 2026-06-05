import pathlib


FIXTURE_PATH = pathlib.Path(__file__).parent.parent.parent / "test-events"

DEFAULT_MINIDUMP = "test-events/minidump.dmp"


def minidump_generator(filename: str = DEFAULT_MINIDUMP, **kwargs):
    """
    minidump format is hard to synthesize, so we just use a single fixture which is read once at factory-build
    time and reused for every request, aka the returned closure yields the same bytes each call

    Args:
        filename: Path to the minidump fixture. May be absolute or relative to
            the test-events fixture directory.

    Returns:
        A function returning {"filename": str, "data": bytes}.
    """
    path = pathlib.Path(filename)
    if not path.is_absolute() and not path.exists():
        path = FIXTURE_PATH / path.name

    with open(path, "rb") as f:
        data = f.read()

    # Relay associates the attachment with the synthesized crash event by
    # filename; "minidump.dmp" keeps it recognizable in the UI.
    attachment_filename = path.name

    def inner():
        return {"filename": attachment_filename, "data": data}

    return inner
