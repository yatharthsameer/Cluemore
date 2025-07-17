#!/usr/bin/env node

// GitHub Release Checker for Cluemore Auto-Update
// This script checks GitHub releases without requiring Electron

const https = require('https');
const fs = require('fs');

console.log('🔍 Cluemore GitHub Release Checker\n');

// Configuration from package.json
const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
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
        'User-Agent': 'Cluemore-Release-Checker',
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
            console.log('   ❌ ISSUE FOUND: Versions are identical - no update available!');
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
            { name: 'latest-mac.yml', required: true },
            { name: '.dmg', required: true },
            { name: '.zip', required: false },
            { name: '.blockmap', required: false }
          ];
          
          let missingAssets = [];
          requiredAssets.forEach(assetType => {
            const found = release.assets?.some(asset => 
              asset.name.includes(assetType.name) || asset.name.endsWith(assetType.name)
            );
            const status = found ? '✅' : (assetType.required ? '❌' : '⚠️');
            console.log(`   ${status} ${assetType.name}: ${found ? 'Found' : 'Missing'}`);
            
            if (!found && assetType.required) {
              missingAssets.push(assetType.name);
            }
          });
          
          console.log('');
          console.log('📝 ANALYSIS RESULTS:');
          
          if (currentVersion === latestVersion) {
            console.log('🔍 PRIMARY ISSUE: Version mismatch');
            console.log('   Your app version and latest release are both v1.3.0');
            console.log('   Auto-updater only shows popup when a NEWER version is available');
            console.log('');
            console.log('✅ SOLUTION STEPS:');
            console.log('   1. Update package.json version to 1.4.0');
            console.log('   2. Keep one installed app at v1.3.0 for testing');
            console.log('   3. Build and publish v1.4.0 to GitHub releases');
            console.log('   4. Open the v1.3.0 app - it should show update popup');
          }
          
          if (missingAssets.length > 0) {
            console.log('🔍 SECONDARY ISSUE: Missing assets');
            console.log(`   Missing: ${missingAssets.join(', ')}`);
            console.log('   These are needed for electron-updater to work properly');
          }
          
          if (release.draft) {
            console.log('🔍 POTENTIAL ISSUE: Release is a draft');
            console.log('   Draft releases are not accessible to auto-updater');
            console.log('   Make sure to publish the release (not draft)');
          }
          
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

// Main function
async function main() {
  try {
    await checkGitHubRelease();
    
    console.log('');
    console.log('🎯 NEXT STEPS:');
    console.log('1. 📝 Update package.json version to 1.4.0');
    console.log('2. 🏗️  Build new version: npm run build-mac');
    console.log('3. 📤 Publish to GitHub releases');
    console.log('4. 🧪 Test with old version (should show popup)');
    console.log('5. 🔧 Use ./scripts/test-autoupdate.sh for easier testing');
    
  } catch (error) {
    console.error('❌ Check failed:', error.message);
    process.exit(1);
  }
}

main().then(() => {
  console.log('\n✅ Check complete!');
}).catch((error) => {
  console.error('\n❌ Check failed:', error.message);
  process.exit(1);
}); 