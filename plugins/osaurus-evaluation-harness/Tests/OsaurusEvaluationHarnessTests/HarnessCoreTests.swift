import Foundation
import Testing
@testable import OsaurusEvaluationHarness


@Test func exposesSevenToolsIncludingDiscover() throws {
    #expect(Set(HarnessCore.toolIDs) == [
        "inventory", "preflight", "run_scenario", "status", "cancel", "cleanup", "discover",
    ])
    let data = try #require(HarnessCore.manifestJSON.data(using: .utf8))
    let manifest = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    #expect(manifest["version"] as? String == "0.4.0")
    let capabilities = try #require(manifest["capabilities"] as? [String: Any])
    let tools = try #require(capabilities["tools"] as? [[String: Any]])
    #expect(tools.count == 7)
    #expect(capabilities["routes"] == nil)
    for tool in tools {
        #expect(tool["permission_policy"] as? String == "ask")
        let parameters = try #require(tool["parameters"] as? [String: Any])
        #expect(parameters["additionalProperties"] as? Bool == false)
    }
}


@Test func validatesOnlyApprovedStageRunIDShapes() {
    #expect(HarnessCore.isValidRunID("stage0-20260713-001"))
    #expect(HarnessCore.isValidRunID("stage1-20260713-001"))
    #expect(HarnessCore.isValidRunID("stage2-20260713-001"))
    #expect(!HarnessCore.isValidRunID("stage0-20260713-001;whoami"))
}


@Test func stageToolsDoNotBroadenArgumentsExceptDiscover() throws {
    let data = try #require(HarnessCore.manifestJSON.data(using: .utf8))
    let manifest = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    let capabilities = try #require(manifest["capabilities"] as? [String: Any])
    let tools = try #require(capabilities["tools"] as? [[String: Any]])
    for tool in tools {
        let id = try #require(tool["id"] as? String)
        let parameters = try #require(tool["parameters"] as? [String: Any])
        let properties = try #require(parameters["properties"] as? [String: Any])
        if id == "inventory" {
            #expect(properties.isEmpty)
        } else if id == "discover" {
            #expect(Set(properties.keys) == ["command"])
        } else {
            #expect(Set(properties.keys) == ["run_id"])
        }
    }
}


@Test func mapsToolsToFixedOperations() {
    #expect(HarnessCore.operation(for: "run_scenario") == "run-scenario")
    #expect(HarnessCore.operation(for: "inventory") == "inventory")
    #expect(HarnessCore.operation(for: "discover") == nil)
    #expect(HarnessCore.operation(for: "shell") == nil)
    #expect(HarnessCore.executablePath == "/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage0")
    #expect(HarnessCore.discoverExecutablePath.hasSuffix("/bin/lmre-discover"))
}


@Test func discoverRejectsExecuteAndUnknownArgs() {
    let execute = HarnessCore.invoke(
        toolID: "discover",
        payload: #"{"command":"execute"}"#
    )
    #expect(execute.contains("invalid_args"))
    let extra = HarnessCore.invoke(
        toolID: "discover",
        payload: #"{"command":"propose","family":"gemma"}"#
    )
    #expect(extra.contains("invalid_args"))
}
