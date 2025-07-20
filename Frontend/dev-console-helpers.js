// Development Console Helpers for Cluemore
// Use these functions in the browser's developer tools console

// Content Protection Toggle Functions
window.dev = {
    // Toggle content protection on/off
    async toggleContentProtection(enabled) {
        if (enabled === undefined) {
            // Get current status
            const status = await window.electronAPI.getContentProtectionStatus();
            console.log(`🔒 Current content protection status: ${status.enabled ? 'ENABLED (invisible to screen sharing)' : 'DISABLED (visible to screen sharing)'}`);
            console.log('💡 Usage: dev.toggleContentProtection(false) to make visible, dev.toggleContentProtection(true) to make invisible');
            return status;
        }

        try {
            const result = await window.electronAPI.toggleContentProtection(enabled);
            if (result.success) {
                console.log(`✅ Content protection ${enabled ? 'ENABLED' : 'DISABLED'}`);
                console.log(`📱 App is now ${enabled ? 'INVISIBLE' : 'VISIBLE'} to screen sharing applications`);
            } else {
                console.error('❌ Failed to toggle content protection:', result.error);
            }
            return result;
        } catch (error) {
            console.error('❌ Error toggling content protection:', error);
        }
    },

    // Quick shortcuts
    async makeVisible() {
        console.log('📱 Making app visible to screen sharing...');
        return await this.toggleContentProtection(false);
    },

    async makeInvisible() {
        console.log('🔒 Making app invisible to screen sharing...');
        return await this.toggleContentProtection(true);
    },

    // Status check
    async status() {
        const protection = await window.electronAPI.getContentProtectionStatus();
        const pin = await window.electronAPI.getPinStatus();
        
        console.log('📊 Cluemore Development Status:');
        console.log(`   🔒 Content Protection: ${protection.enabled ? 'ENABLED (invisible)' : 'DISABLED (visible)'}`);
        console.log(`   📌 Always On Top: ${pin.pinned ? 'ENABLED' : 'DISABLED'}`);
        console.log('');
        console.log('💡 Quick commands:');
        console.log('   dev.makeVisible()   - Make app visible to screen sharing');
        console.log('   dev.makeInvisible() - Make app invisible to screen sharing');
        console.log('   dev.status()        - Show current status');
        
        return { protection, pin };
    },

    // Help
    help() {
        console.log('🔧 Cluemore Development Console Helper');
        console.log('');
        console.log('📱 Content Protection Commands:');
        console.log('   dev.toggleContentProtection()     - Show current status');
        console.log('   dev.toggleContentProtection(false) - Make VISIBLE to screen sharing');
        console.log('   dev.toggleContentProtection(true)  - Make INVISIBLE to screen sharing');
        console.log('   dev.makeVisible()                  - Quick: make visible');
        console.log('   dev.makeInvisible()                - Quick: make invisible');
        console.log('   dev.status()                       - Show all current settings');
        console.log('');
        console.log('💡 Tip: Content protection prevents screen recording/sharing apps from capturing your window.');
        console.log('   Enable it (invisible) for security, disable it (visible) for development screenshots.');
    }
};

// Auto-setup on load
if (window.electronAPI) {
    console.log('🔧 Cluemore Development Console Helpers Loaded!');
    console.log('💡 Type "dev.help()" for available commands');
    console.log('📱 Type "dev.status()" to see current settings');
    
    // Set up content protection change listener
    window.electronAPI.onContentProtectionChanged((data) => {
        console.log(`🔒 Content protection changed: ${data.enabled ? 'ENABLED' : 'DISABLED'}`);
        console.log(`📱 ${data.message}`);
    });
} else {
    console.log('⚠️ Electron API not available - make sure you\'re running in the Electron app');
} 