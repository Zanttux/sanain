// Print the window number of the largest normal window owned by a pid,
// for `screencapture -l` (scripts/screenshots/shoot.sh).
import CoreGraphics
import Foundation

guard CommandLine.arguments.count == 2, let pid = Int(CommandLine.arguments[1]) else { exit(2) }
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
let best = list
    .filter { ($0[kCGWindowOwnerPID as String] as? Int) == pid && ($0[kCGWindowLayer as String] as? Int) == 0 }
    .max { a, b in
        let area = { (w: [String: Any]) -> Double in
            let r = w[kCGWindowBounds as String] as? [String: Double] ?? [:]
            return (r["Width"] ?? 0) * (r["Height"] ?? 0)
        }
        return area(a) < area(b)
    }
guard let n = best?[kCGWindowNumber as String] as? Int else { exit(1) }
print(n)
