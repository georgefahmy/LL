const fs = require('fs');
const path = require('path');
const { downloadArtifact } = require('@electron/get');
const extract = require('extract-zip');
const { version } = require('./node_modules/electron/package.json');

async function install() {
  try {
    console.log('Version:', version);
    const zipPath = await downloadArtifact({
      version,
      artifactName: 'electron',
      platform: 'darwin',
      arch: 'arm64'
    });
    console.log('Zip Path:', zipPath);
    const dist = path.resolve('node_modules/electron/dist');
    console.log('Extracting to:', dist);
    
    // Clean old files if any
    if (fs.existsSync(dist)) {
      fs.rmSync(dist, { recursive: true, force: true });
    }
    fs.mkdirSync(dist, { recursive: true });

    await extract(zipPath, { dir: dist });
    console.log('Extraction complete!');
    
    fs.writeFileSync(path.resolve('node_modules/electron/path.txt'), 'Electron.app/Contents/MacOS/Electron');
    console.log('Path.txt written successfully!');
  } catch (err) {
    console.error('Installation failed:', err);
  }
}

install();
