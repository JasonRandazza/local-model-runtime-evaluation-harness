// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "OsaurusEvaluationHarness",
    platforms: [.macOS(.v15)],
    products: [
        .library(name: "OsaurusEvaluationHarness", type: .dynamic, targets: ["OsaurusEvaluationHarness"])
    ],
    targets: [
        .target(
            name: "OsaurusEvaluationHarness",
            path: "Sources/OsaurusEvaluationHarness"
        ),
        .testTarget(
            name: "OsaurusEvaluationHarnessTests",
            dependencies: ["OsaurusEvaluationHarness"],
            path: "Tests/OsaurusEvaluationHarnessTests"
        )
    ]
)
