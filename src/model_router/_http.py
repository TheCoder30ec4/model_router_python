import json
import urllib.error
import urllib.request

from .errors import RouterError


def request_json(url, api_key=None, body=None, timeout=60):
    """GET (body is None) or POST JSON; raises RouterError on HTTP/network failure."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        raise RouterError(f"{url} -> HTTP {e.code}: {e.read().decode(errors='replace')[:500]}") from e
    except urllib.error.URLError as e:
        raise RouterError(f"{url} -> {e.reason}") from e
    except TimeoutError as e:
        raise RouterError(f"{url} -> timed out after {timeout}s") from e
    except OSError as e:
        raise RouterError(f"{url} -> {e}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise RouterError(f"{url} -> response was not valid JSON: {e}") from e
    if not isinstance(res, dict):
        raise RouterError(f"{url} -> expected a JSON object, got {type(res).__name__}")
    return res
