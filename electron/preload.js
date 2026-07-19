const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  loginToLL: (username, password) => ipcRenderer.invoke('login-ll', { username, password }),
  fetchLL: (url) => ipcRenderer.invoke('fetch-ll', url)
});
