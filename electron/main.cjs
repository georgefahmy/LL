const { app, BrowserWindow, ipcMain, net, session } = require('electron');
const path = require('path');

// Fix $PATH inside packaged macOS GUI app to match terminal shell environment
if (process.platform === 'darwin') {
  try {
    const { execSync } = require('child_process');
    const stdout = execSync('/bin/zsh -l -c "echo \\$PATH"', { encoding: 'utf8' });
    if (stdout.trim()) {
      process.env.PATH = stdout.trim();
    }
  } catch (err) {
    console.error('Failed to get shell PATH:', err);
    // Fallback if zsh call fails
    process.env.PATH = `/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.14/bin:${process.env.PATH}`;
  }
}

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    icon: path.join(__dirname, '../build/icon.png'),
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
  try {
    const csvUrl = `https://www.learnedleague.com/lgwide.php?${season}`;
    const response = await net.fetch(csvUrl, {
      headers: { ...DEFAULT_HEADERS },
      session: session.defaultSession,
      credentials: 'include'
    });
    if (!response.ok) {
      return { success: false, error: `Failed to download stats CSV (HTTP ${response.status})` };
    }
    const csvText = await response.text();
    
    // Save CSV locally as cache
    const homeDir = require('os').homedir();
    const csvFolder = path.join(homeDir, '.LearnedLeague', 'league_wide_csvs');
    require('fs').mkdirSync(csvFolder, { recursive: true });
    const csvFile = path.join(csvFolder, `LL${season}_Leaguewide_MD_${matchday}.csv`);
    require('fs').writeFileSync(csvFile, csvText);
    
    // Run the JS luck analysis algorithm
    const result = calculateLuckJS(csvText, usernames, rundle);
    return { success: true, data: result };
  } catch (err) {
    return { success: false, error: err.message };
  }
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

// Pure JavaScript re-implementation of the LL Luck Analysis OLS algorithm
function parseCSV(text) {
  const lines = [];
  let row = [""];
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const next = text[i+1];
    if (char === '"') {
      if (inQuotes && next === '"') {
        row[row.length - 1] += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      row.push("");
    } else if ((char === '\r' || char === '\n') && !inQuotes) {
      if (char === '\r' && next === '\n') {
        i++;
      }
      lines.push(row);
      row = [""];
    } else {
      row[row.length - 1] += char;
    }
  }
  if (row.length > 1 || row[0] !== "") {
    lines.push(row);
  }
  
  const headers = lines[0].map(h => h.trim());
  return lines.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, idx) => {
      obj[h] = row[idx] || "";
    });
    return obj;
  });
}

function solveLinearSystem(A, B) {
  const n = B.length;
  const M = [];
  for (let i = 0; i < n; i++) {
    M.push([...A[i], B[i]]);
  }
  
  for (let i = 0; i < n; i++) {
    let maxRow = i;
    for (let k = i + 1; k < n; k++) {
      if (Math.abs(M[k][i]) > Math.abs(M[maxRow][i])) {
        maxRow = k;
      }
    }
    const temp = M[i];
    M[i] = M[maxRow];
    M[maxRow] = temp;
    
    if (Math.abs(M[i][i]) < 1e-12) {
      M[i][i] = 1e-12;
    }
    
    for (let k = i + 1; k < n; k++) {
      const factor = M[k][i] / M[i][i];
      for (let j = i; j <= n; j++) {
        M[k][j] -= factor * M[i][j];
      }
    }
  }
  
  const x = new Array(n).fill(0);
  for (let i = n - 1; i >= 0; i--) {
    let sum = M[i][n];
    for (let j = i + 1; j < n; j++) {
      sum -= M[i][j] * x[j];
    }
    x[i] = sum / M[i][i];
  }
  return x;
}

function calculateLuckJS(csvText, usernames, rundleFlag) {
  const rows = parseCSV(csvText);
  if (rows.length === 0) {
    throw new Error("CSV file is empty");
  }
  
  const parseNum = (val) => {
    if (val === "" || val === "--" || val === null || val === undefined) return 0;
    const n = parseFloat(val);
    return isNaN(n) ? 0 : n;
  };
  
  const data = rows.map(r => {
    const W = parseNum(r["Wins"]);
    const L = parseNum(r["Losses"]);
    const T = parseNum(r["Ties"]);
    const PTS = parseNum(r["Pts"]);
    const Rank = parseNum(r["Rundle Rank"]);
    const OE = parseNum(r["OE"]);
    const DE = parseNum(r["DE"]);
    const QPct = parseNum(r["QPct"]);
    const CAA = parseNum(r["CAA"]);
    const FL = parseNum(r["FL"]);
    const MPD = parseNum(r["MPD"]);
    const TCA = parseNum(r["TCA"]);
    const FW = parseNum(r["FW"]);
    const Rundle = r["Rundle"] || "";
    const Player = r["Player"] || "";
    
    const Matches = W + L + T;
    const Played = Matches - FL;
    
    return {
      Player, Rundle, W, L, T, PTS, Rank, OE, DE, QPct, CAA, FL, MPD, TCA, FW, Matches, Played
    };
  }).filter(r => r.Player !== "");
  
  const rundleGroups = {};
  data.forEach(r => {
    if (!rundleGroups[r.Rundle]) {
      rundleGroups[r.Rundle] = [];
    }
    rundleGroups[r.Rundle].push(r);
  });
  
  const rundleQPctMean = {};
  Object.keys(rundleGroups).forEach(rundle => {
    const list = rundleGroups[rundle];
    const sum = list.reduce((acc, curr) => acc + curr.QPct, 0);
    rundleQPctMean[rundle] = sum / list.length;
  });
  
  data.forEach(r => {
    const meanQPct = rundleQPctMean[r.Rundle] || 1;
    const denom = 6 * (r.Matches - r.FW) * meanQPct;
    r.SOS = denom !== 0 ? r.CAA / denom : 0;
  });
  
  const normalizeVars = ["OE", "DE", "QPct", "CAA", "FL", "MPD", "TCA", "SOS"];
  
  Object.keys(rundleGroups).forEach(rundle => {
    const list = rundleGroups[rundle];
    const n = list.length;
    
    normalizeVars.forEach(varName => {
      const sum = list.reduce((acc, curr) => acc + curr[varName], 0);
      const mean = sum / n;
      const sqDiffSum = list.reduce((acc, curr) => acc + Math.pow(curr[varName] - mean, 2), 0);
      const std = n > 1 ? Math.sqrt(sqDiffSum / (n - 1)) : 0;
      
      list.forEach(r => {
        r[`norm_${varName}`] = std !== 0 ? (r[varName] - mean) / std : (r[varName] - mean);
      });
    });
  });
  
  const N = data.length;
  const numPredictors = 7;
  const X = [];
  const y = [];
  
  data.forEach(r => {
    const row = [
      r.Played,
      r.norm_OE,
      r.FL,
      r.norm_OE * r.FL,
      r.norm_QPct,
      r.norm_QPct * r.FL,
      r.norm_DE
    ];
    X.push(row);
    y.push(r.PTS);
  });
  
  const XtX = Array.from({ length: numPredictors }, () => new Array(numPredictors).fill(0));
  const Xty = new Array(numPredictors).fill(0);
  
  for (let i = 0; i < N; i++) {
    const rowX = X[i];
    const valY = y[i];
    for (let r = 0; r < numPredictors; r++) {
      for (let c = 0; c < numPredictors; c++) {
        XtX[r][c] += rowX[r] * rowX[c];
      }
      Xty[r] += rowX[r] * valY;
    }
  }
  
  const beta = solveLinearSystem(XtX, Xty);
  
  data.forEach((r, idx) => {
    const rowX = X[idx];
    let expPts = 0;
    for (let j = 0; j < numPredictors; j++) {
      expPts += rowX[j] * beta[j];
    }
    r.Exp_PTS = expPts;
    r.Luck = r.PTS - r.Exp_PTS;
  });
  
  const rundlePlayerCount = {};
  Object.keys(rundleGroups).forEach(rundle => {
    rundlePlayerCount[rundle] = rundleGroups[rundle].length;
  });
  
  const rundleNames = Object.keys(rundleGroups);
  const rundleSizesSum = rundleNames.reduce((acc, curr) => acc + rundlePlayerCount[curr], 0);
  const meanRundleSize = rundleNames.length > 0 ? rundleSizesSum / rundleNames.length : 0;
  
  Object.keys(rundleGroups).forEach(rundle => {
    const list = rundleGroups[rundle];
    list.sort((a, b) => b.Exp_PTS - a.Exp_PTS);
    
    let rank = 1;
    for (let i = 0; i < list.length; i++) {
      if (i > 0 && list[i].Exp_PTS < list[i-1].Exp_PTS) {
        rank++;
      }
      list[i].Exp_Rank = rank;
      list[i].Player_count = rundlePlayerCount[rundle];
      list[i].Luck_Rank = list[i].Exp_Rank - list[i].Rank;
      list[i].Luck_Rank_adj = (list[i].Luck_Rank / list[i].Player_count) * meanRundleSize;
    }
  });
  
  const sortedByLuckRankAdj = [...data].sort((a, b) => a.Luck_Rank_adj - b.Luck_Rank_adj);
  
  for (let i = 0; i < sortedByLuckRankAdj.length; i++) {
    let maxIdx = i;
    while (maxIdx + 1 < sortedByLuckRankAdj.length && sortedByLuckRankAdj[maxIdx + 1].Luck_Rank_adj === sortedByLuckRankAdj[i].Luck_Rank_adj) {
      maxIdx++;
    }
    const rank = maxIdx + 1;
    for (let k = i; k <= maxIdx; k++) {
      sortedByLuckRankAdj[k].max_rank = rank;
    }
    i = maxIdx;
  }
  
  data.forEach(r => {
    r.LuckPctile = (r.max_rank / N) * 100;
  });
  
  data.sort((a, b) => b.LuckPctile - a.LuckPctile);
  
  const fields = [
    "Player", "W", "L", "T", "QPct", "TCA", "CAA", 
    "PTS", "Exp_PTS", "Luck", "LuckPctile", "Rank", "Exp_Rank", "Rundle"
  ];
  
  let resultData = data;
  if (rundleFlag && usernames && usernames.length > 0) {
    const userRundles = new Set();
    const usernamesSet = new Set(usernames);
    data.forEach(r => {
      if (usernamesSet.has(r.Player)) {
        userRundles.add(r.Rundle);
      }
    });
    resultData = data.filter(r => userRundles.has(r.Rundle));
  } else if (usernames && usernames.length > 0) {
    const usernamesSet = new Set(usernames);
    resultData = data.filter(r => usernamesSet.has(r.Player));
  }
  
  return resultData.map(r => {
    const obj = {};
    fields.forEach(f => {
      const val = r[f];
      if (f === "LuckPctile") {
        obj[f] = parseFloat(val.toFixed(2));
      } else if (typeof val === "number" && !Number.isInteger(val)) {
        obj[f] = parseFloat(val.toFixed(3));
      } else {
        obj[f] = val;
      }
    });
    return obj;
  });
}
