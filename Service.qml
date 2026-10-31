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
          notification.running = true
        }
      } catch (e) { console.warn("Omarchy Cooler LCD: bootstrap failed; check its output") }
      if (code !== 0) console.warn("Omarchy Cooler LCD: " + resultText)
    }
  }

  // Clicking the notification (its default action) opens the password prompt
  // for the one-time setup.sh step.
  Process {
    id: notification
    command: ["notify-send", "--wait", "--action=default=Allow access", "--", "Omarchy Cooler LCD 5131",
              "Click to allow the cooler display (one-time password)."]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.trim() === "default") grant.running = true
    }
  }

  Process {
    id: grant
    command: ["pkexec", "/usr/bin/bash", root.pluginDirectory + "/setup.sh"]
    onExited: function(code) { if (code !== 0) console.warn("Omarchy Cooler LCD: permission not granted") }
  }
}
