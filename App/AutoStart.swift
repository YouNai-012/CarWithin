import AVFoundation
import Foundation
import Network

/// 监听「车机蓝牙已连上」和「仪表 Wi-Fi 已就绪」，交给界面决定是否自动启动。
/// CarPlay 只允许一个会话，所以这里只报告状态，启动动作仍由界面统一执行。
final class AutoStartCoordinator {
    struct State: Equatable {
        /// 命中过滤条件的蓝牙音频设备名；nil 表示当前没有蓝牙音频输出。
        var bluetoothName: String?
        /// en0 的 IPv4 地址；nil 表示当前没有 Wi-Fi 地址。
        var wifiIPv4: String?
    }

    var onStateChanged: ((State) -> Void)?
    /// 每次采样都回调，用于按时间判断仪表 Wi-Fi 是否已断开。
    var onTick: (() -> Void)?

    /// 蓝牙名称过滤，留空表示任意蓝牙音频设备。写入后立即重新评估。
    var nameFilter: String {
        get {
            lock.lock(); defer { lock.unlock() }
            return filter
        }
        set {
            lock.lock(); filter = newValue; lock.unlock()
            queue.async { [weak self] in self?.evaluate() }
        }
    }

    private let queue = DispatchQueue(label: "CarWithin.autoStart")
    private let lock = NSLock()
    private var filter = ""
    private var monitor: NWPathMonitor?
    private var timer: DispatchSourceTimer?
    private var wifiIPv4: String?
    private var bluetoothName: String?
    private var lastPublished: State?

    deinit { stop() }

    func start() {
        stop()
        queue.async { [weak self] in self?.lastPublished = nil }
        let monitor = NWPathMonitor(requiredInterfaceType: .wifi)
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            self.queue.async {
                self.wifiIPv4 = path.status == .satisfied ? ReceiverConfiguration.wifiIPv4Address() : nil
                self.evaluate()
            }
        }
        monitor.start(queue: queue)
        self.monitor = monitor
        // 路由变动通知在音频会话未激活时不一定送达，2 秒轮询最稳。
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now(), repeating: 2, leeway: .milliseconds(300))
        timer.setEventHandler { [weak self] in self?.sample() }
        self.timer = timer
        timer.resume()
    }

    func stop() {
        monitor?.cancel(); monitor = nil
        timer?.cancel(); timer = nil
    }

    private func sample() {
        wifiIPv4 = ReceiverConfiguration.wifiIPv4Address()
        bluetoothName = Self.bluetoothAudioPort()
        evaluate()
        if let onTick { DispatchQueue.main.async(execute: onTick) }
    }

    private static func bluetoothAudioPort() -> String? {
        for port in AVAudioSession.sharedInstance().currentRoute.outputs {
            switch port.portType {
            case .bluetoothA2DP, .bluetoothHFP, .bluetoothLE:
                return port.portName
            default:
                continue
            }
        }
        return nil
    }

    private func evaluate() {
        var state = State(bluetoothName: nil, wifiIPv4: wifiIPv4)
        if let name = bluetoothName {
            lock.lock()
            let needle = filter.trimmingCharacters(in: .whitespacesAndNewlines)
            lock.unlock()
            if needle.isEmpty || name.localizedCaseInsensitiveContains(needle) {
                state.bluetoothName = name
            }
        }
        guard state != lastPublished else { return }
        lastPublished = state
        DispatchQueue.main.async { [weak self] in self?.onStateChanged?(state) }
    }
}
