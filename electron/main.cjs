const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const https = require('https');
const querystring = require('querystring');

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
      preload: path.join(__dirname, 'preload.js')
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

// Helper function to perform HTTPS GET requests with stored cookies
function makeGetRequest(url) {
  return new Promise((resolve, reject) => {
    const options = {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookieString
      }
    };
    
    https.get(url, options, (res) => {
      let data = "";
      res.on("data", (chunk) => {
        data += chunk;
      });
      res.on("end", () => {
        resolve({
          statusCode: res.statusCode,
          data: data
        });
      });
    }).on("error", (err) => {
      reject(err);
    });
  });
}

// IPC Handlers
ipcMain.handle('login-ll', async (event, { username, password }) => {
  return new Promise((resolve) => {
    const postData = querystring.stringify({
      login: "Login",
      username: username,
      password: password
    });

    const options = {
      hostname: "www.learnedleague.com",
      port: 443,
      path: "/ucp.php?mode=login",
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": postData.length,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    };

    const req = https.request(options, (res) => {
      // Parse cookies
      const setCookies = res.headers["set-cookie"];
      if (setCookies) {
        // Collect cookienames and values
        const parsedCookies = setCookies.map(cookie => cookie.split(';')[0]);
        cookieString = parsedCookies.join('; ');
      }

      let data = "";
      res.on("data", (chunk) => {
        data += chunk;
      });

      res.on("end", async () => {
        // Logged in! Let us test by fetching the main page to see if we get user profile link (flag)
        try {
          const testRes = await makeGetRequest("https://www.learnedleague.com");
          const hasFlag = testRes.data.includes("class=\"flag\"");
          const hasIncorrect = testRes.data.includes("incorrect") || testRes.data.includes("Incorrect");
          
          if (hasFlag && !hasIncorrect) {
            // Find profile ID and username
            // Simple regex match: <a href="profiles.php?12345" ...
            const profileMatch = testRes.data.match(/profiles\.php\?(\d+)/);
            const profileId = profileMatch ? profileMatch[1] : "";
            
            resolve({
              success: true,
              profileId: profileId,
              username: username
            });
          } else {
            resolve({
              success: false,
              error: "Invalid username or password, or WAF/Cloudflare block."
            });
          }
        } catch (err) {
          resolve({ success: false, error: err.message });
        }
      });
    });

    req.on("error", (err) => {
      resolve({ success: false, error: err.message });
    });

    req.write(postData);
    req.end();
  });
});

ipcMain.handle('fetch-ll', async (event, url) => {
  try {
    const res = await makeGetRequest(url);
    return {
      success: res.statusCode === 200 || res.statusCode === 302,
      statusCode: res.statusCode,
      data: res.data
    };
  } catch (err) {
    return { success: false, error: err.message };
  }
});
