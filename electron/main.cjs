const { app, BrowserWindow, ipcMain, net, session } = require('electron');
const path = require('path');

let mainWindow;

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

const DEFAULT_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
  "Accept-Language": "en-US,en;q=0.9",
  "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
  "Sec-Ch-Ua-Mobile": "?0",
  "Sec-Ch-Ua-Platform": '"macOS"',
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none",
  "Sec-Fetch-User": "?1",
  "Upgrade-Insecure-Requests": "1"
};

// IPC Handlers
ipcMain.handle('open-login-window', async () => {
  return new Promise((resolve) => {
    const loginWin = new BrowserWindow({
      width: 550,
      height: 700,
      parent: mainWindow,
      modal: true,
      title: "LearnedLeague Login",
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true
      }
    });

    loginWin.loadURL("https://www.learnedleague.com/ucp.php?mode=login");

    loginWin.webContents.on('did-navigate', async (event, url) => {
      // If user successfully authenticated or routed to main dashboard
      if (url === "https://www.learnedleague.com/" || url === "https://www.learnedleague.com/index.php" || (!url.includes("login") && url.includes(".php"))) {
        try {
          const html = await loginWin.webContents.executeJavaScript("document.documentElement.innerHTML");
          const hasFlag = html.includes("class=\"flag\"");
          
          if (hasFlag) {
            const profileMatch = html.match(/profiles\.php\?(\d+)/);
            const profileId = profileMatch ? profileMatch[1] : "";
            
            const usernameMatch = html.match(/profiles\.php\?\d+">([^<]+)<\/a>/);
            const username = usernameMatch ? usernameMatch[1] : "LearnedLeaguer";
            
            resolve({
              success: true,
              profileId: profileId,
              username: username
            });
            loginWin.close();
          }
        } catch (e) {
          console.error("Popup scraping error:", e);
        }
      }
    });

    loginWin.on('closed', () => {
      resolve({ success: false, error: "Window closed by user." });
    });
  });
});

ipcMain.handle('login-ll', async (event, { username, password }) => {
  try {
    const postData = new URLSearchParams({
      login: "Login",
      username: username,
      password: password
    });

    // Use net.fetch which automatically manages cookies globally in the default Electron session
    const response = await net.fetch("https://www.learnedleague.com/ucp.php?mode=login", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        ...DEFAULT_HEADERS
      },
      body: postData.toString(),
      session: session.defaultSession,
      credentials: 'include'
    });

    // Verify login success by requesting home page (cookies are sent automatically by net.fetch)
    const verifyRes = await net.fetch("https://www.learnedleague.com", {
      headers: {
        ...DEFAULT_HEADERS
      },
      session: session.defaultSession,
      credentials: 'include'
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
        ...DEFAULT_HEADERS
      },
      session: session.defaultSession,
      credentials: 'include'
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

ipcMain.handle('run-luck-analysis', async (event, { season, matchday, usernames, rundle }) => {
  return new Promise((resolve) => {
    const csvUrl = `https://www.learnedleague.com/lgwide.php?${season}`;
    net.fetch(csvUrl, {
      headers: {
        ...DEFAULT_HEADERS
      },
      session: session.defaultSession,
      credentials: 'include'
    }).then(async (response) => {
      if (!response.ok) {
        resolve({ success: false, error: `Failed to download stats CSV (HTTP ${response.status})` });
        return;
      }
      const csvText = await response.text();
      
      const homeDir = require('os').homedir();
      const csvFolder = path.join(homeDir, '.LearnedLeague', 'league_wide_csvs');
      require('fs').mkdirSync(csvFolder, { recursive: true });
      const csvFile = path.join(csvFolder, `LL${season}_Leaguewide_MD_${matchday}.csv`);
      require('fs').writeFileSync(csvFile, csvText);
      
      const usernamesArg = usernames.join(' ');
      const rundleFlag = rundle ? '-r' : '';
      const cmd = `python3 luck_analysis.py -f "${csvFile}" ${rundleFlag} -u ${usernamesArg}`;
      
      const { exec } = require('child_process');
      exec(cmd, { cwd: path.join(__dirname, '..') }, (error, stdout, stderr) => {
        if (error) {
          resolve({ success: false, error: error.message + '\n' + stderr });
          return;
        }
        try {
          const res = JSON.parse(stdout);
          resolve(res);
        } catch (e) {
          resolve({ success: false, error: `Invalid JSON output: ${stdout}\nStderr: ${stderr}` });
        }
      });
    }).catch(err => {
      resolve({ success: false, error: err.message });
    });
  });
});
