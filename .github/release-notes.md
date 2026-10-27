**Before you start it:** the programs are not signed (signing costs money every year), so your computer may warn you
the first time.

- **Windows:** if "Windows protected your PC" appears, click **More info**, then **Run anyway**. An antivirus may
  also ask; allow it.
- **Linux:** a downloaded file cannot be started until it is allowed to run: in its Properties tick "Allow executing
  file as program", or run `chmod +x word-tierlister-linux`.
- **macOS** (Apple Silicon): unzip `word-tierlister-macos.zip` and move "Word Tierlister" into a folder of its own. The
  first time, macOS says it cannot check the app: open **System Settings > Privacy & Security**, scroll down and click
  **Open Anyway**. If it says the app "is damaged", run `xattr -dr com.apple.quarantine "Word Tierlister.app"` in
  Terminal, then open it again.

Put the program in a folder of its own: your save stays next to it, and the first start unpacks the program's
source code into "Word Tierlister source" beside it (File > Source & Updates has it too). To run from the source
code instead, see the README.
