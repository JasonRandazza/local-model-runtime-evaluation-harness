import Foundation


private typealias PluginContextPointer = UnsafeMutableRawPointer
private typealias FreeStringFunction = @convention(c) (UnsafePointer<CChar>?) -> Void
private typealias InitFunction = @convention(c) () -> PluginContextPointer?
private typealias DestroyFunction = @convention(c) (PluginContextPointer?) -> Void
private typealias ManifestFunction = @convention(c) (PluginContextPointer?) -> UnsafePointer<CChar>?
private typealias InvokeFunction = @convention(c) (
    PluginContextPointer?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?
) -> UnsafePointer<CChar>?
private typealias RouteFunction = @convention(c) (PluginContextPointer?, UnsafePointer<CChar>?) -> UnsafePointer<CChar>?
private typealias ConfigChangedFunction = @convention(c) (
    PluginContextPointer?, UnsafePointer<CChar>?, UnsafePointer<CChar>?
) -> Void
private typealias TaskEventFunction = @convention(c) (
    PluginContextPointer?, UnsafePointer<CChar>?, Int32, UnsafePointer<CChar>?
) -> Void


private struct PluginAPI {
    var freeString: FreeStringFunction?
    var initialize: InitFunction?
    var destroy: DestroyFunction?
    var getManifest: ManifestFunction?
    var invoke: InvokeFunction?
    var version: UInt32
    var handleRoute: RouteFunction?
    var onConfigChanged: ConfigChangedFunction?
    var onTaskEvent: TaskEventFunction?
}


private final class PluginContext {}


private func makeCString(_ string: String) -> UnsafePointer<CChar>? {
    guard let pointer = strdup(string) else { return nil }
    return UnsafePointer(pointer)
}


nonisolated(unsafe) private var pluginAPI = PluginAPI(
    freeString: { pointer in
        if let pointer { free(UnsafeMutableRawPointer(mutating: pointer)) }
    },
    initialize: {
        Unmanaged.passRetained(PluginContext()).toOpaque()
    },
    destroy: { context in
        guard let context else { return }
        Unmanaged<PluginContext>.fromOpaque(context).release()
    },
    getManifest: { _ in
        makeCString(HarnessCore.manifestJSON)
    },
    invoke: { _, typePointer, idPointer, payloadPointer in
        guard let typePointer, let idPointer, let payloadPointer else {
            return makeCString(HarnessCore.failure(code: "invalid_request", message: "Missing invocation data"))
        }
        let type = String(cString: typePointer)
        guard type == "tool" else {
            return makeCString(HarnessCore.failure(code: "unknown_capability", message: "Only tools are supported"))
        }
        return makeCString(
            HarnessCore.invoke(
                toolID: String(cString: idPointer),
                payload: String(cString: payloadPointer)
            )
        )
    },
    version: 2,
    handleRoute: nil,
    onConfigChanged: nil,
    onTaskEvent: nil
)


@_cdecl("osaurus_plugin_entry_v2")
public func osaurusPluginEntryV2(_ opaqueHost: UnsafeRawPointer?) -> UnsafeRawPointer? {
    _ = opaqueHost
    return withUnsafePointer(to: &pluginAPI) { UnsafeRawPointer($0) }
}


@_cdecl("osaurus_plugin_entry")
public func osaurusPluginEntry() -> UnsafeRawPointer? {
    withUnsafePointer(to: &pluginAPI) { UnsafeRawPointer($0) }
}
