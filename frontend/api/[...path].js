// frontend/api/[...path].js
// Vercel Serverless Function: proxy /api/* -> https://cyclegraph-api.fly.dev/api/*
// Viktig: forward cookies og Set-Cookie slik at auth fungerer.

module.exports = async (req, res) => {
  try {
    const parts = Array.isArray(req.query.path) ? req.query.path : [];
    const qsIndex = req.url.indexOf("?");
    const qs = qsIndex >= 0 ? req.url.slice(qsIndex) : "";

    const target = `https://cyclegraph-api.fly.dev/api/${parts.join("/")}${qs}`;

    // Kopier headers, men fjern hop-by-hop headers
    const headers = { ...req.headers };
    delete headers.host;
    delete headers.connection;
    delete headers["content-length"];

    // Body: Vercel gir ofte req.body som object/string/buffer avhengig av content-type
    let body = undefined;
    if (req.method !== "GET" && req.method !== "HEAD") {
      if (Buffer.isBuffer(req.body)) body = req.body;
      else if (typeof req.body === "string") body = req.body;
      else if (req.body != null) {
        body = JSON.stringify(req.body);
        headers["content-type"] = headers["content-type"] || "application/json";
      }
    }

    const r = await fetch(target, {
      method: req.method,
      headers,
      body,
      redirect: "manual",
    });

    // Forward status
    res.statusCode = r.status;

    // Forward headers (inkl Set-Cookie)
    r.headers.forEach((v, k) => {
      // Unngå å sette noen “problemheaders” dobbelt
      if (k.toLowerCase() === "content-encoding") return;
      res.setHeader(k, v);
    });

    const buf = Buffer.from(await r.arrayBuffer());
    res.end(buf);
  } catch (e) {
    res.statusCode = 502;
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ ok: false, error: String(e) }));
  }
};
