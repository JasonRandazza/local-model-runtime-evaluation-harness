import Foundation


enum HarnessCore {
    static let executablePath = "/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage0"
    static let toolIDs = ["inventory", "preflight", "run_scenario", "status", "cancel", "cleanup"]

    private static let operationMap = [
        "inventory": "inventory",
        "preflight": "preflight",
        "run_scenario": "run-scenario",
        "status": "status",
        "cancel": "cancel",
        "cleanup": "cleanup",
    ]

    static func operation(for toolID: String) -> String? {
        operationMap[toolID]
    }

    static func isValidRunID(_ runID: String) -> Bool {
        runID.range(of: #"^stage[012]-[0-9]{8}-[0-9]{3}$"#, options: .regularExpression) != nil
    }

    static var manifestJSON: String {
        let tools: [[String: Any]] = toolIDs.map { toolID in
            let needsRunID = toolID != "inventory"
            var parameters: [String: Any] = [
                "type": "object",
                "properties": [String: Any](),
                "additionalProperties": false,
            ]
            if needsRunID {
                parameters["properties"] = [
                    "run_id": [
                        "type": "string",
                        "pattern": "^stage[012]-[0-9]{8}-[0-9]{3}$",
                        "description": "Approved Stage 0, Stage 1, or Stage 2 run identifier",
                    ]
                ]
                parameters["required"] = ["run_id"]
            }
            return [
                "id": toolID,
                "description": description(for: toolID),
                "parameters": parameters,
                "requirements": [],
                "permission_policy": "ask",
            ]
        }
        let manifest: [String: Any] = [
            "plugin_id": "local.jrazz.model-runtime-evaluation-harness",
            "name": "Local Model Evaluation Harness",
            "version": "0.3.0",
            "description": "Six fail-closed Stage 0, Stage 1, and Stage 2A runtime-evaluation operations",
            "license": "MIT",
            "authors": ["Jason Randazza"],
            "min_macos": "15.0",
            "min_osaurus": "0.22.3",
            "capabilities": ["tools": tools],
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: manifest, options: [.sortedKeys]),
              let json = String(data: data, encoding: .utf8)
        else {
            return failure(code: "manifest_encoding_failed", message: "Plugin manifest could not be encoded")
        }
        return json
    }

    static func invoke(toolID: String, payload: String) -> String {
        guard let operation = operation(for: toolID) else {
            return failure(code: "unknown_tool", message: "Unknown evaluation tool")
        }
        guard let data = payload.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return failure(code: "invalid_args", message: "Tool arguments must be a JSON object")
        }
        let allowedKeys: Set<String> = toolID == "inventory" ? [] : ["run_id"]
        let userKeys = Set(object.keys.filter { !$0.hasPrefix("_") })
        guard userKeys.isSubset(of: allowedKeys) else {
            return failure(code: "invalid_args", message: "Unknown tool argument")
        }

        var runID: String?
        if toolID != "inventory" {
            guard let value = object["run_id"] as? String, isValidRunID(value) else {
                return failure(code: "invalid_args", message: "A valid approved run_id is required")
            }
            runID = value
        }
        return HarnessProcess.run(operation: operation, runID: runID)
    }

    static func failure(code: String, message: String) -> String {
        encode([
            "ok": false,
            "error": ["code": code, "message": message],
        ])
    }

    static func success(data: Any, summary: String) -> String {
        encode(["ok": true, "data": data, "summary": summary])
    }

    private static func encode(_ value: Any) -> String {
        guard let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
              let string = String(data: data, encoding: .utf8)
        else {
            return #"{"ok":false,"error":{"code":"encoding_failed","message":"Response encoding failed"}}"#
        }
        return string
    }

    private static func description(for toolID: String) -> String {
        switch toolID {
        case "inventory": return "Passively report approved runtime component availability without starting processes"
        case "preflight": return "Validate an approved Stage 0, Stage 1, or Stage 2A manifest and initialize evidence"
        case "run_scenario": return "Run only the scenario authorized by the approved manifest"
        case "status": return "Read persisted state for an approved evaluation run"
        case "cancel": return "Request cancellation of the harness-owned run"
        case "cleanup": return "Finalize owned cleanup and checksummed evidence"
        default: return "Unsupported tool"
        }
    }
}


enum HarnessProcess {
    private static let maximumOutputBytes = 1_048_576

    static func run(operation: String, runID: String?) -> String {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: HarnessCore.executablePath)
        process.arguments = [operation] + (runID.map { [$0] } ?? [])
        let output = Pipe()
        let errors = Pipe()
        process.standardOutput = output
        process.standardError = errors

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return HarnessCore.failure(code: "runner_unavailable", message: "The fixed evaluation runner could not start")
        }

        let stdout = output.fileHandleForReading.readDataToEndOfFile()
        let stderr = errors.fileHandleForReading.readDataToEndOfFile()
        guard stdout.count <= maximumOutputBytes, stderr.count <= maximumOutputBytes else {
            return HarnessCore.failure(code: "runner_output_too_large", message: "Runner output exceeded the bounded limit")
        }
        guard process.terminationStatus == 0,
              let object = try? JSONSerialization.jsonObject(with: stdout) as? [String: Any],
              object["ok"] as? Bool == true,
              let result = object["result"]
        else {
            if let object = try? JSONSerialization.jsonObject(with: stdout) as? [String: Any],
               let error = object["error"] as? [String: Any] {
                return HarnessCore.failure(
                    code: error["kind"] as? String ?? "runner_failed",
                    message: error["message"] as? String ?? "Evaluation runner failed"
                )
            }
            return HarnessCore.failure(code: "runner_failed", message: "Evaluation runner returned invalid output")
        }
        return HarnessCore.success(data: result, summary: "Evaluation \(operation) completed")
    }
}
