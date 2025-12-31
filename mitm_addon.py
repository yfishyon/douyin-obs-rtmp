from mitmproxy import http
import json
import urllib.parse

def response(flow: http.HTTPFlow):
    if "webcast/room/create" not in flow.request.pretty_url:
        return

    try:
        rtmp = flow.response.json()["data"]["stream_url"]["rtmp_push_url"]

        u = urllib.parse.urlparse(rtmp)
        qs = urllib.parse.parse_qs(u.query)
        qs["autoRepush"] = ["True"]
        query = urllib.parse.urlencode(qs, doseq=True)

        base, stream = u.path.rsplit("/", 1)

        server = f"{u.scheme}://{u.netloc}{base}"
        key = f"{stream}?{query}"

        print("RTMP_JSON=" + json.dumps({
            "server": server,
            "key": key
        }), flush=True)
    except:
        pass
