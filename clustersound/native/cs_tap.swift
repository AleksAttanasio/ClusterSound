// cs-tap: records what macOS sends to an output device, through a Core Audio process tap (macOS 14.2+).
//
//   cs-tap list                                  JSON array of output devices
//   cs-tap record --device <uid|all> [--exclude-pid <pid>]
//
// record writes one JSON header line to stdout ({"sample_rate", "channels"}), then interleaved float32 PCM,
// until SIGTERM/SIGINT or stdin closes. Errors go to stderr as one JSON line: {"error", "code"}.
// Nothing is decrypted or bypassed: the tap receives the same audio the device plays.
import CoreAudio
import Foundation

func fail(_ message: String, _ code: OSStatus = 0) -> Never {
    let obj: [String: Any] = ["error": message, "code": Int(code)]
    if let data = try? JSONSerialization.data(withJSONObject: obj) {
        FileHandle.standardError.write(data + Data("\n".utf8))
    }
    exit(1)
}

func check(_ status: OSStatus, _ what: String) {
    if status != noErr { fail("\(what) (OSStatus \(status))", status) }
}

// ------------------------------------------------------------------ properties
func address(_ selector: AudioObjectPropertySelector,
             _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
}

func getValue<T>(_ obj: AudioObjectID, _ selector: AudioObjectPropertySelector, _ initial: T,
                 scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal) -> T? {
    var addr = address(selector, scope)
    var value = initial
    var size = UInt32(MemoryLayout<T>.size)
    let status = withUnsafeMutablePointer(to: &value) { AudioObjectGetPropertyData(obj, &addr, 0, nil, &size, $0) }
    return status == noErr ? value : nil
}

func getString(_ obj: AudioObjectID, _ selector: AudioObjectPropertySelector) -> String? {
    var addr = address(selector)
    var value: Unmanaged<CFString>?
    var size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
    let status = AudioObjectGetPropertyData(obj, &addr, 0, nil, &size, &value)
    guard status == noErr, let v = value else { return nil }
    return v.takeRetainedValue() as String
}

func allDevices() -> [AudioObjectID] {
    var addr = address(kAudioHardwarePropertyDevices)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size) == noErr else { return [] }
    var ids = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids) == noErr else { return [] }
    return ids
}

func outputChannels(_ dev: AudioObjectID) -> Int {
    var addr = address(kAudioDevicePropertyStreamConfiguration, kAudioObjectPropertyScopeOutput)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(dev, &addr, 0, nil, &size) == noErr, size > 0 else { return 0 }
    let raw = UnsafeMutableRawPointer.allocate(byteCount: Int(size), alignment: MemoryLayout<AudioBufferList>.alignment)
    defer { raw.deallocate() }
    guard AudioObjectGetPropertyData(dev, &addr, 0, nil, &size, raw) == noErr else { return 0 }
    let list = UnsafeMutableAudioBufferListPointer(raw.assumingMemoryBound(to: AudioBufferList.self))
    return list.reduce(0) { $0 + Int($1.mNumberChannels) }
}

func defaultOutput() -> AudioObjectID? {
    getValue(AudioObjectID(kAudioObjectSystemObject), kAudioHardwarePropertyDefaultOutputDevice, AudioObjectID(0))
}

func deviceByUID(_ uid: String) -> AudioObjectID? {
    allDevices().first { getString($0, kAudioDevicePropertyDeviceUID) == uid }
}

func processObject(pid: pid_t) -> AudioObjectID? {
    var addr = address(kAudioHardwarePropertyTranslatePIDToProcessObject)
    var pidIn = pid
    var obj = AudioObjectID(0)
    var size = UInt32(MemoryLayout<AudioObjectID>.size)
    let status = AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr,
                                            UInt32(MemoryLayout<pid_t>.size), &pidIn, &size, &obj)
    return status == noErr && obj != 0 ? obj : nil
}

// ------------------------------------------------------------------ list
func listDevices() {
    let def = defaultOutput()
    var out: [[String: Any]] = []
    for dev in allDevices() {
        let ch = outputChannels(dev)
        guard ch > 0, let uid = getString(dev, kAudioDevicePropertyDeviceUID) else { continue }
        let transport: UInt32 = getValue(dev, kAudioDevicePropertyTransportType, UInt32(0)) ?? 0
        if transport == kAudioDeviceTransportTypeAggregate && uid.hasPrefix("cs-tap-") { continue }
        out.append([
            "uid": uid,
            "name": getString(dev, kAudioObjectPropertyName) ?? uid,
            "channels": ch,
            "sample_rate": getValue(dev, kAudioDevicePropertyNominalSampleRate, Float64(0)) ?? 0,
            "default": dev == def,
        ])
    }
    let data = try! JSONSerialization.data(withJSONObject: out)
    FileHandle.standardOutput.write(data + Data("\n".utf8))
}

// ------------------------------------------------------------------ record
final class Recording {
    var tapID = AudioObjectID(0)
    var aggregateID = AudioObjectID(0)
    var procID: AudioDeviceIOProcID?
    var channels = 2
    var interleaved = true
    var scratch = [Float]()
    let lock = NSLock()
    var stopped = false

    func start(deviceUID: String?, excludePID: pid_t?) {
        var excluded: [AudioObjectID] = []
        if let pid = excludePID, let obj = processObject(pid: pid) { excluded.append(obj) }

        let mainUID: String
        let desc: CATapDescription
        if let uid = deviceUID {
            guard deviceByUID(uid) != nil else { fail("device not found: \(uid)") }
            mainUID = uid
            desc = CATapDescription(excludingProcesses: excluded, deviceUID: uid, stream: 0)
        } else {
            guard let def = defaultOutput(), let uid = getString(def, kAudioDevicePropertyDeviceUID) else {
                fail("no default output device")
            }
            mainUID = uid
            desc = CATapDescription(stereoGlobalTapButExcludeProcesses: excluded)
        }
        desc.uuid = UUID()
        desc.isPrivate = true
        desc.muteBehavior = .unmuted
        desc.name = "ClusterSound Recorder"
        check(AudioHardwareCreateProcessTap(desc, &tapID), "cannot create the audio tap")

        let aggregate: [String: Any] = [
            kAudioAggregateDeviceNameKey: "ClusterSound Recorder",
            kAudioAggregateDeviceUIDKey: "cs-tap-" + UUID().uuidString,
            kAudioAggregateDeviceMainSubDeviceKey: mainUID,
            kAudioAggregateDeviceIsPrivateKey: true,
            kAudioAggregateDeviceIsStackedKey: false,
            kAudioAggregateDeviceTapAutoStartKey: true,
            kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: mainUID]],
            kAudioAggregateDeviceTapListKey: [[kAudioSubTapDriftCompensationKey: true,
                                               kAudioSubTapUIDKey: desc.uuid.uuidString]],
        ]
        check(AudioHardwareCreateAggregateDevice(aggregate as CFDictionary, &aggregateID),
              "cannot create the aggregate device")

        guard let fmt = getValue(tapID, kAudioTapPropertyFormat, AudioStreamBasicDescription()) else {
            fail("tap format not available")
        }
        guard fmt.mFormatID == kAudioFormatLinearPCM, fmt.mFormatFlags & kAudioFormatFlagIsFloat != 0,
              fmt.mBitsPerChannel == 32 else { fail("tap format not supported") }
        channels = Int(fmt.mChannelsPerFrame)
        interleaved = fmt.mFormatFlags & kAudioFormatFlagIsNonInterleaved == 0
        // The IOProc runs at the aggregate's rate (its main device): a global tap reports 48 kHz even when the
        // hardware runs at 44.1 kHz, and Core Audio resamples it, so the aggregate's rate is the real one.
        let aggRate = getValue(aggregateID, kAudioDevicePropertyNominalSampleRate, Float64(0)) ?? 0
        let rate = aggRate > 0 ? aggRate : fmt.mSampleRate
        let header = "{\"sample_rate\": \(rate), \"channels\": \(channels)}\n"
        writeOut(Array(header.utf8))

        let queue = DispatchQueue(label: "cs-tap.io", qos: .userInteractive)
        check(AudioDeviceCreateIOProcIDWithBlock(&procID, aggregateID, queue) { [unowned self] _, input, _, _, _ in
            self.deliver(input)
        }, "cannot read from the tap")
        check(AudioDeviceStart(aggregateID, procID), "cannot start the recording")
    }

    func deliver(_ input: UnsafePointer<AudioBufferList>) {
        let list = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: input))
        if interleaved {
            for buf in list where buf.mData != nil && buf.mDataByteSize > 0 {
                writeOut(UnsafeRawBufferPointer(start: buf.mData, count: Int(buf.mDataByteSize)))
            }
            return
        }
        // one buffer per channel: interleave
        let planes = list.filter { $0.mData != nil }
        guard let first = planes.first else { return }
        let frames = Int(first.mDataByteSize) / MemoryLayout<Float>.size
        let n = planes.count
        if scratch.count < frames * n { scratch = [Float](repeating: 0, count: frames * n) }
        for (c, buf) in planes.enumerated() {
            let p = buf.mData!.assumingMemoryBound(to: Float.self)
            for i in 0..<frames { scratch[i * n + c] = p[i] }
        }
        scratch.withUnsafeBytes { writeOut(UnsafeRawBufferPointer(rebasing: $0[0..<(frames * n * 4)])) }
    }

    // The IOProc must never block: it copies the bytes and a serial queue writes them to stdout.
    let out = DispatchQueue(label: "cs-tap.out")

    func writeOut<C: Collection>(_ bytes: C) where C.Element == UInt8 {
        let data = Data(bytes)
        out.async {
            let ok = data.withUnsafeBytes { fwrite($0.baseAddress, 1, data.count, stdout) == data.count }
            fflush(stdout)
            if !ok { self.stop(); exit(0) }  // the reader went away
        }
    }

    func stop() {
        lock.lock()
        defer { lock.unlock() }
        if stopped { return }
        stopped = true
        if aggregateID != 0 {
            AudioDeviceStop(aggregateID, procID)
            if let p = procID { AudioDeviceDestroyIOProcID(aggregateID, p) }
            AudioHardwareDestroyAggregateDevice(aggregateID)
        }
        if tapID != 0 { AudioHardwareDestroyProcessTap(tapID) }
    }
}

// ------------------------------------------------------------------ main
let args = CommandLine.arguments
func option(_ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}

signal(SIGPIPE, SIG_IGN)
switch args.dropFirst().first {
case "list":
    listDevices()
case "record":
    let device = option("--device") ?? "all"
    let rec = Recording()
    rec.start(deviceUID: device == "all" ? nil : device, excludePID: option("--exclude-pid").flatMap { pid_t($0) })
    var sources: [DispatchSourceSignal] = []
    for sig in [SIGTERM, SIGINT] {
        signal(sig, SIG_IGN)
        let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
        src.setEventHandler { rec.stop(); exit(0) }
        src.resume()
        sources.append(src)
    }
    // the parent closing our stdin also means stop
    Thread.detachNewThread {
        while FileHandle.standardInput.availableData.count > 0 {}
        rec.stop()
        exit(0)
    }
    dispatchMain()
default:
    fail("usage: cs-tap list | cs-tap record --device <uid|all> [--exclude-pid <pid>]")
}
