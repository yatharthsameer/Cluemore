#!/usr/bin/env node

// Auto-Update Diagnostic Tool for Cluemore
// This script helps debug why auto-updates aren't working

const { autoUpdater } = require('electron-updater');
const https = require('https');

console.log('🔍 Cluemore Auto-Update Diagnostic Tool\n');

// Configuration from package.json
const packageJson = require('../package.json');
const buildConfig = packageJson.build;

console.log('📋 Current Configuration:');
console.log(`   App Version: ${packageJson.version}`);
console.log(`   App ID: ${buildConfig.appId}`);
console.log(`   Publish Config:`, JSON.stringify(buildConfig.publish, null, 4));
console.log('');

// GitHub API check
async function checkGitHubRelease() {
  return new Promise((resolve, reject) => {
    const publishConfig = buildConfig.publish[0];
    const url = `https://api.github.com/repos/${publishConfig.owner}/${publishConfig.repo}/releases/latest`;
    
    console.log('🌐 Checking GitHub Release API...');
    console.log(`   API URL: ${url}`);
    
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Cluemore-Diagnostic-Tool',
        'Accept': 'application/vnd.github.v3+json'
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const release = JSON.parse(data);
          
          console.log('✅ GitHub API Response:');
          console.log(`   Latest Release: ${release.tag_name}`);
          console.log(`   Published: ${release.published_at}`);
          console.log(`   Draft: ${release.draft}`);
          console.log(`   Prerelease: ${release.prerelease}`);
          console.log(`   Assets Count: ${release.assets?.length || 0}`);
          
          if (release.assets && release.assets.length > 0) {
            console.log('   Assets:');
            release.assets.forEach(asset => {
              console.log(`     - ${asset.name} (${(asset.size / 1024 / 1024).toFixed(1)}MB)`);
            });
          }
          
          console.log('');
          
          // Version comparison
          const currentVersion = packageJson.version;
          const latestVersion = release.tag_name.replace('v', '');
          
          console.log('🔄 Version Analysis:');
          console.log(`   Current App Version: ${currentVersion}`);
          console.log(`   Latest Release Version: ${latestVersion}`);
          
          if (currentVersion === latestVersion) {
            console.log('   ❌ ISSUE: Versions are identical - no update available!');
            console.log('   💡 SOLUTION: Increment app version to test updates');
          } else if (currentVersion > latestVersion) {
            console.log('   ⚠️  ISSUE: App version is newer than latest release');
          } else {
            console.log('   ✅ Update should be available');
          }
          
          console.log('');
          
          // Check for required assets
          console.log('📦 Asset Analysis:');
          const requiredAssets = [
            'latest-mac.yml',
            '.dmg',
            '.zip'
          ];
          
          requiredAssets.forEach(assetType => {
            const found = release.assets?.some(asset => 
              asset.name.includes(assetType) || asset.name.endsWith(assetType)
            );
            console.log(`   ${found ? '✅' : '❌'} ${assetType}: ${found ? 'Found' : 'Missing'}`);
          });
          
          resolve(release);
        } catch (error) {
          console.error('❌ Failed to parse GitHub API response:', error.message);
          reject(error);
        }
      });
    });
    
    req.on('error', (error) => {
      console.error('❌ GitHub API request failed:', error.message);
      reject(error);
    });
  });
}

// Test electron-updater configuration
async function testElectronUpdater() {
  console.log('🔧 Testing electron-updater configuration...');
  
  try {
    // Configure logging
    autoUpdater.logger = console;
    autoUpdater.logger.transports.file.level = 'debug';
    
    console.log(`   Update Check URL: ${autoUpdater.getFeedURL()}`);
    console.log(`   Allow Prerelease: ${autoUpdater.allowPrerelease}`);
    console.log(`   Allow Downgrade: ${autoUpdater.allowDowngrade}`);
    
    // Add event listeners for testing
    autoUpdater.on('checking-for-update', () => {
      console.log('   ⏳ Checking for updates...');
    });
    
    autoUpdater.on('update-available', (info) => {
      console.log('   ✅ Update available:', info.version);
    });
    
    autoUpdater.on('update-not-available', (info) => {
      console.log('   ℹ️  No updates available:', info.version);
    });
    
    autoUpdater.on('error', (error) => {
      console.log('   ❌ Update error:', error.message);
    });
    
    // Check for updates
    console.log('   🔍 Performing update check...');
    const result = await autoUpdater.checkForUpdates();
    console.log('   ✅ Update check completed');
    
    return result;
  } catch (error) {
    console.error('   ❌ electron-updater test failed:', error.message);
    return null;
  }
}

// Main diagnostic function
async function runDiagnostics() {
  try {
    // Check GitHub release
    const release = await checkGitHubRelease();
    
    // Test electron-updater (only in production builds)
    if (process.env.NODE_ENV === 'production') {
      await testElectronUpdater();
    } else {
      console.log('⚠️  Skipping electron-updater test (not in production mode)');
      console.log('   To test: NODE_ENV=production node scripts/diagnose-autoupdate.js');
    }
    
    console.log('');
    console.log('📝 RECOMMENDATIONS:');
    
    const currentVersion = packageJson.version;
    const latestVersion = release.tag_name.replace('v', '');
    
    if (currentVersion === latestVersion) {
      console.log('1. 🔢 Increment version in package.json (e.g., 1.3.0 → 1.4.0)');
      console.log('2. 🏗️  Build and publish new release: npm run build-mac');
      console.log('3. 📝 Create GitHub release with the new version');
      console.log('4. 🔄 Test update with older version of the app');
    }
    
    console.log('5. ✅ Ensure app is properly signed for macOS auto-updates');
    console.log('6. 📦 Verify latest-mac.yml is included in release assets');
    console.log('7. 🧪 Test with: autoUpdater.checkForUpdatesAndNotify()');
    
    console.log('');
    console.log('🎯 Quick Test Commands:');
    console.log('   npm run build-mac        # Build new version');
    console.log('   ./scripts/build-production.sh  # Full production build');
    console.log('   node scripts/diagnose-autoupdate.js  # Run diagnostics');
    
  } catch (error) {
    console.error('❌ Diagnostic failed:', error.message);
    process.exit(1);
  }
}

// Run diagnostics
runDiagnostics().then(() => {
  console.log('\n✅ Diagnostic complete!');
}).catch((error) => {
  console.error('\n❌ Diagnostic failed:', error.message);
  process.exit(1);
}); 