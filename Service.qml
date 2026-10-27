import QtQuick
import Quickshell.Io

Item {
  id: root
  readonly property string pluginDirectory: decodeURIComponent(String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "")).replace(/\/$/, "")
  property bool notified: false

  Component.onCompleted: bootstrapProc.running = true

  Process {
    id: bootstrapProc
    command: ["python3", "-B", root.pluginDirectory + "/bootstrap.py", root.pluginDirectory]
    property string resultText: ""
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: bootstrapProc.resultText = text }
    onExited: function(code) {
      try {
        const result = JSON.parse(resultText)
        if (code === 0 && result.needsSetup && !root.notified) {
          root.notified = true
          notification.command = ["notify-send", "--", "Omarchy Cooler LCD", "USB permission needed. Run in a terminal:\n" + result.setupCommand]
          notification.running = true
        }
      } catch (e) { console.warn("Omarchy Cooler LCD: bootstrap failed; check its output") }
      if (code !== 0) console.warn("Omarchy Cooler LCD: " + resultText)
    }
  }

  Process { id: notification }
}
