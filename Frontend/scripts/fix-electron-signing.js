const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * Complete Apple-compliant signing script for Electron apps
 * Based on: https://developer.apple.com/documentation/security/resolving-common-notarization-issues
 * Handles ALL signing since electron-builder signing is disabled
 */

async function fixElectronSigning(context) {
    const { electronPlatformName, appOutDir } = context;
    
    // Only fix macOS builds
    if (electronPlatformName !== 'darwin') {
        console.log('⏭️  Skipping Electron signing for non-macOS platform');
        return;
    }
    
    const appName = context.packager.appInfo.productFilename;
    const appPath = `${appOutDir}/${appName}.app`;
    // Use certificate hash instead of name for reliability
    const identity = "D69D40108386495771A68085E273426F348DF4D1";
    const entitlementsPath = path.join(__dirname, '../assets/entitlements.mac.plist');
    
    console.log('🔧 Complete Apple-compliant signing (electron-builder signing disabled)...');
    
    try {
        // Step 1: Sign all helper applications first
        const helperApps = [
            'Cluemore Helper.app',
            'Cluemore Helper (GPU).app',
            'Cluemore Helper (Plugin).app', 
            'Cluemore Helper (Renderer).app'
        ];
        
        for (const helperApp of helperApps) {
            const helperPath = `${appPath}/Contents/Frameworks/${helperApp}`;
            
            if (fs.existsSync(helperPath)) {
                console.log(`  📝 Signing ${helperApp}...`);
                
                const signHelperCmd = [
                    'codesign',
                    '--sign', identity,
                    '--force',
                    '--options', 'runtime',
                    '--entitlements', `"${entitlementsPath}"`,
                    '--timestamp',
                    '--verbose',
                    `"${helperPath}"`
                ].join(' ');
                
                execSync(signHelperCmd, { stdio: 'inherit' });
                console.log(`  ✅ Successfully signed ${helperApp}`);
            }
        }
        
        // Step 2: Sign native modules and libraries
        const findNativeModules = `find "${appPath}" -name "*.node" -o -name "*.dylib"`;
        const nativeModules = execSync(findNativeModules, { encoding: 'utf8' }).trim().split('\n').filter(Boolean);
        
        for (const module of nativeModules) {
            if (fs.existsSync(module)) {
                console.log(`  📝 Signing native module: ${path.basename(module)}...`);
                
                const signModuleCmd = [
                    'codesign',
                    '--sign', identity,
                    '--force',
                    '--options', 'runtime',
                    '--timestamp',
                    '--verbose',
                    `"${module}"`
                ].join(' ');
                
                execSync(signModuleCmd, { stdio: 'inherit' });
            }
        }
        
        // Step 3: Sign frameworks in the correct order (inside-out)
        const frameworks = [
            'Mantle.framework',
            'ReactiveObjC.framework', 
            'Squirrel.framework',
            'Electron Framework.framework'
        ];
        
        for (const framework of frameworks) {
            const frameworkPath = `${appPath}/Contents/Frameworks/${framework}`;
            
            if (fs.existsSync(frameworkPath)) {
                console.log(`  📝 Signing ${framework}...`);
                
                const signCmd = [
                    'codesign',
                    '--sign', identity,
                    '--force',
                    '--options', 'runtime',
                    '--entitlements', `"${entitlementsPath}"`,
                    '--timestamp',
                    '--verbose',
                    `"${frameworkPath}"`
                ].join(' ');
                
                execSync(signCmd, { stdio: 'inherit' });
                console.log(`  ✅ Successfully signed ${framework}`);
            }
        }
        
        // Step 4: Sign the main executable
        console.log('  📝 Signing main executable...');
        const mainExecutable = `${appPath}/Contents/MacOS/${appName}`;
        
        const signMainCmd = [
            'codesign',
            '--sign', identity,
            '--force', 
            '--options', 'runtime',
            '--entitlements', `"${entitlementsPath}"`,
            '--timestamp',
            '--verbose',
            `"${mainExecutable}"`
        ].join(' ');
        
        execSync(signMainCmd, { stdio: 'inherit' });
        console.log('  ✅ Successfully signed main executable');
        
        // Step 5: Sign the entire app bundle (final step)
        console.log('  📝 Signing app bundle...');
        const signAppCmd = [
            'codesign',
            '--sign', identity,
            '--force',
            '--options', 'runtime', 
            '--entitlements', `"${entitlementsPath}"`,
            '--timestamp',
            '--verbose',
            `"${appPath}"`
        ].join(' ');
        
        execSync(signAppCmd, { stdio: 'inherit' });
        console.log('  ✅ Successfully signed app bundle');
        
        // Step 6: Verify all signatures
        console.log('🔍 Verifying signatures...');
        execSync(`codesign --verify --deep --strict --verbose=2 "${appPath}"`, { stdio: 'inherit' });
        console.log('✅ All signatures verified successfully!');
        
    } catch (error) {
        console.error('❌ Complete signing failed:', error.message);
        throw error;
    }
}

module.exports = fixElectronSigning; 