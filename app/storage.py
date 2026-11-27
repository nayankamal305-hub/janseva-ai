"""Photo storage behind one interface. Local disk by default; S3-compatible object storage (Neon Object Storage, R2, MinIO ...)
when S3_BUCKET + S3_ENDPOINT + S3_ACCESS_KEY_ID + S3_SECRET_ACCESS_KEY are set. Stdlib only (hand-written SigV4, path-style URLs).
The DB keeps the same '/uploads/<name>' value either way, so old rows keep working."""
import datetime as dt, hashlib, hmac, os, re, urllib.error, urllib.parse, urllib.request

def _h(k, m): return hmac.new(k, m.encode(), hashlib.sha256).digest()

def sigv4_headers(method, url, headers, payload, access, secret, region, service="s3", now=None):
    """Return headers incl. Authorization (AWS Signature V4). `headers` must already include Host."""
    t = now or dt.datetime.now(dt.timezone.utc)
    amz, day = t.strftime("%Y%m%dT%H%M%SZ"), t.strftime("%Y%m%d")
    u = urllib.parse.urlsplit(url)
    hs = {k.lower(): str(v).strip() for k, v in headers.items()}
    hs["x-amz-date"] = amz
    if service == "s3": hs["x-amz-content-sha256"] = hashlib.sha256(payload).hexdigest()
    names = sorted(hs)
    canon_q = "&".join("%s=%s" % (urllib.parse.quote(k, safe="-_.~"), urllib.parse.quote(v, safe="-_.~")) for k, v in sorted(urllib.parse.parse_qsl(u.query, keep_blank_values=True)))
    canon = "\n".join([method, urllib.parse.quote(urllib.parse.unquote(u.path) or "/", safe="/-_.~"), canon_q,
                       "".join("%s:%s\n" % (n, hs[n]) for n in names), ";".join(names), hashlib.sha256(payload).hexdigest()])
    scope = "%s/%s/%s/aws4_request" % (day, region, service)
    sts = "AWS4-HMAC-SHA256\n%s\n%s\n%s" % (amz, scope, hashlib.sha256(canon.encode()).hexdigest())
    k = _h(_h(_h(_h(("AWS4" + secret).encode(), day), region), service), "aws4_request")
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    out = dict(headers); out["x-amz-date"] = amz
    if service == "s3": out["x-amz-content-sha256"] = hs["x-amz-content-sha256"]
    out["Authorization"] = "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (access, scope, ";".join(names), sig)
    return out

_NAME = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_CT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}

class LocalStorage:
    kind = "local"
    def __init__(self, root): self.root = root; os.makedirs(root, exist_ok=True)
    def put(self, name, data, ctype=None):
        if not _NAME.match(name): raise ValueError("bad name")
        with open(os.path.join(self.root, name), "wb") as f: f.write(data)
    def get(self, name):
        if not _NAME.match(os.path.basename(name)): return None
        f = os.path.join(self.root, os.path.basename(name))
        if not os.path.isfile(f): return None
        return open(f, "rb").read(), _CT.get(f.rsplit(".", 1)[-1], "application/octet-stream")

class S3Storage:
    kind = "s3"
    def __init__(self, endpoint, bucket, access, secret, region="auto", prefix="uploads/"):
        self.endpoint, self.bucket, self.access, self.secret, self.region, self.prefix = endpoint.rstrip("/"), bucket, access, secret, region, prefix
    def _url(self, name): return "%s/%s/%s%s" % (self.endpoint, self.bucket, self.prefix, urllib.parse.quote(name))
    def _req(self, method, name, data=b"", ctype=None):
        url = self._url(name)
        h = {"Host": urllib.parse.urlsplit(url).netloc}
        if ctype: h["Content-Type"] = ctype
        h = sigv4_headers(method, url, h, data, self.access, self.secret, self.region)
        return urllib.request.urlopen(urllib.request.Request(url, data=data if method == "PUT" else None, headers=h, method=method), timeout=20)
    def put(self, name, data, ctype=None):
        if not _NAME.match(name): raise ValueError("bad name")
        self._req("PUT", name, data, ctype or "application/octet-stream").read()
    def get(self, name):
        name = os.path.basename(name)
        if not _NAME.match(name): return None
        try:
            r = self._req("GET", name); return r.read(), _CT.get(name.rsplit(".", 1)[-1], "application/octet-stream")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            raise

def from_env(env, local_root):
    need = ("S3_ENDPOINT", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
    if all(env.get(k) for k in need):
        return S3Storage(env["S3_ENDPOINT"], env["S3_BUCKET"], env["S3_ACCESS_KEY_ID"], env["S3_SECRET_ACCESS_KEY"], env.get("S3_REGION", "auto"), env.get("S3_PREFIX", "uploads/"))
    return LocalStorage(local_root)
