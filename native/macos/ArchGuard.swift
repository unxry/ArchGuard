import AppKit
import WebKit
import UniformTypeIdentifiers
import Darwin

final class ArchGuardApp: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var overlay: NSView!
    var message: NSTextField!
    var detail: NSTextField!
    var retry: NSButton!
    var backend: Process?
    var lifeline: Pipe?
    var output: Pipe?
    var origin: URL?
    var generation = 0
    var quitting = false
    var lockFD: Int32 = -1
    var signals: [DispatchSourceSignal] = []
    var deadline: DispatchWorkItem?
    var preferenceTimer: Timer?
    let preferenceKeys = ["locale", "motion", "scene-quality", "edge-flow", "flow-speed"]
    let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("ArchGuard", isDirectory: true)

    var resources: URL { Bundle.main.resourceURL! }
    var projects: URL {
        if let saved = UserDefaults.standard.string(forKey: "ProjectsRoot") {
            return URL(fileURLWithPath: saved, isDirectory: true)
        }
        return resources.appendingPathComponent("Examples", isDirectory: true)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            try FileManager.default.createDirectory(at: support, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        } catch { NSApp.terminate(nil); return }
        lockFD = open(support.appendingPathComponent("desktop.lock").path, O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard lockFD >= 0, flock(lockFD, LOCK_EX | LOCK_NB) == 0 else {
            for app in NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier!) where app.processIdentifier != getpid() {
                app.activate(options: [.activateAllWindows])
            }
            NSApp.terminate(nil)
            return
        }
        makeMenu()
        makeWindow()
        for number in [SIGTERM, SIGINT] {
            signal(number, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: number, queue: .main)
            source.setEventHandler { NSApp.terminate(nil) }
            source.resume()
            signals.append(source)
        }
        startBackend()
    }

    func makeMenu() {
        let menu = NSMenu()
        let appItem = NSMenuItem(); menu.addItem(appItem)
        let appMenu = NSMenu(); appItem.submenu = appMenu
        appMenu.addItem(withTitle: "About ArchGuard", action: #selector(about), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit ArchGuard", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let fileItem = NSMenuItem(); menu.addItem(fileItem)
        let file = NSMenu(title: "File"); fileItem.submenu = file
        file.addItem(withTitle: "Choose Projects Folder… / Папка проектов…", action: #selector(chooseProjects), keyEquivalent: "o")
        file.addItem(withTitle: "Use Included Example / Встроенный пример", action: #selector(useExample), keyEquivalent: "")
        file.addItem(.separator())
        file.addItem(withTitle: "Restart Local Engine / Перезапустить", action: #selector(restart), keyEquivalent: "r")
        let editItem = NSMenuItem(); menu.addItem(editItem)
        let edit = NSMenu(title: "Edit"); editItem.submenu = edit
        for (title, action, key) in [("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Cut", "cut:", "x"), ("Select All", "selectAll:", "a")] {
            edit.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        let windowItem = NSMenuItem(); menu.addItem(windowItem)
        let windowMenu = NSMenu(title: "Window"); windowItem.submenu = windowMenu
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.miniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Enter Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        NSApp.mainMenu = menu; NSApp.windowsMenu = windowMenu
    }

    func makeWindow() {
        let frame = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: min(1440, frame.width - 40), height: min(920, frame.height - 40)), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "ArchGuard · Cinematic Observatory"
        window.minSize = NSSize(width: 1100, height: 720)
        window.backgroundColor = NSColor(calibratedRed: 0.11, green: 0.13, blue: 0.16, alpha: 1)
        window.appearance = NSAppearance(named: .darkAqua)
        window.setFrameAutosaveName("ArchGuard.Main")
        window.isReleasedWhenClosed = false
        let config = WKWebViewConfiguration()
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        // No script message handlers or privileged JavaScript bridge.
        web = WKWebView(frame: window.contentView!.bounds, configuration: config)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self; web.uiDelegate = self
        window.contentView!.addSubview(web)
        overlay = NSView(frame: window.contentView!.bounds)
        overlay.autoresizingMask = [.width, .height]
        overlay.wantsLayer = true; overlay.layer?.backgroundColor = window.backgroundColor.cgColor
        window.contentView!.addSubview(overlay)
        let brand = NSTextField(labelWithString: "ARCHGUARD  /  NATIVE OBSERVATORY")
        brand.textColor = NSColor(calibratedRed: 0.91, green: 0.73, blue: 0.5, alpha: 1)
        brand.font = .systemFont(ofSize: 13, weight: .semibold)
        message = NSTextField(labelWithString: "Preparing your workspace")
        message.font = .systemFont(ofSize: 32, weight: .medium); message.textColor = .white
        detail = NSTextField(wrappingLabelWithString: "Запускаем локальный движок. Ваш код остаётся на этом Mac.")
        detail.textColor = .secondaryLabelColor; detail.alignment = .center
        retry = NSButton(title: "Retry / Повторить", target: self, action: #selector(restart))
        retry.bezelStyle = .rounded; retry.isHidden = true
        let folder = NSButton(title: "Choose Projects Folder… / Папка проектов…", target: self, action: #selector(chooseProjects))
        folder.bezelStyle = .rounded
        let stack = NSStackView(views: [brand, message, detail, retry, folder])
        stack.orientation = .vertical; stack.alignment = .centerX; stack.spacing = 24
        stack.translatesAutoresizingMaskIntoConstraints = false; overlay.addSubview(stack)
        NSLayoutConstraint.activate([stack.centerXAnchor.constraint(equalTo: overlay.centerXAnchor), stack.centerYAnchor.constraint(equalTo: overlay.centerYAnchor), stack.widthAnchor.constraint(lessThanOrEqualToConstant: 760)])
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }

    func diagnostic(_ code: String) {
        let text = "\(ISO8601DateFormatter().string(from: Date())) \(code)\n"
        // Bounded latest-event log: no source paths, session tokens or raw exceptions.
        try? text.write(to: support.appendingPathComponent("startup.log"), atomically: true, encoding: .utf8)
    }

    func loading() {
        overlay.isHidden = false; retry.isHidden = true
        message.stringValue = "Preparing your workspace"
        detail.stringValue = "Запускаем локальный движок. Ваш код остаётся на этом Mac."
    }

    func fail(_ code: String) {
        deadline?.cancel(); origin = nil; web.stopLoading()
        overlay.isHidden = false; retry.isHidden = false
        message.stringValue = "Workspace could not start"
        detail.stringValue = "\(code) · Повторите запуск или выберите доступную папку проектов."
        diagnostic(code)
    }

    func startBackend() {
        guard !quitting else { return }
        generation += 1; let current = generation
        loading(); origin = nil
        let python = resources.appendingPathComponent("python/bin/python3.13")
        guard FileManager.default.isExecutableFile(atPath: python.path) else { fail("RUNTIME_MISSING"); return }
        let child = Process(); let input = Pipe(); let stdout = Pipe()
        child.executableURL = python
        child.arguments = ["-I", "-B", "-m", "archguard.product.desktop", "--projects-root", projects.path, "--state-dir", support.appendingPathComponent("Results").path, "--sessions-dir", support.appendingPathComponent("Runtime").path]
        child.environment = ["PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "HOME": support.path, "TMPDIR": NSTemporaryDirectory()]
        child.currentDirectoryURL = resources
        child.standardInput = input; child.standardOutput = stdout; child.standardError = FileHandle.nullDevice
        backend = child; lifeline = input; output = stdout
        var pending = Data()
        stdout.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { handle.readabilityHandler = nil; return }
            pending.append(data)
            if pending.count > 4096 { handle.readabilityHandler = nil; return }
            while let end = pending.firstIndex(of: 10) {
                let line = pending.prefix(upTo: end); pending.removeSubrange(...end)
                guard let object = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { continue }
                DispatchQueue.main.async {
                    guard let self = self, self.generation == current, !self.quitting else { return }
                    if object["ready"] as? Bool == true, let port = object["port"] as? Int, (1024...65535).contains(port) {
                        self.ready(port, generation: current)
                    } else if object["error"] != nil { self.fail("BACKEND_START_FAILED") }
                }
            }
        }
        child.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self, self.generation == current, !self.quitting else { return }
                self.lifeline?.fileHandleForWriting.closeFile()
                self.fail("BACKEND_EXITED")
            }
        }
        do { try child.run() } catch { fail("RUNTIME_LAUNCH_FAILED"); return }
        let timeout = DispatchWorkItem { [weak self] in
            guard let self = self, self.generation == current else { return }
            self.stopBackend { self.fail("STARTUP_TIMEOUT") }
        }
        deadline = timeout; DispatchQueue.main.asyncAfter(deadline: .now() + 30, execute: timeout)
        diagnostic("BACKEND_STARTING")
    }

    func ready(_ port: Int, generation current: Int) {
        guard origin == nil else { return }
        let url = URL(string: "http://127.0.0.1:\(port)/")!
        var request = URLRequest(url: url.appendingPathComponent("health")); request.timeoutInterval = 3
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            DispatchQueue.main.async {
                guard let self = self, self.generation == current, !self.quitting else { return }
                guard (response as? HTTPURLResponse)?.statusCode == 200, let data = data,
                    (try? JSONSerialization.jsonObject(with: data) as? [String: String])?["status"] == "ok" else {
                    self.stopBackend { self.fail("READINESS_FAILED") }; return
                }
                self.origin = url; self.seedPreferences(); self.web.load(URLRequest(url: url))
            }
        }.resume()
    }

    func stopBackend(_ completion: @escaping () -> Void) {
        deadline?.cancel(); preferenceTimer?.invalidate(); generation += 1; origin = nil
        output?.fileHandleForReading.readabilityHandler = nil
        lifeline?.fileHandleForWriting.closeFile()
        guard let child = backend else { completion(); return }
        child.terminationHandler = nil; backend = nil
        let started = Date()
        func wait() {
            if !child.isRunning { completion(); return }
            if Date().timeIntervalSince(started) > 5 { kill(child.processIdentifier, SIGKILL) }
            else if Date().timeIntervalSince(started) > 3 { child.terminate() }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.05, execute: wait)
        }
        wait()
    }

    @objc func restart() { loading(); savePreferences { self.stopBackend { self.startBackend() } } }

    @objc func chooseProjects() {
        let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.message = "Choose a folder containing only projects you intend to analyze. / Выберите родительскую папку проектов."
        panel.beginSheetModal(for: window) { response in
            guard response == .OK, let url = panel.url else { return }
            UserDefaults.standard.set(url.resolvingSymlinksInPath().path, forKey: "ProjectsRoot")
            self.restart()
        }
    }

    @objc func useExample() { UserDefaults.standard.removeObject(forKey: "ProjectsRoot"); restart() }
    @objc func about() {
        NSApp.orderFrontStandardAboutPanel(options: [.applicationName: "ArchGuard", .applicationVersion: "0.1.0 · Desktop 041", .credits: NSAttributedString(string: "Local architecture observatory\nPython engine · Native WKWebView\nLocal ad-hoc build · not notarized")])
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil); return true
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard backend != nil else { return .terminateNow }
        if quitting { return .terminateLater }
        quitting = true; savePreferences { self.stopBackend { NSApp.reply(toApplicationShouldTerminate: true) } }
        return .terminateLater
    }

    func allowed(_ url: URL) -> Bool {
        guard let origin = origin else { return false }
        return url.scheme == "http" && url.host == "127.0.0.1" && url.port == origin.port && url.user == nil && url.password == nil
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if action.shouldPerformDownload, url.scheme == "blob", action.sourceFrame.isMainFrame,
           action.sourceFrame.request.url.map(allowed) == true {
            decisionHandler(.download); return
        }
        if allowed(url), action.targetFrame?.isMainFrame == true { decisionHandler(.allow); return }
        decisionHandler(.cancel)
        if action.navigationType == .linkActivated, url.scheme == "https", url.host != nil, url.user == nil, url.password == nil {
            let alert = NSAlert(); alert.messageText = "Open external link? / Открыть внешнюю ссылку?"
            alert.informativeText = url.host!; alert.addButton(withTitle: "Open / Открыть"); alert.addButton(withTitle: "Cancel / Отмена")
            alert.beginSheetModal(for: window) { answer in if answer == .alertFirstButtonReturn { NSWorkspace.shared.open(url) } }
        }
    }
    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(response.response.url.map(allowed) == true ? .allow : .cancel)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard webView.url.map(allowed) == true else { return }
        deadline?.cancel(); overlay.isHidden = true; diagnostic("READY")
        preferenceTimer?.invalidate()
        preferenceTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.savePreferences() }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { fail("WEBVIEW_LOAD_FAILED") }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { fail("WEBVIEW_EXITED") }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        guard frame.request.url.map(allowed) == true else { completionHandler(nil); return }
        let panel = NSOpenPanel(); panel.allowedContentTypes = [.json]; panel.allowsMultipleSelection = false
        panel.beginSheetModal(for: window) { response in completionHandler(response == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel(); panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = URL(fileURLWithPath: suggestedFilename).lastPathComponent
        panel.beginSheetModal(for: window) { answer in completionHandler(answer == .OK ? panel.url : nil) }
    }

    func seedPreferences() {
        let saved = UserDefaults.standard.dictionary(forKey: "CinematicPreferences") as? [String: String] ?? [:]
        let safe = saved.filter { preferenceKeys.contains($0.key) && $0.value.count <= 20 }
        let json = String(data: try! JSONSerialization.data(withJSONObject: safe), encoding: .utf8)!
        web.configuration.userContentController.removeAllUserScripts()
        let script = "if(location.hostname==='127.0.0.1'){for(const [k,v] of Object.entries(\(json))){localStorage.setItem('ag-cinematic-v3-'+k,v)}}"
        web.configuration.userContentController.addUserScript(WKUserScript(source: script, injectionTime: .atDocumentStart, forMainFrameOnly: true))
    }

    func savePreferences(_ completion: (() -> Void)? = nil) {
        guard web.url.map(allowed) == true else { completion?(); return }
        let keys = String(data: try! JSONSerialization.data(withJSONObject: preferenceKeys), encoding: .utf8)!
        web.evaluateJavaScript("Object.fromEntries(\(keys).map(k=>[k,localStorage.getItem('ag-cinematic-v3-'+k)]).filter(p=>p[1]!==null))") { result, _ in
            defer { completion?() }
            guard let values = result as? [String: String] else { return }
            let safe = values.filter { self.preferenceKeys.contains($0.key) && $0.value.count <= 20 }
            UserDefaults.standard.set(safe, forKey: "CinematicPreferences")
        }
    }
}

let app = NSApplication.shared
let delegate = ArchGuardApp()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
