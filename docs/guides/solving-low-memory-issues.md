# Solving Low Memory Issues (Java Server)

If you see a warning stating that the DriveWire Java server must disable some functions due to lack of free memory, or an error stating `java.lang.OutOfMemoryError`, this guide will help you resolve it.

> [!NOTE]
> This guide applies specifically to the **Java-based** implementations of DriveWire. Native versions (C, Swift, MicroPython) handle memory management differently.

## 🧠 Understanding Java Memory

The Java Virtual Machine (JVM) imposes a strict limit on the amount of RAM any one application can use. By default, this limit can be quite low. For the full DriveWire GUI, a safe estimate is **20MB + (size of the largest disk image)**, typically capped at 128MB or 256MB.

## 🛠️ How to Increase Memory

You can specify the maximum memory limit using the `-Xmx` argument when launching the server.

- **Standard Command**:
  `java -Xmx256m -jar DriveWire.jar`
- **macOS (Special Requirement)**:
  `java -Xmx256m -XstartOnFirstThread -jar DriveWire.jar`

### Windows (Launcher)
If you use the Windows launcher, you may need to create a `.bat` file with the command above or adjust your system-wide Java settings in the Windows Control Panel.

### Linux / macOS (Scripts)
Simply edit your launch script to include the `-Xmx256m` (or higher) argument.

---
[Return to Documentation Index](../index.md)
