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
  "Referer": "https://www.learnedleague.com/",
  "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
  "Sec-Ch-Ua-Mobile": "?0",
  "Sec-Ch-Ua-Platform": '"macOS"',
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "same-origin",
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

    loginWin.webContents.on('dom-ready', async () => {
      const url = loginWin.webContents.getURL();
      // If user successfully authenticated or routed to main dashboard
      if (url === "https://www.learnedleague.com/" || url === "https://www.learnedleague.com/index.php" || (!url.includes("login") && url.includes(".php"))) {
        try {
          const pageUrl = loginWin.webContents.getURL();
          const links = await loginWin.webContents.executeJavaScript(`
            Array.from(document.querySelectorAll('a')).map(a => ({ href: a.getAttribute('href'), text: a.textContent }))
          `);
          const profileLinks = links.filter(l => l.href && l.href.includes('profiles.php'));
          console.log("[Login Debug] Current URL:", pageUrl);
          console.log("[Login Debug] Profile Links found:", JSON.stringify(profileLinks));

          const profileId = await loginWin.webContents.executeJavaScript(`
            (function() {
              const link = document.querySelector('a[href*="profiles.php?"]');
              if (link) {
                const m = link.getAttribute('href').match(/profiles\\.php\\?(\\d+)/);
                return m ? m[1] : "";
              }
              return "";
            })()
          `);
          
          if (profileId) {
            let username = "LearnedLeaguer";
            try {
              const profileRes = await net.fetch(`https://www.learnedleague.com/profiles.php?${profileId}`, {
                session: session.defaultSession,
                credentials: 'include',
                headers: { ...DEFAULT_HEADERS }
              });
              const profileHtml = await profileRes.text();
              // Try several patterns to extract username robustly
              // Pattern 1: <span class="namecss">FahmyG</span>
              const m1 = profileHtml.match(/<[^>]+class="namecss"[^>]*>\s*([^<]+)\s*</);
              // Pattern 2: <h1>FahmyG</h1> or <h1 ...>FahmyG</h1>
              const m2 = profileHtml.match(/<h1[^>]*>\s*([^<]+)\s*<\/h1>/);
              // Pattern 3: <title>FahmyG - LearnedLeague</title>
              const m3 = profileHtml.match(/<title>([^-<]+)\s*-\s*LearnedLeague<\/title>/);
              const matched = m1 || m2 || m3;
              console.log("[Login Debug] Name patterns:", { m1: m1?.[1], m2: m2?.[1], m3: m3?.[1] });
              if (matched) {
                const candidate = matched[1].trim();
                if (candidate && candidate !== 'LearnedLeaguer') {
                  username = candidate;
                }
              }
            } catch (err) {
              console.error("Error fetching username from profile page:", err);
            }
            
            console.log("[Login Debug] Resolved profileId:", profileId, "username:", username);
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

ipcMain.handle('debug-allquestions', async (event, season) => {
  try {
    const allqUrl = `https://www.learnedleague.com/allquestions.php?${season}`;
    const matchUrl = `https://www.learnedleague.com/match.php?${season}&1`;
    const opts = { session: session.defaultSession, credentials: 'include', headers: { ...DEFAULT_HEADERS } };

    const [allqRes, matchRes] = await Promise.all([
      net.fetch(allqUrl, opts),
      net.fetch(matchUrl, opts)
    ]);

    const allqHtml = await allqRes.text();
    const matchHtml = await matchRes.text();

    const saveDir = path.join(__dirname, '..');
    require('fs').writeFileSync(path.join(saveDir, `allquestions_${season}.html`), allqHtml);
    require('fs').writeFileSync(path.join(saveDir, `matchday1_${season}.html`), matchHtml);

    return { success: true, path: saveDir };
  } catch (err) {
    return { success: false, error: err.message };
  }
});
