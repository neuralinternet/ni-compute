import traceback
import bittensor as bt


def format_exception(exception):
    """
    Return serialized exception traceback.

    Suitable for passing errors over API.
    """
    return traceback.format_exception(exception)


def get_exception_class(exception):
    return exception.__class__.__name__


def make_error_response(
        message: str,
        # TODO: additional optional value, for cases when there's no exception and we want some context provided
        status: bool = False,
        exception: Exception | None = None
) -> dict[str, str | bool]:
    """
    Generate a nice rich error response dictionary.
    """

    bt.logging.info(message)

    response = {"status": status, "message": message}

    if exception is not None:
        cls = get_exception_class(exception)
        tb = format_exception(exception)

        bt.logging.debug(f"Caught exception {cls} and returning error")
        bt.logging.trace(tb)

        response["exception"] = cls
        response["traceback"] = tb
    else:
        bt.logging.debug("Exception instance not provided")
        response["exception"] = ""
        response["traceback"] = ""

    return response
