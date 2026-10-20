// Single entry point for scripts/dev-local.sh up --tunnel.
//
// The phone reaches this computer through one public tunnel, so everything it needs is
// served from one port: the API (each service), the photos (local S3) and the Expo server
// (app bundle, assets and its WebSockets). Only Node's standard library is used.
//
//   node scripts/dev-proxy.mjs <port> <s3-port>

import http from "node:http";
import net from "node:net";

const [port = "8090", s3Port = "9100"] = process.argv.slice(2);

const ROUTES = [
  { prefix: "/api/v1/auth", port: 8001, api: true },
  { prefix: "/api/v1/lead", port: 8002, api: true },
  { prefix: "/api/v1/property", port: 8003, api: true },
  { prefix: "/property-media", port: Number(s3Port), api: false },
];
const EXPO_PORT = 8081;

function targetFor(url = "/") {
  const route = ROUTES.find((r) => url === r.prefix || url.startsWith(`${r.prefix}/`));
  // The API and S3 expect a local Host; the Expo server keeps the public one.
  return route
    ? { port: route.port, api: route.api, host: `localhost:${route.port}` }
    : { port: EXPO_PORT, api: false, host: null };
}

// The browser preview (localhost:8081) calls the API through the tunnel: allow it.
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, x-request-id",
};

const server = http.createServer((req, res) => {
  const target = targetFor(req.url);
  if (target.api && req.method === "OPTIONS") {
    res.writeHead(204, CORS);
    res.end();
    return;
  }
  const headers = { ...req.headers };
  if (target.host) headers.host = target.host;
  const upstream = http.request(
    { host: "127.0.0.1", port: target.port, path: req.url, method: req.method, headers },
    (answer) => {
      res.writeHead(answer.statusCode ?? 502, {
        ...answer.headers,
        ...(target.api ? CORS : {}),
      });
      answer.pipe(res);
    },
  );
  upstream.on("error", () => {
    if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
    res.end("Servizio non raggiungibile");
  });
  req.pipe(upstream);
});

// WebSockets (Expo's hot reload and dev tools) are passed through as raw TCP.
server.on("upgrade", (req, socket, head) => {
  const target = targetFor(req.url);
  const upstream = net.connect(target.port, "127.0.0.1", () => {
    const lines = [`${req.method} ${req.url} HTTP/${req.httpVersion}`];
    for (let i = 0; i < req.rawHeaders.length; i += 2) {
      lines.push(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}`);
    }
    upstream.write(`${lines.join("\r\n")}\r\n\r\n`);
    if (head.length) upstream.write(head);
    upstream.pipe(socket);
    socket.pipe(upstream);
  });
  upstream.on("error", () => socket.destroy());
  socket.on("error", () => upstream.destroy());
});

server.listen(Number(port), "127.0.0.1", () => {
  console.log(`dev proxy on http://127.0.0.1:${port}`);
});
