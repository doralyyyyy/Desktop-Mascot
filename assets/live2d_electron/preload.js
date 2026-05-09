const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopBridge", {
  pointerDown(point) {
    ipcRenderer.send("mascot-pointer-down", point);
  },
  pointerMove(point) {
    ipcRenderer.send("mascot-pointer-move", point);
  },
  pointerUp(point) {
    ipcRenderer.send("mascot-pointer-up", point);
  },
  contextMenu(point) {
    ipcRenderer.send("mascot-context-menu", point);
  },
  onAction(callback) {
    ipcRenderer.on("desktop-action", (_event, action) => callback(action));
  },
});
