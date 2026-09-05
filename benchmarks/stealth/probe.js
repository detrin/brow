async () => {
    const attempt = (fn, dflt = null) => {
        try {
            const v = fn();
            return v === undefined ? dflt : v;
        } catch (e) {
            return dflt;
        }
    };

    const webgl = attempt(() => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (!ctx) return null;
        const dbg = ctx.getExtension('WEBGL_debug_renderer_info');
        if (!dbg) return null;
        return {
            vendor: ctx.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
            renderer: ctx.getParameter(dbg.UNMASKED_RENDERER_WEBGL),
        };
    });

    // Notification.permission is 'denied' by default only under headless Chrome, while
    // permissions.query() still answers 'prompt'. The pair disagreeing is the tell, not either alone.
    let permissionState = null;
    try {
        permissionState = (await navigator.permissions.query({ name: 'notifications' })).state;
    } catch (e) {
        permissionState = 'error';
    }

    const localIps = await new Promise((resolve) => {
        let pc;
        try {
            pc = new RTCPeerConnection({ iceServers: [] });
        } catch (e) {
            return resolve(null);
        }
        const found = new Set();
        const done = () => {
            try { pc.close(); } catch (e) {}
            resolve([...found]);
        };
        setTimeout(done, 1200);
        pc.onicecandidate = (e) => {
            if (!e.candidate) return done();
            const m = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]*:[a-f0-9:]+)/i.exec(e.candidate.candidate);
            if (m) found.add(m[1]);
        };
        try {
            pc.createDataChannel('x');
            pc.createOffer().then((o) => pc.setLocalDescription(o)).catch(done);
        } catch (e) {
            done();
        }
    });

    return {
        webdriver: navigator.webdriver === true,
        automationKeys: Object.keys(window).filter((k) => /^(cdc_|\$cdc|__playwright|__pw|__puppeteer|__driver|__selenium|__nightmare)/i.test(k)),
        documentAutomationKeys: attempt(() => Object.keys(document).filter((k) => /^(cdc_|\$cdc)/i.test(k)), []),
        hasChromeObject: !!window.chrome,
        hasChromeRuntime: attempt(() => !!(window.chrome && window.chrome.runtime), false),
        plugins: attempt(() => navigator.plugins.length, 0),
        mimeTypes: attempt(() => navigator.mimeTypes.length, 0),
        pdfViewerEnabled: attempt(() => navigator.pdfViewerEnabled, null),
        userAgent: navigator.userAgent,
        headlessInUserAgent: /headless/i.test(navigator.userAgent),
        vendor: navigator.vendor,
        platform: navigator.platform,
        languages: attempt(() => [...navigator.languages], []),
        language: navigator.language,
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: attempt(() => navigator.deviceMemory, null),
        maxTouchPoints: navigator.maxTouchPoints,
        userAgentData: attempt(() => {
            const d = navigator.userAgentData;
            return d ? { brands: d.brands.map((b) => b.brand), mobile: d.mobile, platform: d.platform } : null;
        }),
        webgl,
        timezone: attempt(() => Intl.DateTimeFormat().resolvedOptions().timeZone),
        locale: attempt(() => Intl.DateTimeFormat().resolvedOptions().locale),
        screen: {
            width: screen.width,
            height: screen.height,
            availWidth: screen.availWidth,
            availHeight: screen.availHeight,
            colorDepth: screen.colorDepth,
        },
        window: { outerWidth: window.outerWidth, outerHeight: window.outerHeight, devicePixelRatio: window.devicePixelRatio },
        notificationPermission: attempt(() => Notification.permission),
        permissionQueryState: permissionState,
        nativeToString: attempt(() => /\[native code\]/.test(Function.prototype.toString.call(navigator.permissions.query)), null),
        stackMentionsDriver: attempt(() => /puppeteer|playwright|patchright|selenium/i.test(new Error().stack || ''), null),
        webRtcLocalIps: localIps,
    };
}
