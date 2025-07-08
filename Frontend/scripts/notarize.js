require('dotenv').config();

const { notarize } = require('@electron/notarize');
const fs = require('fs');
const path = require('path');
const plist = require('plist');
const { execSync } = require('child_process');

// ───────── helpers ────────────────────────────────────────────────────────
const sleep = ms => new Promise(r => setTimeout(r, ms));

const readBundleId = appPath => {
    const info = fs.readFileSync(
        path.join(appPath, 'Contents', 'Info.plist'),
        'utf8'
    );
    return plist.parse(info).CFBundleIdentifier;
};

const buildAuthOpts = base => {
    if (process.env.NOTARIZE_KEYCHAIN_PROFILE) {
        console.log('🔐  Using Keychain profile auth');
        return { ...base, keychainProfile: process.env.NOTARIZE_KEYCHAIN_PROFILE };
    }
    if (
        process.env.APPLE_API_KEY &&
        process.env.APPLE_API_KEY_ID &&
        process.env.APPLE_API_ISSUER
    ) {
        console.log('🔐  Using API-key auth');
        return {
            ...base,
            appleApiKey: process.env.APPLE_API_KEY,
            appleApiKeyId: process.env.APPLE_API_KEY_ID,
            appleApiIssuer: process.env.APPLE_API_ISSUER,
        };
    }
    if (
        process.env.APPLE_ID &&
        process.env.APPLE_ID_PASSWORD &&
        process.env.APPLE_TEAM_ID
    ) {
        console.log('🔐  Using Apple-ID auth');
        return {
            ...base,
            appleId: process.env.APPLE_ID,
            appleIdPassword: process.env.APPLE_ID_PASSWORD,
            teamId: process.env.APPLE_TEAM_ID,
        };
    }
    throw new Error(
        'No Apple credentials set – define ONE of:\n' +
        '  NOTARIZE_KEYCHAIN_PROFILE\n' +
        '  (APPLE_API_KEY + APPLE_API_KEY_ID + APPLE_API_ISSUER)\n' +
        '  (APPLE_ID + APPLE_ID_PASSWORD + APPLE_TEAM_ID)'
    );
};

// ───────── stapling with retry ────────────────────────────────────────────
async function stapleWithRetry(appPath) {
    const maxTries = parseInt(process.env.STAPLE_ATTEMPTS || 30, 10); // ~15 min
    const delayMs = parseInt(process.env.STAPLE_DELAY_MS || 30000, 10);

    for (let i = 1; i <= maxTries; i++) {
        try {
            execSync(`xcrun stapler staple -q "${appPath}"`, { stdio: 'inherit' });
            console.log('📎  Stapling succeeded');
            return;
        } catch (e) {
            if (i === maxTries) throw e;
            console.log(`⏳  Ticket not yet on CDN – retry ${i}/${maxTries} in ${delayMs / 1000}s`);
            await sleep(delayMs);
        }
    }
}

// ───────── main export (Electron-builder hook) ────────────────────────────
module.exports = async function notarizeApp(ctx) {
    if (ctx && ctx.electronPlatformName !== 'darwin') return;          // mac only
    if (!process.env.CI && !process.env.NOTARIZE_APP) {                // opt-in
        console.log('⏭️  NOTARIZE_APP not set – skipping notarization');
        return;
    }

    // resolve .app path + bundle ID
    let appPath, bundleId;
    if (ctx) {
        const name = ctx.packager.appInfo.productFilename;
        appPath = path.join(ctx.appOutDir, `${name}.app`);
        bundleId = ctx.packager.appInfo.id;
    } else {                                    // stand-alone: node notarize.js <My.app>
        appPath = process.argv[2];
        if (!appPath || !appPath.endsWith('.app')) {
            console.error('Usage: node notarize.js <Your.app>');
            process.exit(1);
        }
        bundleId = readBundleId(appPath);
    }

    console.log('\n🍎  Notarization starting…');
    console.log(`   → ${appPath}`);
    console.log(`   → bundle id: ${bundleId}`);

    const opts = buildAuthOpts({
        tool: 'notarytool',
        appPath,
        appBundleId: bundleId,
        wait: true,     // wait until Apple says “Accepted”
        // no staple here – we’ll retry ourselves
    });

    try {
        await notarize(opts);
        console.log('✅  Notary service accepted – waiting for ticket propagation…');
        await stapleWithRetry(appPath);
        console.log('🎉  Notarization + stapling finished successfully');
    } catch (err) {
        console.error('❌  Notarization/stapling error:', err.message || err);
        if (process.env.CI) process.exit(1);
    }
};

// ───────── stand-alone wrapper ────────────────────────────────────────────
if (require.main === module) {
    module.exports().catch(e => {
        console.error(e);
        process.exit(1);
    });
}
