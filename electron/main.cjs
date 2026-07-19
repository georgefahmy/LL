const { app, BrowserWindow, ipcMain, net } = require('electron');
const path = require('path');

let mainWindow;
let cookieString = ""; // Stores session cookies globally in memory

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: false
    },
    title: "LearnedLeague Practice Tool",
    backgroundColor: '#060814' // Dark theme matching Outfit design system
  });

  // Load built react bundle
  mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  
  // Optional: Open devtools for debugging if running in development mode
  // mainWindow.webContents.openDevTools();
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers
ipcMain.handle('login-ll', async (event, { username, password }) => {
  try {
    const postData = new URLSearchParams({
      login: "Login",
      username: username,
      password: password
    });

    // Use net.fetch which runs in Chromium net stack (bypassing TLS WAF blocks)
    // but executes in Main process (avoiding Renderer SameSite cookie limits)
    const response = await net.fetch("https://www.learnedleague.com/ucp.php?mode=login", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      },
      body: postData.toString(),
      redirect: "manual"
    });

    // Extract cookie headers
    const setCookies = response.headers.get("set-cookie");
    if (setCookies) {
      // Parse out the primary cookies
      const cookies = setCookies.split(',').map(c => c.split(';')[0].trim());
      cookieString = cookies.join('; ');
    }

    // Verify login success by requesting home page
    const verifyRes = await net.fetch("https://www.learnedleague.com", {
      headers: {
        "Cookie": cookieString,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    });

    const html = await verifyRes.text();
    const hasFlag = html.includes("class=\"flag\"");
    const hasIncorrect = html.includes("incorrect") || html.includes("Incorrect");

    if (hasFlag && !hasIncorrect) {
      const profileMatch = html.match(/profiles\.php\?(\d+)/);
      const profileId = profileMatch ? profileMatch[1] : "";
      return {
        success: true,
        profileId: profileId,
        username: username
      };
    } else {
      return {
        success: false,
        error: "Invalid username/password, or security challenge."
      };
    }
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle('fetch-ll', async (event, url) => {
  try {
    const response = await net.fetch(url, {
      headers: {
        "Cookie": cookieString,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    });
    if (!response.ok) {
      return { success: false, error: `HTTP ${response.status}` };
    }
    const data = await response.text();
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message };
  }
});
