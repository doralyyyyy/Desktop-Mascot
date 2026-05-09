const { app, BrowserWindow, ipcMain, screen } = require("electron");
const fs = require("fs");
const http = require("http");
const path = require("path");
const { URL } = require("url");

const args = parseArgs(process.argv.slice(2));
const callbackUrl = process.env.LIVE2D_CALLBACK_URL || args["callback-url"];
const controlPort = Number(process.env.LIVE2D_CONTROL_PORT || args["control-port"] || 0);
const assetsDir = process.env.LIVE2D_ASSETS_DIR || args["assets-dir"];
const width = Number(process.env.LIVE2D_WIDTH || args.width || 380);
const height = Number(process.env.LIVE2D_HEIGHT || args.height || 460);
const logPath = process.env.LIVE2D_LOG_PATH || args["log-path"];

if (logPath) {
  try {
    fs.writeFileSync(logPath, `[${new Date().toISOString()}] Live2D Electron entry loaded\n`, "utf8");
  } catch (_error) {
    // Ignore early logging failures.
  }
}

let win = null;
let controlServer = null;
let assetServer = null;
let assetBaseUrl = null;
let pressPoint = null;
let pressBounds = null;
let dragging = false;

function normalizePoint(point) {
  return {
    x: Number.isFinite(Number(point?.x)) ? Math.round(Number(point.x)) : 0,
    y: Number.isFinite(Number(point?.y)) ? Math.round(Number(point.y)) : 0,
  };
}

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  if (logPath) {
    try {
      fs.appendFileSync(logPath, line, "utf8");
    } catch (_error) {
      // Ignore logging failures; they should not affect the mascot window.
    }
  }
  console.log(message);
}

function parseArgs(argv) {
  const parsed = {};
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith("--")) {
      continue;
    }
    const key = item.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      parsed[key] = "1";
      continue;
    }
    parsed[key] = next;
    i += 1;
  }
  return parsed;
}

function sendEvent(type, x = 0, y = 0) {
  if (!callbackUrl) {
    return;
  }
  const url = new URL(callbackUrl);
  url.searchParams.set("type", type);
  url.searchParams.set("x", String(Math.round(x)));
  url.searchParams.set("y", String(Math.round(y)));
  http.get(url, (res) => res.resume()).on("error", () => {});
}

function createControlServer() {
  if (!controlPort) {
    return;
  }
  controlServer = http.createServer((req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${controlPort}`);
    if (url.pathname !== "/control") {
      res.writeHead(404);
      res.end();
      return;
    }
    const action = url.searchParams.get("action");
    if (action === "tap") {
      win?.webContents.send("desktop-action", "tap");
    } else if (action === "idle") {
      win?.webContents.send("desktop-action", "idle");
    }
    res.writeHead(204);
    res.end();
  });
  controlServer.listen(controlPort, "127.0.0.1", () => {
    log(`Control server listening on ${controlPort}`);
  });
}

function contentTypeFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".html") return "text/html; charset=utf-8";
  if (ext === ".js") return "application/javascript; charset=utf-8";
  if (ext === ".json") return "application/json; charset=utf-8";
  if (ext === ".png") return "image/png";
  if (ext === ".moc3") return "application/octet-stream";
  return "application/octet-stream";
}

function createAssetServer() {
  assetServer = http.createServer((req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    const decodedPath = decodeURIComponent(url.pathname).replace(/^\/+/, "");
    const filePath = path.normalize(path.join(assetsDir, decodedPath));
    const assetRoot = path.normalize(assetsDir);
    if (!filePath.startsWith(assetRoot)) {
      res.writeHead(403);
      res.end();
      return;
    }
    fs.readFile(filePath, (error, data) => {
      if (error) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, {
        "Content-Type": contentTypeFor(filePath),
        "Cache-Control": "no-store",
      });
      res.end(data);
    });
  });

  return new Promise((resolve) => {
    assetServer.listen(0, "127.0.0.1", () => {
      const address = assetServer.address();
      assetBaseUrl = `http://127.0.0.1:${address.port}`;
      log(`Asset server listening at ${assetBaseUrl}`);
      resolve();
    });
  });
}

function createWindow() {
  if (!assetsDir) {
    throw new Error("LIVE2D_ASSETS_DIR is required");
  }
  log(`Creating transparent window ${width}x${height}`);
  const area = screen.getPrimaryDisplay().workArea;
  win = new BrowserWindow({
    width,
    height,
    x: Math.max(area.x, area.x + area.width - width - 140),
    y: Math.max(area.y, area.y + area.height - height - 60),
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    hasShadow: false,
    resizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });
  win.setMenu(null);
  win.setAlwaysOnTop(true, "screen-saver");

  ipcMain.on("mascot-pointer-down", (_event, point) => {
    pressPoint = normalizePoint(point);
    pressBounds = win.getBounds();
    dragging = false;
    log(`Pointer down ${JSON.stringify(pressPoint)} bounds=${JSON.stringify(pressBounds)}`);
  });

  ipcMain.on("mascot-pointer-move", (_event, point) => {
    if (!pressPoint || !pressBounds) {
      return;
    }
    const current = normalizePoint(point);
    const dx = current.x - pressPoint.x;
    const dy = current.y - pressPoint.y;
    if (Math.abs(dx) + Math.abs(dy) < 18) {
      return;
    }

    dragging = true;
    const area = screen.getPrimaryDisplay().workArea;
    const width = Math.round(pressBounds.width);
    const height = Math.round(pressBounds.height);
    const nextBounds = {
      x: Math.min(Math.max(area.x - width + 80, Math.round(pressBounds.x + dx)), area.x + area.width - 80),
      y: Math.min(Math.max(area.y - height + 80, Math.round(pressBounds.y + dy)), area.y + area.height - 80),
      width,
      height,
    };
    try {
      win.setBounds(nextBounds);
    } catch (error) {
      log(`setBounds failed ${JSON.stringify(nextBounds)}: ${error.stack || error.message || error}`);
    }
  });

  ipcMain.on("mascot-pointer-up", (_event, point) => {
    const current = normalizePoint(point);
    log(`Pointer up ${JSON.stringify(current)} dragging=${dragging}`);
    pressPoint = null;
    pressBounds = null;
    dragging = false;
  });

  ipcMain.on("mascot-context-menu", (_event, point) => {
    const current = normalizePoint(point);
    log(`Context menu ${JSON.stringify(current)}`);
    sendEvent("contextmenu", current.x, current.y);
  });

  win.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    log(`Live2D renderer[${level}] ${sourceId}:${line}: ${message}`);
  });
  win.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    log(`Live2D load failed ${errorCode}: ${errorDescription} ${validatedURL}`);
  });
  win.webContents.on("render-process-gone", (_event, details) => {
    log(`Live2D render process gone: ${JSON.stringify(details)}`);
  });
  win.webContents.on("did-finish-load", () => {
    log("Live2D page finished load");
    sendEvent("ready");
  });

  const pageUrl = `${assetBaseUrl}/live2d_runtime/index.html?model=${encodeURIComponent("/live2d/model/model.model3.json")}`;
  log(`Live2D loading ${pageUrl}`);
  win.loadURL(pageUrl);
  win.on("closed", () => {
    log("Live2D window closed");
    sendEvent("quit");
  });
}

app.whenReady().then(async () => {
  log("Electron app ready");
  createControlServer();
  await createAssetServer();
  createWindow();
});

app.on("window-all-closed", () => {
  log("Electron window-all-closed");
  if (controlServer) {
    controlServer.close();
  }
  if (assetServer) {
    assetServer.close();
  }
  app.quit();
});

app.on("before-quit", () => log("Electron before-quit"));
app.on("render-process-gone", (_event, webContents, details) => {
  log(`App render-process-gone ${webContents.id}: ${JSON.stringify(details)}`);
});
process.on("uncaughtException", (error) => {
  log(`Uncaught exception: ${error.stack || error.message || error}`);
});
process.on("unhandledRejection", (error) => {
  log(`Unhandled rejection: ${error && error.stack ? error.stack : error}`);
});
